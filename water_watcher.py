import RPi.GPIO as GPIO
import time
from datetime import datetime, timedelta
import logging
import requests
import os
import sqlite3
from typing import Optional
import argparse

from leviton import LevitonController


class Database:
    def __init__(self, db_path: str = "water_sensor.db"):
        """Initialize database connection"""
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Create database and tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS water_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL,
                    location TEXT,
                    action_taken TEXT
                )
            """
            )
            conn.commit()

    def log_event(self, status: str, location: str, action_taken: Optional[str] = None):
        """Log a water detection event"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO water_events (status, location, action_taken) VALUES (?, ?, ?)",
                    (status, location, action_taken),
                )
                conn.commit()
        except Exception as e:
            logging.error(f"Database error: {str(e)}")

    def get_recent_events(self, limit: int = 10):
        """Get recent water detection events"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            return cursor.execute(
                "SELECT * FROM water_events ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self._token = token
        self._chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"

    def send_message(self, message: str) -> bool:
        try:
            url = f"{self.base_url}/sendMessage"
            data = {"chat_id": self._chat_id, "text": message, "parse_mode": "HTML"}
            response = requests.post(url, data=data)
            response.raise_for_status()
            return True
        except Exception as e:
            logging.error(f"Failed to send Telegram message: {str(e)}")
            return False


class WaterDetector:
    def __init__(
        self,
        sensor_pin: int,
        power_pin: int,
        leviton_cntrl: Optional[LevitonController] = None,
        telegram_notifier: Optional[TelegramNotifier] = None,
        database: Optional[Database] = None,
        debug: bool = False,
    ):
        """
        Initialize the water detector with optional notifications and automation
        """
        self.sensor_pin = sensor_pin
        self.power_pin = power_pin
        self.telegram = telegram_notifier
        self.db = database
        self.location = os.uname().nodename
        self.debug = debug

        self.leviton_cntrl = leviton_cntrl

        # State tracking
        self.last_state = False
        self.last_reading_time = None
        self.last_notification_time = None

        # Minimum time between notifications
        self.notification_cooldown = timedelta(hours=1) if debug else timedelta(hours=6)

        # Setup logging
        logging.basicConfig(
            filename="water_detection.log",
            level=logging.DEBUG if debug else logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )

        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.sensor_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(self.power_pin, GPIO.OUT)

        # Initialize database if not provided
        if not self.db:
            self.db = Database()

        logging.info("Water detector initialized")
        if self.telegram:
            self.telegram.send_message(
                "🔄 Water detection system initialized and monitoring"
            )

    def debug_print(self, message: str):
        """Print debug messages if debug mode is on"""
        if self.debug:
            print(f"DEBUG: {message}")
            logging.debug(message)

    def should_notify(self) -> bool:
        """Check if enough time has passed to send another notification"""
        if not self.last_notification_time:
            return True
        return datetime.now() - self.last_notification_time > self.notification_cooldown

    def check_water(self) -> bool:
        try:
            self.debug_print("Starting water check")
            GPIO.output(self.power_pin, GPIO.HIGH)
            time.sleep(0.1)

            readings = []
            for _ in range(5):
                reading = GPIO.input(self.sensor_pin)
                readings.append(reading)
                self.debug_print(f"Sensor reading: {reading}")
                time.sleep(0.01)

            GPIO.output(self.power_pin, GPIO.LOW)

            result = sum(readings) > len(readings) / 2
            self.debug_print(f"Water check result: {result}")
            return result

        except Exception as e:
            logging.error(f"Error checking water: {str(e)}")
            GPIO.output(self.power_pin, GPIO.LOW)
            if self.telegram:
                self.telegram.send_message(f"⚠️ Error checking water sensor: {str(e)}")
            raise

    def monitor(self, check_interval: float = 1):
        """
        Continuously monitor for water with improved state tracking and debugging
        """
        print("\nStarting water monitoring...")
        print("Press CTRL+C to stop\n")

        try:
            while True:
                current_time = datetime.now()
                current_state = self.check_water()
                emoji = "💧" if current_state else "🔹"

                self.debug_print(f"Current state: {current_state} at {current_time}")

                if current_time.hour > 6 and current_time.hour < 18 and current_state:
                    if (
                        self.leviton_cntrl
                        and self.leviton_cntrl.get_plug_status() == "OFF"
                    ):
                        self.debug_print("Plug is OFF, turning it ON")

                        self.leviton_cntrl.set_plug("ON")

                        message = "Turning plug on."
                        self.debug_print(message)
                        logging.info(message)

                        if self.telegram:
                            telegram_msg = (
                                f"{emoji} Water Sensor Update {emoji}\n"
                                f"Water detected.\n"
                                f"Turning bird bath ON"
                            )
                            self.telegram.send_message(telegram_msg)

                if self.last_reading_time is None:
                    # Initial reading
                    self.last_reading_time = current_time
                    self.last_state = current_state

                    state_changed = True
                else:
                    state_changed = current_state != self.last_state

                if state_changed or self.should_notify():
                    status = "WET" if current_state else "DRY"
                    message = f"Status changed to: {status}"
                    self.debug_print(message)
                    logging.info(message)

                    time_since_last_reading = current_time - self.last_reading_time

                    # Log to database
                    if self.db:
                        self.db.log_event(
                            status=status,
                            location=self.location,
                            action_taken=f"Time since last reading: {time_since_last_reading}",
                        )

                    # Send notification if enabled
                    if self.telegram:
                        telegram_msg = (
                            f"{emoji} Water Sensor Update {emoji}\n"
                            f"Location: {self.location}\n"
                            f"Status: {status}\n"
                            f"Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                            f"Duration: {time_since_last_reading}"
                        )
                        self.telegram.send_message(telegram_msg)
                        self.last_notification_time = current_time

                    self.last_state = current_state
                    self.last_reading_time = current_time

                time.sleep(check_interval)

        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
            if self.telegram:
                self.telegram.send_message("🛑 Water monitoring stopped by user")
        except Exception as e:
            logging.error(f"Monitoring error: {str(e)}")
            if self.telegram:
                self.telegram.send_message(f"🚨 Monitoring error: {str(e)}")
            raise
        finally:
            GPIO.output(self.power_pin, GPIO.LOW)
            GPIO.cleanup()


if __name__ == "__main__":
    # Add command-line argument parsing
    parser = argparse.ArgumentParser(description="Water Detector Monitoring")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    # Configuration
    telegram_token = os.environ.get("SECRET_TELEGRAM_TOKEN")
    telegram_chat = os.environ.get("SECRET_TELEGRAM_CHAT")

    leviton_email = os.environ.get("SECRET_LEVITON_USER")
    leviton_pass = os.environ.get("SECRET_LEVITON_PASS")

    # Initialize components
    telegram = TelegramNotifier(telegram_token, telegram_chat)
    db = Database()

    # Initialize water detector with all components and debug flag
    detector = WaterDetector(
        sensor_pin=17,
        power_pin=27,
        leviton_cntrl=LevitonController(leviton_email, leviton_pass),
        telegram_notifier=telegram,
        database=db,
        debug=args.debug,
    )

    # Start monitoring
    detector.monitor(check_interval=120)
