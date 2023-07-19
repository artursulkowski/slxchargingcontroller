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

from .const import (
    CHARGER_MODES,
    CHR_MODE_UNKNOWN,
    CHR_MODE_STOPPED,
    CHR_MODE_PVCHARGE,
    CHR_MODE_NORMAL,
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
}

_LOGGER = logging.getLogger(__name__)


class SLXOpenEVSE:
    """Class for OpenEVSE connection"""

    openevse_id: str | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        cb_sessionenergy: Callable[[Event], Any],
        cb_plug: Callable[[Event], Any],
    ):
        _LOGGER.debug("SLXOpenEVSE")
        self.hass = hass
        self.charge_mode: str = CHR_MODE_UNKNOWN
        self.unsub_dict: dict[str, Callable[[Event], Any]] = {}
        if SLXOpenEVSE.check_all_entities(hass) is False:
            _LOGGER.error(
                "OpenEVSE device wasn't found or there were not all required entities"
            )
        else:
            self.__subscribe_entity(WatchedEntities["sessionenergy"], cb_sessionenergy)
            self.__subscribe_entity(WatchedEntities["plug"], cb_plug)
            _LOGGER.info("SLXOpenEVSE correctly initialized")

    def __subscribe_entity(
        self, entity_name: str, external_calback: Callable[[Event], Any]
    ) -> None:
        self.unsub_dict[entity_name] = async_track_state_change_event(
            self.hass, entity_name, external_calback
        )

    def _get_value(self, name: str) -> Any:
        if name in GetEntities:
            return self.hass.states.get(GetEntities[name]).state
        if name in SetEntities:
            return self.hass.states.get(SetEntities[name]).state
        return None

    def _set_value(self, name: str, value: Any) -> bool:
        if name in SetEntities:
            self.hass.async_add_executor_job(
                self.hass.states.set,
                SetEntities[name],
                value,
                {},
            )
            return True
        else:
            return False

    def _select_option(self, name: str, value: str) -> bool:
        if name in SetEntities:
            self.hass.async_add_executor_job(
                self.hass.services.call,
                "select",
                "select_option",
                {"entity_id": SetEntities[name], "option": value},
            )
            _LOGGER.debug("_select_option %s to %s", name, value)
            return True
        else:
            _LOGGER.warning("_select_option is invalid: %s", name)

        return False

    def _activate_override(self, charge: bool) -> bool:
        value_to_set: str = ""
        if charge:
            value_to_set = "active"
        else:
            value_to_set = "disabled"
        _LOGGER.debug(
            "_activate_override - value: %s, device_id = %s",
            value_to_set,
            SLXOpenEVSE.openevse_id,
        )
        self.hass.async_add_executor_job(
            self.hass.services.call,
            "openevse",
            "set_override",
            {"state": value_to_set, "device_id": [SLXOpenEVSE.openevse_id]},
        )

    def _clear_override(self) -> bool:
        _LOGGER.debug("_clear_override, device_id = %s", SLXOpenEVSE.openevse_id)
        self.hass.async_add_executor_job(
            self.hass.services.call,
            "openevse",
            "clear_override",
            {"device_id": [SLXOpenEVSE.openevse_id]},
        )

    def set_charger_mode(self, mode: str) -> None:
        if not mode in CHARGER_MODES:
            _LOGGER.warning("Invalid charing mode %s", mode)
            return
        _LOGGER.info("Set charger mode %s", mode)

        if mode == self.charge_mode:
            return
        self.charge_mode = mode

        if self.charge_mode == CHR_MODE_STOPPED:
            if self._get_value("divertmode") != "fast":
                self._select_option("divertmode", "fast")
            self._activate_override(False)
            return

        if self.charge_mode == CHR_MODE_PVCHARGE:
            if self._get_value("divertmode") != "eco":
                self._select_option("divertmode", "eco")
            self._clear_override()
            return

        if self.charge_mode == CHR_MODE_NORMAL:
            if self._get_value("divertmode") != "fast":
                self._select_option("divertmode", "fast")
            self._activate_override(True)
            return

    @staticmethod
    def _find_openevse_entities(hass: HomeAssistant) -> dict[str, EntityRegistry]:
        deviceregistry = device_registry.async_get(hass)
        #  openevse_id = None
        for device_id in deviceregistry.devices:
            device = deviceregistry.async_get(device_id)
            if device.manufacturer == "OpenEVSE":
                # check all other information
                details_ok = True
                if device.model != "openevse_wifi_v1":
                    details_ok = False
                if details_ok is True:
                    SLXOpenEVSE.openevse_id = device_id
                    break
        if SLXOpenEVSE.openevse_id is None:
            _LOGGER.warning("OpenEVSE device is not found")
            return
        _LOGGER.info("Found OpenEVSE , device_id = %s", SLXOpenEVSE.openevse_id)

        entity_list: dict[str, EntityRegistry] = {}
        entityregistry = entity_registry.async_get(hass)
        for entity_id in entityregistry.entities:
            entity = entityregistry.async_get(entity_id)
            if entity.device_id == SLXOpenEVSE.openevse_id:
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
                else:
                    _LOGGER.warning("Missing entity %s", entity_name)
                    all_good = False

        return all_good
