"""Test the for the SLXChargingController coordinator."""

from . import FIXTURE_CONFIG_ENTRY
from homeassistant.core import HomeAssistant
from custom_components.slxchargingcontroller.slxtripplanner import (
    SLXTripPlanner,
    ODOMETER_STORAGE_KEY,
)

from custom_components.slxchargingcontroller.const import ODOMETER_DAYS_BACK

from homeassistant.helpers import storage

import homeassistant.util.dt as dt_util
from datetime import datetime, timedelta
from freezegun.api import FrozenDateTimeFactory, freeze_time

import logging
from unittest.mock import patch

import pytest

ODOMETER_ENTITY_NAME = "kona.odometer_entity_test"


odometer_list_storage: list[(datetime, float)] = [
    (datetime.fromisoformat("2024-01-17 18:54:41.0+00:00"), 1234.0),
    (datetime.fromisoformat("2024-01-18 12:54:41.0+00:00"), 1240.1),  # 6.1
    (datetime.fromisoformat("2024-01-18 14:20:00.0+00:00"), 1310.6),  # 70.5
    (datetime.fromisoformat("2024-01-19 01:00:00.0+00:00"), 1325.6),  # 15.0
    (datetime.fromisoformat("2024-01-21 12:00:41.0+00:00"), 1340),
    (datetime.fromisoformat("2024-01-23 03:10:00.0+00:00"), 1700.1),
    (datetime.fromisoformat("2024-01-24 17:30:00.0+00:00"), 1710.2),
]

odometer_list_entity: list[(datetime, float)] = [
    (datetime.fromisoformat("2024-01-24 12:00:00.0+00:00"), 1705),
    (datetime.fromisoformat("2024-01-26 19:54:41.0+00:00"), 1720.2),
]

odometer_test_time = datetime.fromisoformat("2024-01-27 13:14:15.0+00:00")


async def test_tripplanner_storage_read(hass: HomeAssistant) -> None:
    odometer_list: list[(datetime, float)] = [
        (datetime.fromisoformat("2024-01-17 18:54:41.482455+00:00"), 1234.5),
        (datetime.fromisoformat("2024-01-18 19:54:41.482455+00:00"), 2345.6),
    ]

    data_for_write = {ODOMETER_ENTITY_NAME: odometer_list}
    store = storage.Store(hass, 1, ODOMETER_STORAGE_KEY)
    await store.async_save(data_for_write)

    tripplanner = SLXTripPlanner(hass)
    await tripplanner.initialize(ODOMETER_ENTITY_NAME)
    await tripplanner.read_storage()
    list_odo = tripplanner.odometer_list
    assert len(list_odo) == 2
    assert list_odo[1][1] == 2345.6


async def test_tripplanner_historical_odometer(
    hass: HomeAssistant,
) -> None:
    """No storage available, check that it will request records for last 30 days"""
    with patch(
        "custom_components.slxchargingcontroller.slxtripplanner.SLXTripPlanner._get_historical_odometer",
        return_value=[
            (datetime.fromisoformat("2024-01-18 19:54:41.482455+00:00"), 2345.6),
            (datetime.fromisoformat("2024-01-19 21:54:41.482455+00:00"), 2445.6),
        ],
    ) as historical_odometer:
        tripplanner = SLXTripPlanner(hass)
        await tripplanner.initialize(ODOMETER_ENTITY_NAME)
        await tripplanner.capture_odometer()
        historical_odometer.assert_called_once_with(ODOMETER_DAYS_BACK)


async def test_tripplanner_merge_storage_and_historical(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    data_for_write = {ODOMETER_ENTITY_NAME: odometer_list_storage}
    store = storage.Store(hass, 1, ODOMETER_STORAGE_KEY)
    await store.async_save(data_for_write)

    tripplanner = SLXTripPlanner(hass)
    await tripplanner.initialize(ODOMETER_ENTITY_NAME)

    with patch(
        "custom_components.slxchargingcontroller.slxtripplanner.SLXTripPlanner._get_historical_odometer",
        return_value=odometer_list_entity,
    ) as historical_odometer:
        freezer.move_to(odometer_test_time)
        await tripplanner.capture_odometer()
        historical_odometer.assert_called_once_with(
            3
        )  # diff between  odometer_test_time and last entry is 2 full days but we are checking one day extra
        list_odo = tripplanner.odometer_list
        assert len(list_odo) == 8
