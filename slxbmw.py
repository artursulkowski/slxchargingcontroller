""" slxmodule for bmw connect integratio"""

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

from .slxcar import SLXCar

_LOGGER = logging.getLogger(__name__)


class SLXBmw(SLXCar):
    DOMAIN_NAME = "bmw_connected_drive"

    # entities we subscribe to
    WATCHED_ENTITIES = {
        # type of value : entity_id
        "soclevel": "sensor.{devicename}_remaining_battery_percent",
    }

    @staticmethod
    def get_domain() -> str:
        return SLXBmw.DOMAIN_NAME

    @staticmethod
    def get_required_entities() -> list[dict[str, str]]:
        combined_list = [SLXBmw.WATCHED_ENTITIES]
        return combined_list

    def __init__(self, hass: HomeAssistant):
        _LOGGER.info("Initialize SLXBMW")
        super().__init__(hass)
        self.dynamic_config[SLXCar.CONF_SOC_UPDATE_REQUIRED] = False

    def connect(
        self,
        cb_soc: Callable[[Event], Any],
        cb_soc_update: Callable[[Event], Any] | None = None,
        device_id: str | None = None,
    ) -> bool:
        found_devices = SLXCar.find_devices_check_entites(
            self.hass, SLXBmw.get_domain(), SLXBmw.get_required_entities()
        )

        # self.device_id = device_id
        if device_id in found_devices:
            self.device_id = device_id
            self.device_name = found_devices[self.device_id]
        else:
            _LOGGER.error("Device %s not found", device_id)
            return False
        self.slugified_name = SLXCar._slugify_device_name(self.device_name)
        _LOGGER.info("Found BMW device : device_name %s", self.device_name)

        self._subscribe_entity(
            SLXCar._traslate_entity_name(
                SLXBmw.WATCHED_ENTITIES["soclevel"], self.slugified_name
            ),
            cb_soc,
        )

        super().connect()

    async def disconnect(self) -> bool:
        _LOGGER.info("Disconnect")
        super().disconnect()

    def request_soc_update(self) -> bool:
        UPDATE_SERVICE_DOMAIN = "homeassistant"
        UPDATE_SERVICE_REQUEST = "update_entity"
        entity_name = SLXCar._traslate_entity_name(
            SLXBmw.WATCHED_ENTITIES["soclevel"], self.slugified_name
        )
        if self.hass.services.has_service(
            UPDATE_SERVICE_DOMAIN, UPDATE_SERVICE_REQUEST
        ):
            self.hass.async_add_executor_job(
                self.hass.services.call,
                UPDATE_SERVICE_DOMAIN,
                UPDATE_SERVICE_REQUEST,
                {"entity_id": entity_name},
            )
            return True
        return False
