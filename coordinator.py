"""module for coordinator"""

from __future__ import annotations

from datetime import timedelta, datetime

import logging
import asyncio

from typing import Any
from homeassistant.config_entries import ConfigEntry

from homeassistant.const import (
    CONF_SCAN_INTERVAL,
)

from homeassistant.core import (
    HomeAssistant,
    CALLBACK_TYPE,
    Event,
    HassJob,
    State,
    callback,
)

from .const import (
    DEFAULT_SCAN_INTERVAL,
    CONF_CHARGER_TYPE,
    CONF_EVSE_SESSION_ENERGY,
    CONF_EVSE_PLUG_CONNECTED,
    CONF_CAR_TYPE,
    CONF_CAR_SOC_LEVEL,
    CONF_CAR_SOC_UPDATE_TIME,
    CONF_BATTERY_CAPACITY,
    DOMAIN,
    ENT_CHARGE_MODE,
    ENT_CHARGE_METHOD,
    CHR_MODE_UNKNOWN,
    CHR_METHOD_ECO,
    CHR_METHOD_MANUAL,
    ENT_SOC_LIMIT_MIN,
    ENT_SOC_LIMIT_MAX,
    ENT_SOC_TARGET,
    CHARGER_MODES,
)

from .chargingmanager import SLXChargingManager
from .timer import SlxTimer
from .slxopenevse import SLXOpenEvse
from .slxevsemanual import SLXManualEvse
from .slxcar import SLXCar
from .slxkiahyundai import SLXKiaHyundai
from .slxbmw import SLXBmw
from .slxcarmanual import SLXCarManual
from .slxtripplanner import SLXTripPlanner

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers import entity_registry
from homeassistant.helpers.event import async_track_state_change_event

import homeassistant.util.dt as dt_util


_LOGGER = logging.getLogger(__name__)


class SLXChgCtrlUpdateCoordinator(DataUpdateCoordinator):
    """Main class storing state and refresing it"""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )

    async def initialize(self, config_entry: ConfigEntry) -> None:
        self.platforms: set[str] = set()

        # currenlty CONF_SCAN_INTERVAL is not set in configuration flow.
        self.scan_interval: int = (
            config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL) * 60
        )

        # First setup a car - as we will need a configuration from the car!

        ### Connect to Car integration
        self._received_soc_level: float = None
        self._received_soc_update: datetime = None
        self._delay_soc_update: bool = False

        car_created: bool = False
        car_config = config_entry.options.get(CONF_CAR_TYPE, "")
        self.car = None
        car_created = self.create_auto_car(car_config)

        self.car_config = None

        # TODO - move to self.create_manual_car
        if car_created is False:
            # we try manual update
            # there is a nicer way to do it (some factory with additional config options?)
            current_soc_level = config_entry.options.get(CONF_CAR_SOC_LEVEL, "")
            current_soc_update = config_entry.options.get(
                CONF_CAR_SOC_UPDATE_TIME, None
            )
            if current_soc_level != "":
                self.car = SLXCarManual(self.hass)
                car_created = self.car.connect(
                    self.callback_soc_level,
                    current_soc_level,
                    self.callback_soc_update,
                    current_soc_update,
                )
                if current_soc_update is not None:
                    # that's unusual as we are storing config back to car object
                    self.car.dynamic_config[SLXCar.CONF_SOC_UPDATE_REQUIRED] = True
                else:
                    self.car.dynamic_config[SLXCar.CONF_SOC_UPDATE_REQUIRED] = False

        if car_created is True:
            self.car_config: dict[str, Any] = self.car.dynamic_config
            self._delay_soc_update = self.car_config[SLXCar.CONF_SOC_UPDATE_REQUIRED]

        self._timer_read_soc = None
        timer_read_soc = self.car.dynamic_config[SLXCar.CONF_SOC_READING_DELAY]
        if timer_read_soc > 0 and self._delay_soc_update is True:
            self._timer_read_soc = SlxTimer(
                self.hass,
                timedelta(seconds=timer_read_soc),
                self.callback_soc_delayed,
            )

        self._timer_soc_update_retry = None
        soc_update_retry_time = self.car.dynamic_config[SLXCar.CONF_SOC_UPDATE_RETRY]
        if soc_update_retry_time > 0:
            self._timer_soc_update_retry = SlxTimer(
                self.hass,
                timedelta(seconds=soc_update_retry_time),
                self.callback_soc_requested_retry,
            )

        # Setup charging manager

        self.charging_manager = SLXChargingManager(self.hass, self.car_config)
        self.charging_manager.set_energy_estimated_callback(
            self.callback_energy_estimated
        )
        self.charging_manager.set_soc_requested_callback(self.callback_soc_requested)
        self.charging_manager.set_charger_mode_callback(self.callback_charger_mode)

        bat_capacity = config_entry.options.get(CONF_BATTERY_CAPACITY, 10)
        self.charging_manager.battery_capacity = bat_capacity

        ### Connect to EVSE
        self.evse = None
        charger_config = config_entry.options.get(CONF_CHARGER_TYPE, "")
        evse_configured: bool = self.create_auto_evse(charger_config)

        # TODO add checking if OpenEVSE was in fact setup through configuration

        if evse_configured is False:
            evse_configured = self.create_manual_evse(config_entry)
        ################### Continue configuration

        # I need to initialize data after parent class.
        # If not done at that order parent's init will overwrite self.data
        self.data: dict[str, Any] = {}
        self.data[ENT_CHARGE_MODE] = CHR_MODE_UNKNOWN
        self.data[ENT_CHARGE_METHOD] = CHR_METHOD_ECO
        self.data[ENT_SOC_LIMIT_MIN] = float(20)
        self.data[ENT_SOC_LIMIT_MAX] = float(80)
        # We are setting up target SOC same as minimum. Of course planner can and will override it.
        self.data[ENT_SOC_TARGET] = self.data[ENT_SOC_LIMIT_MIN]

        self.charging_manager.soc_minimum = self.data[ENT_SOC_LIMIT_MIN]
        self.charging_manager.soc_maximum = self.data[ENT_SOC_LIMIT_MAX]
        self.charging_manager.target_soc = self.data[ENT_SOC_TARGET]
        self.charging_manager.charge_method = self.data[ENT_CHARGE_METHOD]

        odometer_entity = self.car.odometer_entity()
        self.trip_planner = SLXTripPlanner(self.hass)

        if odometer_entity is not None:
            await self.trip_planner.initialize(odometer_entity)

    def cleanup(self):
        if self.charging_manager is not None:
            self.charging_manager.cleanup()

    def create_auto_evse(self, configuration: str) -> bool:
        if configuration == "manual":
            return False

        conf_list: list[str] = configuration.split(".")
        if len(conf_list) != 2:
            _LOGGER.error("Invalid syntax of evse Config: %s", configuration)
            return True

        if conf_list[0] != "openevse":
            _LOGGER.error(
                "Only OpenEVSE devices are supported. Config: %s", configuration
            )
            return True

        device_id = conf_list[1]

        # double check if OpenEVSE with that deviceID exists
        if SLXOpenEvse.check_all_entities(self.hass, device_id) is True:
            self.evse = SLXOpenEvse(
                self.hass,
            )
            return self.evse.connect(
                cb_sessionenergy=self.callback_charger_session_energy,
                cb_plug=self.callback_charger_plug_connected,
                device_id=device_id,
            )
        else:
            _LOGGER.error(
                "Error initializing OpenEVSE, proper device isn't found. Config: %s",
                configuration,
            )
            # we return True as still OpenEVSE shall be created and we should not use Manual configuration.
            return True

        return True

    def create_manual_evse(self, config_entry: ConfigEntry) -> bool:
        current_evse_energy = config_entry.options.get(CONF_EVSE_SESSION_ENERGY, "")
        current_evse_plug_connected = config_entry.options.get(
            CONF_EVSE_PLUG_CONNECTED, ""
        )

        if current_evse_energy == "" or current_evse_plug_connected == "":
            return False

        _LOGGER.info(
            "Creating manual EVSE with entities: session= %s, plug = %s",
            current_evse_energy,
            current_evse_plug_connected,
        )
        self.evse = SLXManualEvse(self.hass)
        successful_connect = self.evse.connect(
            self.callback_charger_session_energy,
            current_evse_energy,
            self.callback_charger_plug_connected,
            current_evse_plug_connected,
        )
        return successful_connect

    def create_auto_car(self, configuration: str) -> bool:
        if configuration == "manual":
            return False

        conf_list: list[str] = configuration.split(".")
        if len(conf_list) != 2:
            _LOGGER.error("Invalid syntax of car Config: %s", configuration)
            return True

        integration_name = conf_list[0]
        device_id = conf_list[1]

        tmp_car = None

        match integration_name:
            case "kia_hyundai":
                tmp_car = SLXKiaHyundai(self.hass)
            case "bmw":
                tmp_car = SLXBmw(self.hass)

        if tmp_car is None:
            _LOGGER.error(
                "Unsupported type of Car Integration. Config: %s", configuration
            )
            return True

        if (
            tmp_car.connect(
                self.callback_soc_level, self.callback_soc_update, device_id
            )
            is False
        ):
            _LOGGER.error(
                "Error at connecting car's integration. Config: %s", configuration
            )
            return True
        else:
            self.car = tmp_car
        return True

    async def _async_update_data(self):
        """Update data via library. Called by update_coordinator periodically."""
        _LOGGER.debug("Update function called periodically - can add some updates here")

    async def set_soc_min(self, value: float):
        # self.ent_soc_min = value
        _LOGGER.info("User set entity value, soc_min = %.1f", value)
        self.data[ENT_SOC_LIMIT_MIN] = value
        self.charging_manager.soc_minimum = value

    async def set_soc_max(self, value: float):
        _LOGGER.info("User set entity value, soc_max = %.1f", value)
        self.data[ENT_SOC_LIMIT_MAX] = value
        self.charging_manager.soc_maximum = value

    async def set_soc_target(self, value: float):
        _LOGGER.info("User set entity value, soc_target = %.1f", value)
        self.data[ENT_SOC_TARGET] = value
        self.charging_manager.target_soc = value

    async def set_charger_select(self, value: str):
        _LOGGER.info("User changed charger_select to %s", value)
        if self.data[ENT_CHARGE_METHOD] != CHR_METHOD_MANUAL:
            _LOGGER.warning(
                "It is not possible to control charger is method is not set to MANUAL"
            )
            self.async_set_updated_data(self.data)
            return
        self.async_charger_select(value)

    def async_charger_select(self, value: str):
        self.data[ENT_CHARGE_MODE] = value
        if self.evse is not None:
            self.evse.set_charger_mode(value)
            _LOGGER.info("Setting charger mode to %s", value)
        else:
            _LOGGER.error(
                "There is no charger to control (tried chang value to %s)", value
            )

    async def set_charge_method(self, value: str):
        _LOGGER.info("User changed charging method to %s", value)
        self.data[ENT_CHARGE_METHOD] = value
        self.charging_manager.charge_method = value

    @staticmethod
    def extract_energy_entity(event_new_state) -> float:
        """Translates state with energy into kWh"""
        try:
            value = float(event_new_state.state)
        except ValueError:
            value = None
        try:
            unit = event_new_state.attributes["unit_of_measurement"]
        except Exception:  # pylint: disable=broad-except
            unit = None
        if value is not None and unit is not None:
            if unit == "Wh":
                value = value / 1000
        return value

    @staticmethod
    def extract_bool_state(event_new_state) -> bool:
        try:
            state_text = event_new_state.state
            d = {"off": False, "on": True}
            if state_text in d:
                value = d[state_text]
            else:
                value = None
        except Exception:  # pylint: disable=broad-except
            value = None
        return value

    @callback
    def callback_energy_estimated(self, energy: float) -> None:
        """Callback used to inform that new battery energy is estimated"""
        # Passed data is not used - so pass just a useless string
        self.async_set_updated_data(self.data)

    @callback
    def callback_soc_requested(self, request_counter: int = -1) -> None:
        _LOGGER.info("SOC Request number %d", request_counter)
        # TODO - now it is just hardcoded service. Later it should be set by configuration

        if self.car is not None:
            if self.car.request_soc_update() is False:
                _LOGGER.warning("SOC Update service not found")
                if request_counter != -1:
                    _LOGGER.info("Schedule retry of SOC update")
                    self._timer_soc_update_retry.schedule_timer()
        else:
            _LOGGER.warning(
                "Get request for SocUpdate but car's integration isn't setup"
            )

    # TODO workaround because SLXTimer is passing DateTime as parametrs - this should be made more elegant
    @callback
    def callback_soc_requested_retry(self, _) -> None:
        self.callback_soc_requested()

    @callback
    def callback_charger_mode(self, charger_mode: str) -> None:
        _LOGGER.info("Callback for changing charger mode to %s", charger_mode)
        if self.data[ENT_CHARGE_METHOD] == CHR_METHOD_MANUAL:
            _LOGGER.warning(
                "Ignoring request to change charge mode to %s as manual charing method is selected",
                charger_mode,
            )
            return
        if self.evse is None:
            _LOGGER.error("Cannor handled charger mode change. OpenEVSE isn't setup")
            return

        if charger_mode in CHARGER_MODES:
            self.async_charger_select(charger_mode)
            self.async_set_updated_data(self.data)

    @callback
    def callback_charger_session_energy(self, event: Event) -> None:
        value = self.extract_energy_entity(event.data["new_state"])
        _LOGGER.info("Callback - charger session energy changed %.3f", value)
        self.charging_manager.add_charger_energy(value, event.time_fired)

    @callback
    def callback_charger_plug_connected(self, event: Event) -> None:
        value = self.extract_bool_state(event.data["new_state"])
        _LOGGER.info("Callback - charger plug connected %s", value)
        if value is True:
            # Try to get session energy at the moment when plug is connected.
            evse_energy: float = None
            if self.evse is not None:
                evse_energy = self.evse.get_session_energy()
            self.charging_manager.plug_connected(evse_energy)
        else:
            self.charging_manager.plug_disconnected()

    @callback
    def callback_soc_level(self, event: Event) -> None:
        try:
            value = float(event.data["new_state"].state)
        except ValueError:
            value = None

        self._received_soc_level = value
        if self._delay_soc_update is False:
            _LOGGER.info(
                "Callback - soc level changed %d, charging managed updated", value
            )
            self.charging_manager.set_soc_level(value)
        else:
            _LOGGER.info("Callback - soc level changed %d, delayed update", value)

    @callback
    def callback_soc_update(self, event: Event) -> None:
        """Handle SOC updated time"""
        try:
            state_value = event.data["new_state"].state
            _LOGGER.debug("SOC Update - state raw value: %s", state_value)
            value = dt_util.as_utc(dt_util.parse_datetime(state_value))
            # value = datetime.fromisoformat(state_value)
        except (ValueError, AttributeError):
            value = None

        if value is None:
            _LOGGER.warning(
                "Callback soc update time, cannot parse the time %s", state_value
            )
            return
        else:
            _LOGGER.info("Callback soc update time %s", value)

        if self._received_soc_update is not None:
            if value < self._received_soc_update:
                _LOGGER.warning("Igore soc update time which is moving backwards")
                return

        self._received_soc_update = value
        if self._delay_soc_update:
            _LOGGER.debug("Soc update - schedule timer for handling delayed update")
            self._timer_read_soc.schedule_timer()

    @callback
    def callback_soc_delayed(self, _) -> None:
        _LOGGER.info("Callback for delayed soc update time")
        # Check if we have both values correct
        if self._received_soc_level is None:
            return
        if self._received_soc_update is None:
            return

        _LOGGER.debug(
            "Passing SOC information, level %d , time %s",
            self._received_soc_level,
            self._received_soc_update,
        )

        self.charging_manager.set_soc_level(
            self._received_soc_level, self._received_soc_update
        )
