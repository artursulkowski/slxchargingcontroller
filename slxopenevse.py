""" slxmodule for connecting with OpenEVSE"""

from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers import entity_registry, device_registry
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.util import slugify

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
    "sessionenergy": "sensor.{devicename}_usage_this_session",
    "plug": "binary_sensor.{devicename}_vehicle_connected",
}

# entities we are taking value from
GetEntities = {
    "maxcurrent": "select.{devicename}_max_current",
    "divertactive": "binary_sensor.{devicename}_divert_active",
}


# entities we are setting value
SetEntities = {
    "manualoverride": "switch.{devicename}_manual_override",
    "divertmode": "select.{devicename}_divert_mode",
}

_LOGGER = logging.getLogger(__name__)


class SLXOpenEVSE:
    """Class for OpenEVSE connection"""

    def __init__(
        self,
        hass: HomeAssistant,
        cb_sessionenergy: Callable[[Event], Any],
        cb_plug: Callable[[Event], Any],
        device_id: str | None = None,
    ):
        _LOGGER.debug("SLXOpenEVSE")

        self.hass = hass

        self.openevse_id = device_id
        self.openevse_name = SLXOpenEVSE.get_openevse_devicename(hass, device_id)
        if self.openevse_name is None:
            _LOGGER.error("OpenEVSE device with device_id=%s does not exist", device_id)

        self.openevse_slugified_name = SLXOpenEVSE._slugify_device_name(
            self.openevse_name
        )

        self.charge_mode: str = CHR_MODE_UNKNOWN
        self.unsub_dict: dict[str, Callable[[Event], Any]] = {}
        if (
            SLXOpenEVSE.check_all_entities(hass, self.openevse_id, self.openevse_name)
            is False
        ):
            _LOGGER.error(
                "OpenEVSE device wasn't found or there were not all required entities"
            )
        else:
            self.__subscribe_entity(
                SLXOpenEVSE.__traslate_entity_name(
                    WatchedEntities["sessionenergy"], self.openevse_slugified_name
                ),
                cb_sessionenergy,
            )
            self.__subscribe_entity(
                SLXOpenEVSE.__traslate_entity_name(
                    WatchedEntities["plug"], self.openevse_slugified_name
                ),
                cb_plug,
            )
            _LOGGER.info("SLXOpenEVSE correctly initialized")

    @staticmethod
    def __traslate_entity_name(template_name: str, openevse_slugified_name: str) -> str:
        if openevse_slugified_name is not None:
            result = template_name.format(devicename=openevse_slugified_name)
        else:
            result = template_name.format(devicename="")
            _LOGGER.warning(
                "Missing OpenEVSE device name when trying to translate entity %s",
                template_name,
            )
        return result

    def __subscribe_entity(
        self, entity_name: str, external_calback: Callable[[Event], Any]
    ) -> None:
        self.unsub_dict[entity_name] = async_track_state_change_event(
            self.hass, entity_name, external_calback
        )

    def _get_value(self, name: str) -> Any:
        translated_name: str | None = None

        if name in GetEntities:
            translated_name = SLXOpenEVSE.__traslate_entity_name(
                GetEntities[name], self.openevse_slugified_name
            )
        if name in SetEntities:
            translated_name = SLXOpenEVSE.__traslate_entity_name(
                SetEntities[name], self.openevse_slugified_name
            )
        if name in WatchedEntities:
            translated_name = SLXOpenEVSE.__traslate_entity_name(
                WatchedEntities[name], self.openevse_slugified_name
            )

        if translated_name is None:
            return None

        entity_state = self.hass.states.get(translated_name)
        if entity_state is None:
            return None
        return entity_state.state

    def _set_value(self, name: str, value: Any) -> bool:
        if name in SetEntities:
            self.hass.async_add_executor_job(
                self.hass.states.set,
                SLXOpenEVSE.__traslate_entity_name(
                    SetEntities[name], self.openevse_slugified_name
                ),
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
                {
                    "entity_id": SLXOpenEVSE.__traslate_entity_name(
                        SetEntities[name], self.openevse_slugified_name
                    ),
                    "option": value,
                },
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

    def get_session_energy(self) -> float:
        return self._get_value("sessionenergy")

    @staticmethod
    def _slugify_device_name(device_name: str) -> str:
        return slugify(device_name.lower())

    @staticmethod
    def find_openevse_devices(hass: HomeAssistant) -> dict[str, str]:
        """Finds list of compatible OpenEVSE devices
        :returns: Dictionary of [deviceID, DeviceName]
        """
        devices_found: dict[str, str] = {}
        deviceregistry = device_registry.async_get(hass)
        for device_id in deviceregistry.devices:
            device = deviceregistry.async_get(device_id)
            if device.manufacturer == "OpenEVSE":
                if device.model == "openevse_wifi_v1":
                    devices_found[device_id] = device.name
        return devices_found

    @staticmethod
    def _find_device_entities(
        hass: HomeAssistant, device_id: str
    ) -> dict[str, EntityRegistry] | None:
        """
        Lists all entities belonging to a given device. It's universal and requires only device_id
        :returns: None if no device was found. Otherwise returns list of entities.
        """
        entity_list: dict[str, EntityRegistry] = {}
        entityregistry = entity_registry.async_get(hass)
        for entity_id in entityregistry.entities:
            entity = entityregistry.async_get(entity_id)
            if entity.device_id == device_id:
                entity_list[entity.entity_id] = entity
        return entity_list

    @staticmethod
    def get_openevse_devicename(hass: HomeAssistant, device_id: str) -> str | None:
        found_devices = SLXOpenEVSE.find_openevse_devices(hass)
        if device_id in found_devices:
            return found_devices[device_id]
        else:
            return None

    @staticmethod
    def check_all_entities(
        hass: HomeAssistant, device_id: str, device_name: str | None = None
    ) -> bool:
        """Checks if we have OpenEVSE device with all required entities"""

        if device_name is None:
            device_name = SLXOpenEVSE.get_openevse_devicename(hass, device_id)

        if device_name is None:
            return False

        slugified_device_name = SLXOpenEVSE._slugify_device_name(device_name)

        entity_list = SLXOpenEVSE._find_device_entities(hass, device_id)
        if not entity_list:
            return False

        all_good = True

        to_check_list = [WatchedEntities, SetEntities, GetEntities]

        list_of_entity_names = []
        for checking_list in to_check_list:
            for entity_template in checking_list.values():
                list_of_entity_names.append(
                    SLXOpenEVSE.__traslate_entity_name(
                        entity_template, slugified_device_name
                    )
                )

        for entity_name in list_of_entity_names:
            if entity_name in entity_list:
                _LOGGER.info("Found %s", entity_name)
            else:
                _LOGGER.warning("Missing entity %s", entity_name)
                all_good = False
        return all_good
