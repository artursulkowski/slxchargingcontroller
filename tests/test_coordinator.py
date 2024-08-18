"""Test the for the SLXChargingController coordinator."""

from custom_components.slxchargingcontroller.tests import FIXTURE_CONFIG_ENTRY
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

from custom_components.slxchargingcontroller.const import (
    CONF_EVSE_SESSION_ENERGY,
    CONF_EVSE_PLUG_CONNECTED,
    CHR_MODE_NORMAL,
)
import homeassistant.util.dt as dt_util
from datetime import datetime, timedelta
from freezegun.api import FrozenDateTimeFactory

import logging
from unittest.mock import patch

import pytest


from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

from tests.common import async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


async def test_hass_exists(hass: HomeAssistant) -> None:
    await hass.async_block_till_done()
    assert hass is not None


async def test_create_coordinator(hass: HomeAssistant, coordinator_factory) -> None:
    coordinator: SLXChgCtrlUpdateCoordinator = await coordinator_factory
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 4


async def test_connect_and_soc_entity(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, coordinator_factory
) -> None:
    coordinator: SLXChgCtrlUpdateCoordinator = await coordinator_factory
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
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, coordinator_factory
) -> None:
    coordinator: SLXChgCtrlUpdateCoordinator = await coordinator_factory
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


# scenarios to be tested in coordinator.
# Functional tests
# - requesting soc update and correctly handling it's retry, timeout
# -

# Group 1 - car with SOC read immediatelly (no soc update defined)
# do we ge soc request after plug-in.
# immediatelly soc estimate after reading soc energy (no delay)
# are we getting re-try of soc request if it was not provided within timeout
#


async def helper_set_entity_value(
    hass: HomeAssistant, entity_name: str, entity_value: str
):
    await hass.async_add_executor_job(
        hass.states.set,
        entity_name,
        entity_value,
        {},
    )


async def test_soc_request_after_plugged(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, coordinator_factory
) -> None:
    """Tests if car is asked for SOC update after plug is being connected"""
    coordinator: SLXChgCtrlUpdateCoordinator = await coordinator_factory
    _LOGGER.info(coordinator.car_config)
    _LOGGER.info(coordinator)
    assert coordinator is not None
    # soc_timeout = coordinator.car_config[SLXCar.CONF_SOC_REQUEST_TIMEOUT]

    with patch(
        "custom_components.slxchargingcontroller.slxcarmanual.SLXCarManual.request_soc_update",
        return_value=True,
    ) as car_mock:
        entity_name_evse_plug: str = FIXTURE_CONFIG_ENTRY["options"][
            CONF_EVSE_PLUG_CONNECTED
        ]
        await helper_set_entity_value(hass, entity_name_evse_plug, "on")

        assert (
            coordinator.charging_manager._car_connected_status
            == CarConnectedStates.ramping_up
        )
        assert len(car_mock.mock_calls) == 1


async def test_no_soc_request_after_plugged(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, coordinator_factory, caplog
) -> None:
    """Tests if car is not asked for SOC update after plug is being connected - when SOC is "fresh" enough"""

    coordinator: SLXChgCtrlUpdateCoordinator = await coordinator_factory
    # caplog.set_level(logging.debug)
    _LOGGER.info(coordinator.car_config)
    _LOGGER.info(coordinator)
    assert coordinator is not None
    soc_before_energy = coordinator.car_config[SLXCar.CONF_SOC_BEFORE_ENERGY]

    # Set SOC
    entity_name_soc: str = FIXTURE_CONFIG_ENTRY["options"][CONF_CAR_SOC_LEVEL]
    await helper_set_entity_value(hass, entity_name_soc, "30")

    freezer.tick(timedelta(seconds=(soc_before_energy - 10)))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        coordinator.charging_manager._attr_bat_soc_estimated is None
    ), "before energy was passed from the charged (and plug is connected), estimated soc should still be unknown"

    entity_name_evse_energy: str = FIXTURE_CONFIG_ENTRY["options"][
        CONF_EVSE_SESSION_ENERGY
    ]
    _LOGGER.warning(entity_name_evse_energy)
    await helper_set_entity_value(hass, entity_name_evse_energy, "1")

    with patch(
        "custom_components.slxchargingcontroller.slxcarmanual.SLXCarManual.request_soc_update",
        return_value=True,
    ) as car_mock:
        entity_name_evse_plug: str = FIXTURE_CONFIG_ENTRY["options"][
            CONF_EVSE_PLUG_CONNECTED
        ]

        assert (
            coordinator.charging_manager._car_connected_status is None
        ), "before connecting the plug, status should still be None"

        assert (
            coordinator.charging_manager._attr_bat_soc_estimated is None
        ), "before connecting plug, estimated soc should still be unknown"

        await helper_set_entity_value(hass, entity_name_evse_plug, "on")

        assert (
            coordinator.charging_manager._car_connected_status
            == CarConnectedStates.soc_known
        )

        assert len(car_mock.mock_calls) == 0

        assert coordinator.charging_manager._attr_bat_soc_estimated == 30

        ##TODO - check that SOC is requested after initial value expires.. (timer_next_soc_request)
        # SLXCar.CONF_SOC_NEXT_UPDATE
        soc_refresh_time = coordinator.car_config[SLXCar.CONF_SOC_NEXT_UPDATE]
        freezer.tick(timedelta(seconds=(soc_refresh_time)))
        async_fire_time_changed(hass)
        assert len(car_mock.mock_calls) == 1


# https://github.com/artursulkowski/slxchargingcontroller/issues/32
async def test_requested_soc_timeouted(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, coordinator_factory
) -> None:
    """Test scenario - connected plug, SOC is requested but it timeouts, we should get retry and charger should switch to normal charging (autopilot mode)"""
    coordinator: SLXChgCtrlUpdateCoordinator = await coordinator_factory
    _LOGGER.info(coordinator.car_config)
    _LOGGER.info(coordinator)
    assert coordinator is not None
    soc_timeout = coordinator.car_config[SLXCar.CONF_SOC_REQUEST_TIMEOUT]

    with (
        patch(
            "custom_components.slxchargingcontroller.slxcarmanual.SLXCarManual.request_soc_update",
            return_value=True,
        ) as car_mock,
        patch(
            "custom_components.slxchargingcontroller.slxevsemanual.SLXManualEvse.set_charger_mode"
        ) as evse_mock,
    ):
        entity_name_evse_plug: str = FIXTURE_CONFIG_ENTRY["options"][
            CONF_EVSE_PLUG_CONNECTED
        ]
        await helper_set_entity_value(hass, entity_name_evse_plug, "on")

        assert (
            coordinator.charging_manager._car_connected_status
            == CarConnectedStates.ramping_up
        )
        assert len(car_mock.mock_calls) == 1, "First request for SOC"
        freezer.tick(timedelta(seconds=(soc_timeout + 2)))
        async_fire_time_changed(hass)

        assert (
            coordinator.charging_manager._car_connected_status
            == CarConnectedStates.autopilot
        ), "After SOC timeout we should switch to autopilot mode"

        evse_mock.assert_called_with(CHR_MODE_NORMAL)


# https://github.com/artursulkowski/slxchargingcontroller/issues/29
async def test_estimated_soc_cleared_after_unplug(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, coordinator_factory, caplog
) -> None:
    """Check that estimated soc is cleared after unplug"""

    coordinator: SLXChgCtrlUpdateCoordinator = await coordinator_factory

    assert coordinator is not None
    soc_before_energy = coordinator.car_config[SLXCar.CONF_SOC_BEFORE_ENERGY]
    #
    # Set SOC
    entity_name_soc: str = FIXTURE_CONFIG_ENTRY["options"][CONF_CAR_SOC_LEVEL]
    await helper_set_entity_value(hass, entity_name_soc, "30")

    assert (
        coordinator.charging_manager._attr_bat_soc_estimated is None
    ), "before energy was passed from the charged (and plug is connected), estimated soc should still be unknown"

    entity_name_evse_energy: str = FIXTURE_CONFIG_ENTRY["options"][
        CONF_EVSE_SESSION_ENERGY
    ]
    _LOGGER.warning(entity_name_evse_energy)
    await helper_set_entity_value(hass, entity_name_evse_energy, "1")

    entity_name_evse_plug: str = FIXTURE_CONFIG_ENTRY["options"][
        CONF_EVSE_PLUG_CONNECTED
    ]
    await helper_set_entity_value(hass, entity_name_evse_plug, "on")

    await hass.async_block_till_done()
    assert coordinator.charging_manager._attr_bat_soc_estimated == 30

    await helper_set_entity_value(hass, entity_name_evse_plug, "off")
    await hass.async_block_till_done()
    assert coordinator.charging_manager._attr_bat_soc_estimated is None


async def test__template(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, coordinator_factory
) -> None:
    coordinator: SLXChgCtrlUpdateCoordinator = await coordinator_factory


## TODO - for some reason this fixt_data is remaining as active impacting any further tests. As workaround temporary moved as the last test.


# this is how I can overwrite the default configuration settings
@pytest.mark.fixt_data({CONF_EVSE_SESSION_ENERGY: "point_evse"})
async def test_alternative_fixture(hass: HomeAssistant, coordinator_factory) -> None:
    coordinator_instance: SLXChgCtrlUpdateCoordinator = await coordinator_factory
    assert coordinator_instance.charging_manager is not None
    assert coordinator_instance.evse._session_energy_name == "point_evse"
