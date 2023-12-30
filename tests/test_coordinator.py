"""Test the for the SLXChargingController coordinator."""

from . import FIXTURE_CONFIG_ENTRY
from homeassistant.core import HomeAssistant
from custom_components.slxchargingcontroller.chargingmanager import SlxEnergyTracker
from custom_components.slxchargingcontroller.const import CONF_CAR_SOC_LEVEL
from custom_components.slxchargingcontroller.slxcar import SLXCar
from custom_components.slxchargingcontroller.coordinator import (
    SLXChgCtrlUpdateCoordinator,
)
import homeassistant.util.dt as dt_util
from time import sleep
from datetime import datetime, timedelta
from freezegun import freeze_time
import logging
from unittest.mock import patch


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

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 4
    # coordinator = hass.data[config_entry.domain][config_entry.entry_id]
    # assert coordinator.data is not None


async def test_coordinator_data(hass: HomeAssistant) -> None:
    config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator: SLXChgCtrlUpdateCoordinator = hass.data[config_entry.domain][
        config_entry.unique_id
    ]
    _LOGGER.info(coordinator.car_config)
    _LOGGER.info(coordinator)
    assert coordinator is not None

    coordinator.charging_manager.plug_connected()
    coordinator.charging_manager.add_charger_energy(1)
    _LOGGER.info(coordinator.charging_manager._car_connected_status)

    entity_name: str = FIXTURE_CONFIG_ENTRY["options"][CONF_CAR_SOC_LEVEL]
    entity_value: str = "13"
    _LOGGER.info("Entity name: %s", entity_name)
    await hass.async_add_executor_job(
        hass.states.set,
        entity_name,
        entity_value,
        {},
    )
    await hass.async_block_till_done()
    _LOGGER.info(coordinator.charging_manager._attr_bat_soc_estimated)
    assert coordinator.charging_manager._attr_bat_soc_estimated == 13
