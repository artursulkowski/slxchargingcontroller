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

    async def connect(self) -> bool:
        _LOGGER.info("Connect")

    async def disconnect(self) -> bool:
        _LOGGER.info("Disconnect")

    def request_soc_update(self) -> bool:
        _LOGGER.info("RequestSocUpdate")
