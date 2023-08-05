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


class SLXKiaHyundai:
    @staticmethod
    async def find_kiahyundai_devices(hass: HomeAssistant) -> dict[str, str]:
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

        return devices_found

    @staticmethod
    def jump_function(hass: HomeAssistant) -> dict[str, str]:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(SLXKiaHyundai.find_kiahyundai_devices(hass))
        return result

    #      return await SLXKiaHyundai.find_kiahyundai_devices(hass)

    @staticmethod
    def sync_find_kiahyundai_devices(hass: HomeAssistant) -> dict[str, str]:
        # loop = asyncio.get_event_loop()
        # task = loop.create_task(SLXKiaHyundai.jump_function(hass))

        result = hass.async_add_executor_job(SLXKiaHyundai.jump_function, hass)
        #  result = loop.run_until_complete(task)

        _LOGGER.info(result)
        return result
