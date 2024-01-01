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

from .slxevse import SLXEvse

from .const import (
    CHARGER_MODES,
    CHR_MODE_UNKNOWN,
    CHR_MODE_STOPPED,
    CHR_MODE_PVCHARGE,
    CHR_MODE_NORMAL,
)

_LOGGER = logging.getLogger(__name__)


class SLXManualEvse(SLXEvse):
    """Class for manual EVSE connection"""

    def __init__(
        self,
        hass: HomeAssistant,
    ):
        _LOGGER.debug("SLXManualEvse")
        super().__init__(hass)

    def connect(
        self,
        cb_sessionenergy: Callable[[Event], Any],
        session_energy_name: str,
        cb_plug: Callable[[Event], Any],
        plug_name: str,
    ) -> bool:
        self._subscribe_entity(session_energy_name, cb_sessionenergy)
        self._subscribe_entity(plug_name, cb_plug)
        self._session_energy_name = session_energy_name
        self._plug_name = plug_name
        return True

    def get_session_energy(self) -> float | None:
        entity_state = self.hass.states.get(self._session_energy_name)
        if entity_state is None:
            _LOGGER.warning(
                "Get_session_energy - value of %s is None", self._session_energy_name
            )
            return None
        try:
            value_str = entity_state.state
            value = float(value_str)
            return value
        except ValueError:
            _LOGGER.warning("Get_session_energy - invalid state= %s", value_str)
            return None
        return None

    def set_charger_mode(self, mode: str) -> None:
        if not mode in CHARGER_MODES:
            _LOGGER.warning("Invalid charing mode %s", mode)
            return
        _LOGGER.info("Set charger mode %s", mode)

        if mode == self.charge_mode:
            return
        self.charge_mode = mode
