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

    def _call_api(self, endpoint, method="GET", payload=None):
        """Call the Leviton API"""

        if self.access_token is None:
            self.login()

        url = f"{self.base_url}/{endpoint}"
        headers = {"Authorization": self.access_token}

        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=payload)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=payload)
            else:
                raise ValueError("Invalid HTTP method")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API call failed: {e}")
            raise

    def list_devices(self):
        """List all devices and their IDs"""

        devices_url = f"Residences/{self.residence_id}/iotSwitches"

        try:
            devices = self._call_api(devices_url, method="GET")

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
        control_url = f"IotSwitches/{self.device_id}"

        try:
            status = self._call_api(control_url, method="GET")
            return status['power']
        except requests.exceptions.RequestException as e:
            print(f"Failed to get plug status: {e}")
            raise

    def set_plug(self, power):
        """Turn on the smart plug"""
        control_url = f"IotSwitches/{self.device_id}"

        assert power in ['ON', 'OFF']
        payload = {"power": power}

        try:
            self._call_api(control_url, method="PUT", payload=payload)
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
