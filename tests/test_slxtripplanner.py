"""Test the for the SLXChargingController coordinator."""

from . import FIXTURE_CONFIG_ENTRY
from homeassistant.core import HomeAssistant
from custom_components.slxchargingcontroller.slxtripplanner import (
    SLXTripPlanner,
    ODOMETER_STORAGE_KEY,
)
from homeassistant.helpers import storage

import homeassistant.util.dt as dt_util
from datetime import datetime, timedelta
from freezegun.api import FrozenDateTimeFactory

import logging
from unittest.mock import patch

import pytest


from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_tripplanner_storage_read(hass: HomeAssistant) -> None:
    ODOMETER_ENTITY_NAME = "odometer_entity_test"

    odometer_list: list[datetime, float] = []
    odometer_list.append(
        (datetime.fromisoformat("2024-01-17 18:54:41.482455+00:00"), 1234.5)
    )
    odometer_list.append(
        (datetime.fromisoformat("2024-01-18 19:54:41.482455+00:00"), 2345.6)
    )

    data_for_write = {ODOMETER_ENTITY_NAME: odometer_list}
    store = storage.Store(hass, 1, ODOMETER_STORAGE_KEY)
    await store.async_save(data_for_write)

    tripplanner = SLXTripPlanner(hass)
    await tripplanner.initialize(ODOMETER_ENTITY_NAME)
    await tripplanner.read_storage()
    list_odo = tripplanner.odometer_list
    assert len(list_odo) == 2
    assert list_odo[1][1] == 2345.6
