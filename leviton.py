# -*- coding: utf-8 -*-
"""Leviton Decora Smart Wi-Fi Plug-in Dimmer (DW3HL) Controller
This module provides a controller for the Leviton Decora Smart Wi-Fi Plug-in Dimmer (DW3HL).
It allows you to login to the Leviton API, list devices, get the status of the smart plug,
and set the plug on or off.
"""
import requests
from datetime import datetime

class LevitonController:
    """Based on https://github.com/tlyakhov/python-decora_wifi"""
    def __init__(self, email, password):
        self.base_url = "https://my.leviton.com/api"

        self._email = email
        self._password = password

        self.access_token = None

        self.residence_id = "903353"
        self.device_id = "1920823"

    def login(self):
        """Login to Leviton API and get access token"""
        login_url = f"{self.base_url}/Person/login"
        payload = {"email": self._email, "password": self._password}

        try:
            response = requests.post(login_url, json=payload)
            response.raise_for_status()
            self.access_token = response.json().get("id")
            print("Successfully logged in to Leviton")
        except requests.exceptions.RequestException as e:
            print(f"Failed to login: {e}")
            raise

    def list_devices(self):
        """List all devices and their IDs"""

        if self.access_token is None:
            self.login()

        devices_url = f"{self.base_url}/Residences/{self.residence_id}/iotSwitches"
        headers = {"Authorization": self.access_token}

        try:
            response = requests.get(devices_url, headers=headers)
            response.raise_for_status()
            devices = response.json()

            print("\nAvailable Devices:")
            print("-----------------")
            for device in devices:
                print(f"Device ID: {device['id']}")
                print(f"Name: {device.get('name', 'Unnamed')}")
                print(f"Type: {device.get('type', 'Unknown')}")
                print(f"Location: {device.get('location', 'Unknown')}")
                print("-----------------")

            return devices
        except requests.exceptions.RequestException as e:
            print(f"Failed to list devices: {e}")
            raise

    def get_plug_status(self):
        """Get the status of the smart plug"""
        if not self.access_token:
            self.login()

        control_url = f"{self.base_url}/IotSwitches/{self.device_id}"
        headers = {"Authorization": self.access_token}

        try:
            response = requests.get(control_url, headers=headers)
            response.raise_for_status()
            status = response.json().get("power")
            print(f"Plug status: {status}")
            return status
        except requests.exceptions.RequestException as e:
            print(f"Failed to get plug status: {e}")
            raise

    def set_plug(self, power):
        assert power in ['ON', 'OFF']

        """Turn on the smart plug"""
        if not self.access_token:
            self.login()

        control_url = f"{self.base_url}/IotSwitches/{self.device_id}"
        headers = {"Authorization": self.access_token}
        payload = {"power": power}

        try:
            response = requests.put(control_url, headers=headers, json=payload)
            response.raise_for_status()
            print(
                f"Successfully turned on plug at {datetime.now().strftime('%H:%M:%S')}"
            )
        except requests.exceptions.RequestException as e:
            print(f"Failed to turn on plug: {e}")
            raise


def test_controller():
    import os
    cntrl = LevitonController(
        os.environ.get('SECRET_LEVITON_USER'), os.environ.get('SECRET_LEVITON_PASS')
    )

    print(cntrl.list_devices())
    print(cntrl.get_plug_status())
    cntrl.set_plug('ON')
    print(cntrl.get_plug_status())
    cntrl.set_plug('OFF')
    print(cntrl.get_plug_status())

if __name__ == "__main__":
    test_controller()
