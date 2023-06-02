""" slxmodule for connecting with OpenEVSE"""

from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers import entity_registry, device_registry
from homeassistant.helpers.entity_registry import EntityRegistry
import logging

from typing import Any
from enum import Enum

from homeassistant.core import (
    HomeAssistant,
    Event,
    Callable,
    State,
    callback,
)


# entities we subscribe to
WatchedEntities = {
    # type of value : entity_id
    "sessionenergy": "sensor.openevse_usage_this_session",
    "plug": "binary_sensor.openevse_vehicle_connected",
}

# entities we are taking value from
GetEntities = {
    "maxcurrent": "select.openevse_max_current",
    "divertactive": "binary_sensor.openevse_divert_active",
}


# entities we are setting value
SetEntities = {
    "manualoverride": "switch.openevse_manual_override",
    "divertmode": "select.openevse_divert_mode",
    "sleepmode": "switch.openevse_sleep_mode",
}

_LOGGER = logging.getLogger(__name__)


class ChargerMode(Enum):
    UNKNOWN = 0
    STOPPED = 1
    PVCHARGE = 2
    NORMALCHARGE = 3


class SLXOpenEVSE:
    """Class for OpenEVSE connection"""

    def __init__(
        self,
        hass: HomeAssistant,
        cb_sessionenergy: Callable[[Event], Any],
        cb_plug: Callable[[Event], Any],
    ):
        _LOGGER.debug("SLXOpenEVSE")
        self.hass = hass
        self.charge_mode = ChargerMode.UNKNOWN
        # entity_list = SLXOpenEVSE.__find_openevse_entities(hass)
        self.unsub_dict: dict[str, Callable[[Event], Any]] = {}
        SLXOpenEVSE.check_all_entities(hass)
        self.__subscribe_entity(WatchedEntities["sessionenergy"], cb_sessionenergy)
        self.__subscribe_entity(WatchedEntities["plug"], cb_plug)

    def __subscribe_entity(
        self, entity_name: str, external_calback: Callable[[Event], Any]
    ) -> None:
        self.unsub_dict[entity_name] = async_track_state_change_event(
            self.hass, entity_name, external_calback
        )

    def _get_value(self, name: str) -> Any:
        if name in GetEntities:
            return self.hass.states.get(GetEntities[name])
        else:
            return None

    def _set_value(self, name: str, value: Any) -> bool:
        if name in SetEntities:
            self.hass.states.set(SetEntities[name], value)
            return True
        else:
            return False

    def set_charger_mode(self, mode: ChargerMode) -> None:
        if mode == self.charge_mode:
            return
        self.charge_mode = mode

        if self.charge_mode == ChargerMode.STOPPED:
            self._set_value(SetEntities["divertmode"], "fast")
            self._set_value(SetEntities["sleepmode"], "on")
            return

        if self.charge_mode == ChargerMode.PVCHARGE:
            self._set_value(SetEntities["divertmode"], "eco")
            self._set_value(SetEntities["sleepmode"], "on")
            return

        if self.charge_mode == ChargerMode.NORMALCHARGE:
            self._set_value(SetEntities["divertmode"], "fast")
            self._set_value(SetEntities["sleepmode"], "off")
            return

    @staticmethod
    def _find_openevse_entities(hass: HomeAssistant) -> dict[str, EntityRegistry]:
        deviceregistry = device_registry.async_get(hass)
        openevse_id = None
        for device_id in deviceregistry.devices:
            device = deviceregistry.async_get(device_id)
            if device.manufacturer == "OpenEVSE":
                # check all other information
                details_ok = True
                if device.model != "openevse_wifi_v1":
                    details_ok = False
                if details_ok is True:
                    openevse_id = device_id
                    break
        if openevse_id is None:
            return
        _LOGGER.debug("Found OpenEVSE %s", openevse_id)

        entity_list: dict[str, EntityRegistry] = {}
        entityregistry = entity_registry.async_get(hass)
        for entity_id in entityregistry.entities:
            entity = entityregistry.async_get(entity_id)
            if entity.device_id == openevse_id:
                entity_list[entity.entity_id] = entity
        return entity_list

    @staticmethod
    def check_all_entities(hass: HomeAssistant) -> bool:
        """Checks if we have OpenEVSE device with all required entities"""
        entity_list = SLXOpenEVSE._find_openevse_entities(hass)
        if not entity_list:
            return False

        all_good = True

        to_check_list = [WatchedEntities, SetEntities, GetEntities]
        for checking_list in to_check_list:
            for entity_name in checking_list.values():
                if entity_name in entity_list:
                    _LOGGER.info("Found %s", entity_name)
                    _LOGGER.debug(entity_list[entity_name])
                else:
                    _LOGGER.error("Missing entity %s", entity_name)
                    all_good = False

        return all_good
