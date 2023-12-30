""" slxmodule for connecting using manual configuration"""

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


class SLXCarManual(SLXCar):
    def __init__(self, hass: HomeAssistant):
        _LOGGER.info("Initialize SLXCarManual")
        super().__init__(hass)
        # overwrite some config information

    def connect(
        self,
        cb_soc: Callable[[Event], Any],
        entity_name_soc: str,
        cb_soc_update: Callable[[Event], Any] | None = None,
        entity_name_soc_update: str | None = None,
    ) -> bool:
        self._subscribe_entity(entity_name_soc, cb_soc)
        if cb_soc_update is not None and entity_name_soc_update is not None:
            self._subscribe_entity(entity_name_soc_update, cb_soc_update)
        super().connect()
        return True

    async def disconnect(self) -> bool:
        _LOGGER.info("Disconnect")
        if self.connected is False:
            # it's already disconnected, ignore the request.
            return True
        super().disconnect()

    def request_soc_update(self) -> bool:
        # Nothing functional should be implemented at manual integration.
        return True
