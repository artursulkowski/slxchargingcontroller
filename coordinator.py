""" module for coordinator"""

from __future__ import annotations

from datetime import timedelta, datetime

import logging
import asyncio

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
    CONF_CHARGE_TARGET,
    DEFAULT_CHARGE_TARGET,
    DEFAULT_SCAN_INTERVAL,
    CONF_EVSE_SESSION_ENERGY,
    CONF_EVSE_PLUG_CONNECTED,
    CONF_CAR_SOC_LEVEL,
    CONF_CAR_SOC_UPDATE_TIME,
    CONF_BATTERY_CAPACITY,
    DOMAIN,
)

from .chargingmanager import SLXChargingManager, SlxTimer
from .slxopenevse import SLXOpenEVSE

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers import entity_registry
from homeassistant.helpers.event import async_track_state_change_event

import homeassistant.util.dt as dt_util


_LOGGER = logging.getLogger(__name__)

DELAYED_SOC_READING: int = 5  # seconds


class SLXChgCtrlUpdateCoordinator(DataUpdateCoordinator):
    """Main class storing state and refresing it"""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.platforms: set[str] = set()
        self.scan_interval: int = (
            config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL) * 60
        )
        self.target_charge: int = config_entry.options.get(
            CONF_CHARGE_TARGET, DEFAULT_CHARGE_TARGET
        )

        #
        self.charging_manager = SLXChargingManager(hass, _LOGGER)
        self.charging_manager.set_energy_estimated_callback(
            self.callback_energy_estimated
        )
        self.charging_manager.set_soc_requested_callback(self.callback_soc_requested)

        bat_capacity = config_entry.options.get(CONF_BATTERY_CAPACITY, 10)
        self.charging_manager.battery_capacity = bat_capacity
        # variables to store enities numbers.
        self.ent_soc_min: int = 20
        self.ent_soc_max: int = 80
        self.ent_charger_select: str = ""

        openevse = None

        openevse = SLXOpenEVSE(
            hass,
            cb_sessionenergy=self.callback_charger_session_energy,
            cb_plug=self.callback_charger_plug_connected,
        )

        # TODO add checking if OpenEVSE was in fact setup through configuration

        if openevse is None:
            self.unsub_openevse_session_energy = None
            current_evse_energy = config_entry.options.get(CONF_EVSE_SESSION_ENERGY, "")
            if current_evse_energy != "":
                _LOGGER.warning("Subscribing to")
                _LOGGER.warning(current_evse_energy)
                self.unsub_openevse_session_energy = async_track_state_change_event(
                    hass,
                    current_evse_energy,
                    self.callback_charger_session_energy,
                )

            self.unsub_openevse_plug_connected = None
            current_evse_plug_connected = config_entry.options.get(
                CONF_EVSE_PLUG_CONNECTED, ""
            )
            if current_evse_plug_connected != "":
                _LOGGER.warning("Subscribing to")
                _LOGGER.warning(current_evse_plug_connected)
                self.unsub_openevse_plug_connected = async_track_state_change_event(
                    hass,
                    current_evse_plug_connected,
                    self.callback_charger_plug_connected,
                )
        self._received_soc_level: float = None
        self._received_soc_update: datetime = None

        self.unsub_soc_level = None
        current_soc_level = config_entry.options.get(CONF_CAR_SOC_LEVEL, "")
        if current_soc_level != "":
            _LOGGER.warning("Subscribing to")
            _LOGGER.warning(current_soc_level)
            self.unsub_soc_level = async_track_state_change_event(
                hass,
                current_soc_level,
                self.callback_soc_level,
            )

        self.unsub_soc_update = None
        current_soc_update = config_entry.options.get(CONF_CAR_SOC_UPDATE_TIME, "")
        if current_soc_update != "":
            _LOGGER.warning("Subscribing to")
            _LOGGER.warning(current_soc_update)
            self.unsub_soc_update = async_track_state_change_event(
                hass,
                current_soc_update,
                self.callback_soc_update,
            )

        self._delay_soc_update: bool = False
        if self.unsub_soc_update is not None and self.unsub_soc_level is not None:
            self._delay_soc_update = True

        self._timer_read_soc = SlxTimer(
            hass,
            _LOGGER,
            timedelta(seconds=DELAYED_SOC_READING),
            self.callback_soc_delayed,
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # disable
            # update_interval=timedelta(seconds=self.scan_interval),
        )

    async def _async_update_data(self):
        """Update data via library. Called by update_coordinator periodically."""
        _LOGGER.warning("Update function called periodically - to IMPLEMENT IT!")
        _LOGGER.debug(self)

    async def set_soc_min(self, value: int):
        self.ent_soc_min = value

        # NOTES - NOT ALL ENTITIES HAVE ENTRIES DEFINED!
        for state in self.hass.states.async_all():
            entity_id = state.entity_id
            _LOGGER.debug("===========")
            _LOGGER.debug(entity_id)
            _LOGGER.debug(state)
            # if ent_reg_ent := ent_reg.async_get(entity_id):
            #    _LOGGER.debug(ent_reg_ent)

        _LOGGER.debug(value)

    # async_get_entity_id ?

    async def set_soc_max(self, value: int):
        self.ent_soc_max = value
        _LOGGER.debug(value)

    async def set_charger_select(self, value: str):
        self.ent_charger_select = value
        _LOGGER.error("TADA - I CAN STEER A CHARGER: %s", value)

    #
    @staticmethod
    def extract_energy_entity(event_new_state) -> float:
        """Translates state with energy into kWh"""
        try:
            value = float(event_new_state.state)
        except ValueError:
            value = None
        try:
            unit = event_new_state.attributes["unit_of_measurement"]
        except Exception:
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
        except Exception:
            value = None
        return value

    @callback
    def callback_energy_estimated(self, energy: float) -> None:
        """Callback used to inform that new battery energy is estimated"""
        # Passed data is not used - so pass just a useless string
        self.async_set_updated_data("testdata")

    @callback
    def callback_soc_requested(self, request_counter: int) -> None:
        _LOGGER.debug("SOC Request number %d", request_counter)
        # TODO - now it is just hardcoded service. Later it should be set by configuration
        self.hass.async_add_executor_job(
            self.hass.services.call, "kia_uvo", "force_update", {}
        )

    @callback
    def callback_charger_session_energy(self, event: Event) -> None:
        """Handle child updates."""
        _LOGGER.warning("Charger session energy changed")
        _LOGGER.debug(event)
        _LOGGER.debug(event.data["new_state"])
        value = self.extract_energy_entity(event.data["new_state"])
        self.charging_manager.add_charger_energy(value, event.time_fired)

    @callback
    def callback_charger_plug_connected(self, event: Event) -> None:
        """Handle child updates."""
        _LOGGER.debug("Charger plug changed")
        value = self.extract_bool_state(event.data["new_state"])
        self.charging_manager.plug_status = value

    @callback
    def callback_soc_level(self, event: Event) -> None:
        """Handle child updates."""
        _LOGGER.warning("SOC level changed")
        _LOGGER.debug(event)

        try:
            value = float(event.data["new_state"].state)
        except ValueError:
            value = None

        self._received_soc_level = value

        if self._delay_soc_update is False:
            self.charging_manager.set_soc_level(value)

    @callback
    def callback_soc_update(self, event: Event) -> None:
        """Handle SOC updated time"""
        _LOGGER.debug("SOC update time changed")
        _LOGGER.debug(event)

        try:
            state_value = event.data["new_state"].state
            _LOGGER.debug(state_value)
            value = dt_util.as_utc(dt_util.parse_datetime(state_value))
            # value = datetime.fromisoformat(state_value)
        except ValueError:
            value = None

        if value is None:
            return
        self._received_soc_update = value
        if self._delay_soc_update:
            self._timer_read_soc.schedule_timer()

    @callback
    def callback_soc_delayed(self, _) -> None:
        _LOGGER.debug("Delayed soc reading")
        # Check if we have both values correct
        if self._received_soc_level is None:
            return
        if self._received_soc_update is None:
            return

        # call

        _LOGGER.debug(
            "Passing SOC information, level %d , time %s",
            self._received_soc_level,
            self._received_soc_update,
        )

        self.charging_manager.set_soc_level(
            self._received_soc_level, self._received_soc_update
        )
