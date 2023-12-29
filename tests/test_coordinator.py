"""Test the for the SLXChargingController coordinator."""

from . import FIXTURE_CONFIG_ENTRY
from homeassistant.core import HomeAssistant
from custom_components.slxchargingcontroller.chargingmanager import SlxEnergyTracker
import homeassistant.util.dt as dt_util
from time import sleep
from datetime import datetime, timedelta
from freezegun import freeze_time
import logging

from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN


_LOGGER = logging.getLogger(__name__)


async def test_hass_exists(hass: HomeAssistant) -> None:
    await hass.async_block_till_done()
    assert hass is not None


async def test_create_coordinator(hass: HomeAssistant) -> None:
    config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 20
    # coordinator = hass.data[config_entry.domain][config_entry.entry_id]
    # assert coordinator.data is not None
