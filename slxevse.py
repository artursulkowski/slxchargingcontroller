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

_LOGGER = logging.getLogger(__name__)


class SLXEvse:
    """base class for any EVSE connection"""

    def __init__(
        self,
        hass: HomeAssistant,
    ):
        self.hass = hass
        self.charge_mode: str = CHR_MODE_UNKNOWN
        self.unsub_dict: dict[str, Callable[[Event], Any]] = {}
        self.connected: bool = False

    def set_charger_mode(self, mode: str) -> None:
        _LOGGER.error("Setting charger mode is not defined")

    def _subscribe_entity(
        self, entity_name: str, external_calback: Callable[[Event], Any]
    ) -> None:
        self.unsub_dict[entity_name] = async_track_state_change_event(
            self.hass, entity_name, external_calback
        )

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
