""" slxmodule for car's integration base class"""

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


class SLXCar:
    # static helper methods - can be used by any car integration

    @staticmethod
    def _slugify_device_name(device_name: str) -> str:
        return slugify(device_name.lower())

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
    async def async_find_integration_by_domain(
        hass: HomeAssistant, domain_name: str
    ) -> bool:
        try:
            integration = await async_get_integration(hass, domain_name)
        except Exception:  # pylint: disable=broad-except
            return False

        integration_version = integration.version

        _LOGGER.debug(
            "Integration - domain %s, version %s", domain_name, integration_version
        )
        component = integration.get_component()
        _LOGGER.debug(component)
        return True

    @staticmethod
    def _traslate_entity_name(template_name: str, slugified_name: str) -> str:
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
        to_check_list: list[dict[str, str]],
        entity_list: list[(str, EntityRegistry)],
        slugified_device_name: str,
    ) -> bool:
        all_good = True

        list_of_entity_names = []
        for checking_list in to_check_list:
            for entity_template in checking_list.values():
                list_of_entity_names.append(
                    SLXCar._traslate_entity_name(entity_template, slugified_device_name)
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

    ## TODO - find_devices_check_entities will probably need some adjustment to meet specific criteria.
    ## Probably this can be covered using a dedicated
    @staticmethod
    def find_devices_check_entites(
        hass: HomeAssistant,
        domain: str,
        entities_list_to_check: list[dict[str, str]],
    ) -> dict[str, str]:
        """Finds list of compatible KiaHyundai devices
        :returns: Dictionary of [deviceID, DeviceName]
        """
        entity_list = SLXCar._find_entities_group_by_device(hass, domain)
        deviceregistry = device_registry.async_get(hass)

        devices_found: dict[str, str] = {}

        for device_id, ent_list in entity_list.items():
            device = deviceregistry.async_get(device_id)
            device_name = device.name
            device_name_slugified = SLXCar._slugify_device_name(device_name)

            _LOGGER.warning(
                "Found deviceID = %s, deviceName= %s", device_id, device_name
            )
            # _LOGGER.warning("It's entities: ")
            # _LOGGER.info(ent_list)
            # if SLXKiaHyundai._check_entities(ent_list, device_name_slugified) is True:
            if (
                SLXCar._check_entities(
                    entities_list_to_check, ent_list, device_name_slugified
                )
                is True
            ):
                devices_found[device_id] = device_name
                _LOGGER.info(
                    "Found device with correct entities. domain=%s  deviceID = %s, deviceName= %s",
                    domain,
                    device_id,
                    device_name,
                )
            else:
                _LOGGER.warning(
                    "Found device without propper entities,domain =%s, deviceID = %s, deviceName= %s",
                    domain,
                    device_id,
                    device_name,
                )
        return devices_found

    def _subscribe_entity(
        self, entity_name: str, external_calback: Callable[[Event], Any]
    ) -> None:
        self.unsub_dict[entity_name] = async_track_state_change_event(
            self.hass, entity_name, external_calback
        )

    # Configurations. Assume that all times are set in seconds.

    # Used by coordinator
    CONF_SOC_UPDATE_REQUIRED = "SOC_UPDATE_REQUIRED"  # True/False - does we need to subscribe for SOC Update time
    CONF_SOC_READING_DELAY = "SOC_READING_DELAY"  # time[s] how long after received SOC Update Time - we read SOC level. Only used if CONF_SOC_UPDATE_REQUIRED is True.
    CONF_SOC_UPDATE_RETRY = "SOC_UPDATE_RETRY"  # time[s] after which we retry "request_soc_update", if 0 or missing,  no retry is done
    # Used by charging manager
    CONF_SOC_REQUEST_TIMEOUT = "SOC_REQUEST_TIMEOUT"  # time[s] after which we treat that SOC isn't received and we switch to autopilot mode
    CONF_SOC_NEXT_UPDATE = (
        "SOC_NEXT_UPDATE"  # time[s] how often we request for checking SOC level
    )
    CONF_SOC_BEFORE_ENERGY = "SOC_BEFORE_ENERGY"  # time[s] how long before plug connection and/or receiving session energy from EVSE, SOC level is treated as valid.
    CONF_SOC_AFTER_ENERGY = "SOC_AFTER_ENERGY"  # time[s] how long after last energy reading - received SOC can be treated as valid.

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.unsub_dict: dict[str, Callable[[Event], Any]] = {}
        self.device_id = None
        self.device_name = None
        self.slugified_name = None
        self.connected: bool = False
        self.dynamic_config: dict[str, Any] = {
            SLXCar.CONF_SOC_UPDATE_REQUIRED: True,
            SLXCar.CONF_SOC_READING_DELAY: 20,
            SLXCar.CONF_SOC_UPDATE_RETRY: 60,
            SLXCar.CONF_SOC_REQUEST_TIMEOUT: 3 * 60,
            SLXCar.CONF_SOC_NEXT_UPDATE: 150 * 60,  # 2.5 h
            SLXCar.CONF_SOC_BEFORE_ENERGY: 15 * 60,  # 15 minutes
            SLXCar.CONF_SOC_AFTER_ENERGY: 48
            * 60
            * 60,  # up to 48 hours. In fact we need to handle a case in which session energy won't change because charging will be paused for few days!
        }

    def connect(self) -> bool:
        # method to connect with external intergration
        self.connected = True

    async def disconnect(self) -> bool:
        # method to disconnect from external integration
        if self.connected is False:
            return True

        for entity_name, cancel in self.unsub_dict.items():
            _LOGGER.debug("Unsubscribing entity %s", entity_name)
            cancel()

    def request_soc_update(self) -> bool:
        pass


## TODO - move as many as possible helper classes from slxkiahyundai.
## Skip public methods
