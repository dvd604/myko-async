import json
import os

import pytest

from hubspace_async import device

current_path = os.path.dirname(os.path.realpath(__file__))


with open(os.path.join(current_path, "data", "device_lock.json")) as fh:
    device_lock_response = json.load(fh)


@pytest.mark.parametrize(
    "hs_device,expected",
    [
        # Everything is set correctly
        (
            {
                "id": "id",
                "device_id": "device_id",
                "model": "model",
                "device_class": "device_class",
                "default_name": "default_name",
                "default_image": "default_image",
                "friendly_name": "friendly_name",
                "functions": ["functions!"],
                "states": [],
            },
            device.HubSpaceDevice(
                **{
                    "id": "id",
                    "device_id": "device_id",
                    "model": "model",
                    "device_class": "device_class",
                    "default_name": "default_name",
                    "default_image": "default_image",
                    "friendly_name": "friendly_name",
                    "functions": ["functions!"],
                    "states": [],
                }
            ),
        ),
        # DriskolFan
        (
            {
                "id": "id",
                "device_id": "device_id",
                "model": "",
                "device_class": "device_class",
                "default_name": "default_name",
                "default_image": "ceiling-fan-snyder-park-icon",
                "friendly_name": "friendly_name",
                "functions": ["functions!"],
                "states": [],
            },
            device.HubSpaceDevice(
                **{
                    "id": "id",
                    "device_id": "device_id",
                    "model": "DriskolFan",
                    "device_class": "device_class",
                    "default_name": "default_name",
                    "default_image": "ceiling-fan-snyder-park-icon",
                    "friendly_name": "friendly_name",
                    "functions": ["functions!"],
                    "states": [],
                }
            ),
        ),
        # VinwoodFan
        (
            {
                "id": "id",
                "device_id": "device_id",
                "model": "",
                "device_class": "device_class",
                "default_name": "default_name",
                "default_image": "ceiling-fan-vinings-icon",
                "friendly_name": "friendly_name",
                "functions": ["functions!"],
                "states": [],
            },
            device.HubSpaceDevice(
                **{
                    "id": "id",
                    "device_id": "device_id",
                    "model": "VinwoodFan",
                    "device_class": "device_class",
                    "default_name": "default_name",
                    "default_image": "ceiling-fan-vinings-icon",
                    "friendly_name": "friendly_name",
                    "functions": ["functions!"],
                    "states": [],
                }
            ),
        ),
        # ZandraFan
        (
            {
                "id": "id",
                "device_id": "device_id",
                "model": "TBD",
                "device_class": "fan",
                "default_name": "default_name",
                "default_image": "ceiling-fan-chandra-icon",
                "friendly_name": "friendly_name",
                "functions": ["functions!"],
                "states": [],
            },
            device.HubSpaceDevice(
                **{
                    "id": "id",
                    "device_id": "device_id",
                    "model": "ZandraFan",
                    "device_class": "fan",
                    "default_name": "default_name",
                    "default_image": "ceiling-fan-chandra-icon",
                    "friendly_name": "friendly_name",
                    "functions": ["functions!"],
                    "states": [],
                }
            ),
        ),
        # NevaliFan
        (
            {
                "id": "id",
                "device_id": "device_id",
                "model": "TBD",
                "device_class": "fan",
                "default_name": "default_name",
                "default_image": "ceiling-fan-ac-cct-dardanus-icon",
                "friendly_name": "friendly_name",
                "functions": ["functions!"],
                "states": [],
            },
            device.HubSpaceDevice(
                **{
                    "id": "id",
                    "device_id": "device_id",
                    "model": "NevaliFan",
                    "device_class": "fan",
                    "default_name": "default_name",
                    "default_image": "ceiling-fan-ac-cct-dardanus-icon",
                    "friendly_name": "friendly_name",
                    "functions": ["functions!"],
                    "states": [],
                }
            ),
        ),
        # TagerFan
        (
            {
                "id": "id",
                "device_id": "device_id",
                "model": "",
                "device_class": "fan",
                "default_name": "default_name",
                "default_image": "ceiling-fan-slender-icon",
                "friendly_name": "friendly_name",
                "functions": ["functions!"],
                "states": [],
            },
            device.HubSpaceDevice(
                **{
                    "id": "id",
                    "device_id": "device_id",
                    "model": "TagerFan",
                    "device_class": "fan",
                    "default_name": "default_name",
                    "default_image": "ceiling-fan-slender-icon",
                    "friendly_name": "friendly_name",
                    "functions": ["functions!"],
                    "states": [],
                }
            ),
        ),
    ],
)
def test_HubSpaceDevice(hs_device, expected):
    assert device.HubSpaceDevice(**hs_device) == expected


@pytest.mark.parametrize(
    "hs_device,expected_attrs",
    [
        # Validate when values are missing
        (
            {},
            {
                "id": None,
                "device_id": None,
                "model": None,
                "device_class": None,
                "default_name": None,
                "default_image": None,
                "friendly_name": None,
                "functions": [],
            },
        ),
        # Ensure values are properly parsed
        (
            device_lock_response[0],
            {
                "id": "5a5d5e04-a6ad-47c0-b9f4-b9fe5c049ef4",
                "device_id": "0123f95ec14bdb23",
                "model": "TBD",
                "device_class": "door-lock",
                "default_name": "Keypad Deadbolt Lock",
                "default_image": "keypad-deadbolt-lock-icon",
                "friendly_name": "Friendly Name 2",
                "functions": device_lock_response[0]["description"]["functions"],
            },
        ),
    ],
)
def test_get_hs_device(hs_device, expected_attrs):
    dev = device.get_hs_device(hs_device)
    for key, val in expected_attrs.items():
        assert (
            getattr(dev, key) == val
        ), f"Key {key} did not match, {getattr(dev, key)} != {val}"


@pytest.mark.parametrize(
    "data,expected_attrs",
    [
        # verify defaults
        (
            {
                "functionClass": "class",
                "value": "beans",
            },
            {
                "functionClass": "class",
                "value": "beans",
                "functionInstance": None,
                "lastUpdateTime": None,
            },
        ),
        # verify defaults
        (
            {
                "functionClass": "class",
                "value": "beans",
                "functionInstance": "beans",
                "lastUpdateTime": 4,
            },
            {
                "functionClass": "class",
                "value": "beans",
                "functionInstance": "beans",
                "lastUpdateTime": 4,
            },
        ),
    ],
)
def test_HubSpaceState(data, expected_attrs):
    elem = device.HubSpaceState(**data)
    for key, val in expected_attrs.items():
        assert getattr(elem, key) == val
