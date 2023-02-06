""" module for coordinator"""

from __future__ import annotations

from datetime import timedelta

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_SCAN_INTERVAL,
)

from homeassistant.core import (
    HomeAssistant,
    CALLBACK_TYPE,
    Event,
    HassJob,
    HomeAssistant,
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

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers import entity_registry
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(__name__)


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

        # variables to store enities numbers.
        self.ent_soc_min: int = 20
        self.ent_soc_max: int = 80

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

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=self.scan_interval),
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

    #

    @callback
    def callback_charger_session_energy(self, event: Event) -> None:
        """Handle child updates."""
        _LOGGER.warning("Charger session energy changed")
        _LOGGER.debug(event)

    @callback
    def callback_charger_plug_connected(self, event: Event) -> None:
        """Handle child updates."""
        _LOGGER.warning("Charger plug connected")
        _LOGGER.debug(event)

    @callback
    def callback_soc_level(self, event: Event) -> None:
        """Handle child updates."""
        _LOGGER.warning("SOC level changed")
        _LOGGER.debug(event)
        # In case I need to unsubscribe - I can call it:
        # self.unsub_soc_level()

    @callback
    def callback_soc_update(self, event: Event) -> None:
        """Handle child updates."""
        _LOGGER.warning("SOC update time changed")
        _LOGGER.debug(event)


class SLXChargingManager:
    def __init__(self, hass: HomeAssistant, logger):
        self.hass = hass
        self.logger = logger


#      _ev_driving_range: float = None
# def ev_driving_range(self):
#     return self._ev_driving_range

# @ev_driving_range.setter
# def ev_driving_range(self, value):
#     self._ev_driving_range_value = value[0]
#     self._ev_driving_range_unit = value[1]
#     self._ev_driving_range = value[0]
