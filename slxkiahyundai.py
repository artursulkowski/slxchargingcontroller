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

from .slxcar import SLXCar

_LOGGER = logging.getLogger(__name__)


class SLXKiaHyundai(SLXCar):
    DOMAIN_NAME = "kia_uvo"
    FORCE_UPDATE_SERVICE = "force_update"

    # entities we subscribe to
    WATCHED_ENTITIES = {
        # type of value : entity_id
        "soclevel": "sensor.{devicename}_ev_battery_level",
        "soclastupdate": "sensor.{devicename}_last_updated_at",
    }

    @staticmethod
    def get_domain() -> str:
        return SLXKiaHyundai.DOMAIN_NAME

    @staticmethod
    def get_required_entities() -> list[dict[str, str]]:
        combined_list = [SLXKiaHyundai.WATCHED_ENTITIES]
        return combined_list

    def __init__(self, hass: HomeAssistant):
        _LOGGER.info("Initialize SLXKiaHyundai")
        super().__init__(hass)
        # overwrite some config information

    def connect(
        self,
        cb_soc: Callable[[Event], Any],
        cb_soc_update: Callable[[Event], Any],
        device_id: str | None = None,
    ) -> bool:
        found_devices = self.find_devices_check_entites(
            self.hass, SLXKiaHyundai.get_domain(), SLXKiaHyundai.get_required_entities()
        )

        if device_id in found_devices:
            self.device_id = device_id
            self.device_name = found_devices[self.device_id]
        else:
            _LOGGER.error("Device %s not found", device_id)
            return False
        self.slugified_name = SLXCar._slugify_device_name(self.device_name)
        _LOGGER.info("Found Kia/Hyundai device : device_name %s", self.device_name)

        self._subscribe_entity(
            SLXCar._traslate_entity_name(
                SLXKiaHyundai.WATCHED_ENTITIES["soclevel"], self.slugified_name
            ),
            cb_soc,
        )

        self._subscribe_entity(
            SLXCar._traslate_entity_name(
                SLXKiaHyundai.WATCHED_ENTITIES["soclastupdate"], self.slugified_name
            ),
            cb_soc_update,
        )
        super().connect()

    async def disconnect(self) -> bool:
        _LOGGER.info("Disconnect")
        if self.connected is False:
            # it's already disconnected, ignore the request.
            return True
        super().disconnect()

    def request_soc_update(self) -> bool:
        # TODO - add checking if integration was connected

        if self.hass.services.has_service(
            SLXKiaHyundai.DOMAIN_NAME, SLXKiaHyundai.FORCE_UPDATE_SERVICE
        ):
            self.hass.async_add_executor_job(
                self.hass.services.call,
                SLXKiaHyundai.DOMAIN_NAME,
                SLXKiaHyundai.FORCE_UPDATE_SERVICE,
                {},
            )
            return True
        return False
