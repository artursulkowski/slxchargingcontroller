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
    def check_entites_and_devices(hass: HomeAssistant) -> dict[str, str]:
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

    # THAT DOESN'T WORK
    # @staticmethod
    # def _find_integration(hass: HomeAssistant, domain_name: str) -> bool:
    #     # loop = asyncio.get_event_loop()
    #     # task = loop.create_task(SLXKiaHyundai.jump_function(hass))

    #     def find_integration_jump(hass: HomeAssistant, domain_name: str) -> bool:
    #         loop = asyncio.new_event_loop()
    #         result = loop.run_until_complete(
    #             SLXKiaHyundai.async_find_integration(hass, domain_name)
    #         )
    #         return result

    #     result = hass.async_add_executor_job(find_integration_jump, hass, domain_name)
    #     return result

    # @staticmethod
    # def config_find_integration(hass: HomeAssistant) -> dict[str, str]:
    #     """Find list of compatible
    #     :returns: Dictionary of [deviceId, DeviceName]
    #     """
    #     devices_found: dict[str, str] = {}

    #     is_integration_found: bool = SLXKiaHyundai._find_integration(
    #         hass, KIAHYUNDAI_NAME
    #     )
    #     _LOGGER.warning(is_integration_found)
    #     if is_integration_found is False:
    #         return devices_found

    @staticmethod
    async def find_kiahyundai_devices_test(hass: HomeAssistant) -> dict[str, str]:
        """Finds list of compatible OpenEVSE devices
        :returns: Dictionary of [deviceID, DeviceName]
        """
        domain: str = "kia_uvo"
        my_integration = await async_get_integration(hass, domain)

        # my_integration = hass.async_add_executor_job(async_get_integration, domain)

        _LOGGER.warning(my_integration)
        _LOGGER.info(my_integration.domain)
        _LOGGER.info(my_integration.version)
        component = my_integration.get_component()
        _LOGGER.info(component)
        _LOGGER.info(component.DOMAIN)

        devices_found: dict[str, str] = {}
        deviceregistry = device_registry.async_get(hass)
        for device_id in deviceregistry.devices:
            device = deviceregistry.async_get(device_id)

            _LOGGER.debug(device)
            _LOGGER.debug("device.manufacturer = %s", device.manufacturer)
            _LOGGER.debug("device.model = %s", device.model)
            _LOGGER.debug("device.id = %s", device.id)
            _LOGGER.debug("device.sw_version = %s", device.sw_version)
            _LOGGER.debug("device.hw_version = %s", device.hw_version)

            # if device.manufacturer == "OpenEVSE":
            #     if device.model == "openevse_wifi_v1":
            #         devices_found[device_id] = device.name

        ### Look for entities with the right device and right integration.

        entity_list: dict[str, EntityRegistry] = {}
        entityregistry = entity_registry.async_get(hass)

        devices_within_domain: list[str] = []

        for entity_id in entityregistry.entities:
            entity = entityregistry.async_get(entity_id)
            # _LOGGER.debug(entity)
            if entity.platform == "kia_uvo":
                _LOGGER.info(entity)
                device_id = entity.device_id
                if device_id not in devices_within_domain:
                    devices_within_domain.append(device_id)

        _LOGGER.warning("Found devices:")
        _LOGGER.warning(devices_within_domain)
        for device in devices_within_domain:
            devices_found[device] = device

        return devices_found

    # @staticmethod
    # async def jump_function_asnyc(hass: HomeAssistant) -> dict[str, str]:
    #     result = await SLXKiaHyundai.find_kiahyundai_devices_test(hass)
    #     return result

    # @staticmethod
    # def jump_function(hass: HomeAssistant) -> dict[str, str]:
    #     loop = asyncio.new_event_loop()
    #     # loop = asyncio.get_event_loop()
    #     result = loop.run_until_complete(
    #         # SLXKiaHyundai.jump_function_asnyc(hass)
    #         SLXKiaHyundai.find_kiahyundai_devices_test(hass)
    #     )
    #     return result

    #      return await SLXKiaHyundai.find_kiahyundai_devices(hass)

    # @staticmethod
    # def sync_find_kiahyundai_devices(hass: HomeAssistant) -> dict[str, str]:
    #     # loop = asyncio.get_event_loop()
    #     # task = loop.create_task(SLXKiaHyundai.jump_function(hass))

    #     feature_result = hass.async_add_executor_job(SLXKiaHyundai.jump_function, hass)
    #     ##    result = asyncio.run(feature_result)
    #     # result2 = asyncio.ensure_future(feature_result)
    #     # await asyncio.gather(feature_result)
    #     result = feature_result.result()
    #     #  result = loop.run_until_complete(task)

    #     _LOGGER.warning(result)
    #     return result
