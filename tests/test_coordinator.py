"""Test the for the SLXChargingController coordinator."""

from . import FIXTURE_CONFIG_ENTRY
from homeassistant.core import HomeAssistant
from custom_components.slxchargingcontroller.chargingmanager import (
    SlxEnergyTracker,
    CarConnectedStates,
)
from custom_components.slxchargingcontroller.const import CONF_CAR_SOC_LEVEL
from custom_components.slxchargingcontroller.slxcar import SLXCar
from custom_components.slxchargingcontroller.coordinator import (
    SLXChgCtrlUpdateCoordinator,
)

from custom_components.slxchargingcontroller.const import CONF_EVSE_SESSION_ENERGY
import homeassistant.util.dt as dt_util
from datetime import datetime, timedelta
from freezegun.api import FrozenDateTimeFactory

import logging
from unittest.mock import patch

import pytest


from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN


## TODO  - to fix - this is ugly workaround for including modules from core/tests. Probably could be solved by the propper configuration file.
import sys

sys.path.append("/workspaces/core/tests")

from common import async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


# TODO - move coordinator creation as fixure. Check if it's possible to customize fixure.


async def test_hass_exists(hass: HomeAssistant) -> None:
    await hass.async_block_till_done()
    assert hass is not None


async def test_create_coordinator(hass: HomeAssistant) -> None:
    config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 4


async def test_connect_and_soc_entity(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
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


async def test_coordinator_soc_timeout(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
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

    soc_timeout = coordinator.car_config[SLXCar.CONF_SOC_REQUEST_TIMEOUT]

    coordinator.charging_manager.plug_connected()
    coordinator.charging_manager.add_charger_energy(1)
    _LOGGER.info(coordinator.charging_manager._car_connected_status)
    assert (
        coordinator.charging_manager._car_connected_status
        == CarConnectedStates.ramping_up
    )

    freezer.tick(timedelta(seconds=(soc_timeout + 2)))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        coordinator.charging_manager._car_connected_status
        == CarConnectedStates.autopilot
    )


async def test_create_coordinator_fixture(
    hass: HomeAssistant, coordinator_factory
) -> None:
    coordinator_instance: SLXChgCtrlUpdateCoordinator = await coordinator_factory
    assert coordinator_instance.charging_manager is not None
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 4
    assert coordinator_instance.evse._session_energy_name == "evsetest.energy"


# this is how I can overwrite the default configuration settings
@pytest.mark.fixt_data({CONF_EVSE_SESSION_ENERGY: "point_evse"})
async def test_alternative_fixture(hass: HomeAssistant, coordinator_factory) -> None:
    coordinator_instance: SLXChgCtrlUpdateCoordinator = await coordinator_factory
    assert coordinator_instance.charging_manager is not None
    assert coordinator_instance.evse._session_energy_name == "point_evse"
