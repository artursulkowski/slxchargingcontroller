""" slxmodule for connecting with Kia Uvo, Hyundai Bluelink"""


from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers import entity_registry, device_registry
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.util import slugify
from homeassistant.loader import async_get_integrations, async_get_integration

import logging
import asyncio

from typing import Any
from enum import Enum

from homeassistant.core import (
    HomeAssistant,
    Event,
    Callable,
    State,
    callback,
)

_LOGGER = logging.getLogger(__name__)

KIAHYUNDAI_NAME = "kia_uvo"
FORCE_UPDATE_SERVICE = "force_update"


# entities we subscribe to
WatchedEntities = {
    # type of value : entity_id
    "soclevel": "sensor.{devicename}_ev_battery_level",
    "soclastupdate": "sensor.{devicename}_last_updated_at",
}


class SLXKiaHyundai:
    # Finding the integration
    @staticmethod
    def _slugify_device_name(device_name: str) -> str:
        return slugify(device_name.lower())

    @staticmethod
    async def async_find_integration(hass: HomeAssistant) -> bool:
        domain_name: str = KIAHYUNDAI_NAME
        integration = await async_get_integration(hass, domain_name)
        integration_version = integration.version

        _LOGGER.debug(
            "Integration - domain %s, version %s", domain_name, integration_version
        )
        component = integration.get_component()
        _LOGGER.debug(component)

        ## TODO - check if the propper integration doesn't exist
        return True

    @staticmethod
    def _find_entities_group_by_device(
        hass: HomeAssistant, domain_name: str
    ) -> dict[str, list[str, EntityRegistry]]:
        """
        :returns deviceId, (entity_id, EntityRegistry)
        """
        entity_list: dict[str, list[(str, EntityRegistry)]] = {}
        entityregistry = entity_registry.async_get(hass)
        for entity_id in entityregistry.entities:
            entity = entityregistry.async_get(entity_id)
            if entity.platform == domain_name:
                device_id = entity.device_id
                entity_id = entity.entity_id
                if device_id in entity_list:
                    entity_list[device_id].append((entity_id, entity))
                else:
                    entity_list[device_id] = [(entity_id, entity)]
                # entity_list[(device_id, entity_id)] = entity
        return entity_list

    @staticmethod
    def __traslate_entity_name(template_name: str, slugified_name: str) -> str:
        if slugified_name is not None:
            result = template_name.format(devicename=slugified_name)
        else:
            result = template_name.format(devicename="")
            _LOGGER.warning(
                "Missing device name when trying to translate entity %s",
                template_name,
            )
        return result

    @staticmethod
    def _check_entities(
        entity_list: list[(str, EntityRegistry)], slugified_device_name: str
    ) -> bool:
        all_good = True

        to_check_list = [WatchedEntities]

        list_of_entity_names = []
        for checking_list in to_check_list:
            for entity_template in checking_list.values():
                list_of_entity_names.append(
                    SLXKiaHyundai.__traslate_entity_name(
                        entity_template, slugified_device_name
                    )
                )
        # I need to translate entity_list into dictionary ( this can be optimized)
        entity_dict = {}
        for entity in entity_list:
            entity_dict[entity[0]] = entity[1]

        for entity_name in list_of_entity_names:
            if entity_name in entity_dict:
                _LOGGER.info("Found %s", entity_name)
            else:
                _LOGGER.warning("Missing entity %s", entity_name)
                all_good = False
        return all_good

    @staticmethod
    def find_devices_check_entites(hass: HomeAssistant) -> dict[str, str]:
        """Finds list of compatible KiaHyundai devices
        :returns: Dictionary of [deviceID, DeviceName]
        """
        entity_list = SLXKiaHyundai._find_entities_group_by_device(
            hass, KIAHYUNDAI_NAME
        )
        deviceregistry = device_registry.async_get(hass)

        devices_found: dict[str, str] = {}

        for device_id, ent_list in entity_list.items():
            device = deviceregistry.async_get(device_id)
            device_name = device.name
            device_name_slugified = SLXKiaHyundai._slugify_device_name(device_name)

            _LOGGER.warning(
                "Found deviceID = %s, deviceName= %s", device_id, device_name
            )
            # _LOGGER.warning("It's entities: ")
            # _LOGGER.info(ent_list)
            if SLXKiaHyundai._check_entities(ent_list, device_name_slugified) is True:
                devices_found[device_id] = device_name
                _LOGGER.info(
                    "Found  KiaHyundai device with correct entities. deviceID = %s, deviceName= %s",
                    device_id,
                    device_name,
                )
            else:
                _LOGGER.warning(
                    "Found KiaHyundai device without propper entities,deviceID = %s, deviceName= %s",
                    device_id,
                    device_name,
                )
        return devices_found

    def __subscribe_entity(
        self, entity_name: str, external_calback: Callable[[Event], Any]
    ) -> None:
        self.unsub_dict[entity_name] = async_track_state_change_event(
            self.hass, entity_name, external_calback
        )

    def __init__(
        self,
        hass: HomeAssistant,
        cb_soc: Callable[[Event], Any],
        cb_soc_update: Callable[[Event], Any],
        device_id: str | None = None,
    ):
        self.hass = hass
        found_devices = SLXKiaHyundai.find_devices_check_entites(hass)

        self.device_id = device_id
        if self.device_id in found_devices:
            self.device_name = found_devices[self.device_id]
        else:
            _LOGGER.error("Device %s not found", self.device_id)
            # TODO - consider throwing an exception.
            return

        self.slugified_name = SLXKiaHyundai._slugify_device_name(self.device_name)

        self.unsub_dict: dict[str, Callable[[Event], Any]] = {}
        self.__subscribe_entity(
            SLXKiaHyundai.__traslate_entity_name(
                WatchedEntities["soclevel"], self.slugified_name
            ),
            cb_soc,
        )
        self.__subscribe_entity(
            SLXKiaHyundai.__traslate_entity_name(
                WatchedEntities["soclastupdate"], self.slugified_name
            ),
            cb_soc_update,
        )
        _LOGGER.info("SLXKiaHyundai correctly initialized")

    def request_force_update(self) -> bool:
        if self.hass.services.has_service(KIAHYUNDAI_NAME, FORCE_UPDATE_SERVICE):
            self.hass.async_add_executor_job(
                self.hass.services.call, KIAHYUNDAI_NAME, FORCE_UPDATE_SERVICE, {}
            )
            return True
        return False
