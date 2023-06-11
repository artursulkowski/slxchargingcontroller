"""Select entities for SlxChargingController"""

from __future__ import annotations
from dataclasses import dataclass

from collections.abc import Callable
import logging
from typing import Final, Any


from homeassistant.components.select import SelectEntity, SelectEntityDescription

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SLXChgCtrlUpdateCoordinator
from .entity import SlxChgCtrlEntity

from .const import DOMAIN, CMD_CHARGE_MODE, ENT_CHARGE_MODE

_LOGGER = logging.getLogger(__name__)


@dataclass
class SLXSelectEntityDescription(SelectEntityDescription):
    """Extend default SelectEntityDescription to include options and command which should be called in coordinator"""

    command: str | None = None
    data_entry: str | None = None
    default_options: list | None = None


SELECT_DESCRIPTIONS: Final[tuple[SLXSelectEntityDescription, ...]] = (
    SLXSelectEntityDescription(
        key=CMD_CHARGE_MODE,
        command="set_charger_select",
        data_entry=ENT_CHARGE_MODE,
        name="Charge mode",
        default_options=["UNKNOWN", "STOPPED", "PVCHARGE", "NORMALCHARGE"],
        icon="mdi:ev-station",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities = []

    for description in SELECT_DESCRIPTIONS:
        entities.append(SlxChrCtrlSelect(coordinator, description))

    async_add_entities(entities)
    return True


class SlxChrCtrlSelect(SelectEntity, SlxChgCtrlEntity):
    def __init__(
        self,
        coordinator: SLXChgCtrlUpdateCoordinator,
        description: SLXSelectEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self._description = description
        self._key = self._description.key
        self._command = description.command
        self._data_entry = description.data_entry
        self._attr_unique_id = f"{DOMAIN}_{self._key}"
        self._attr_icon = self._description.icon
        self._attr_name = f"{self._description.name}"
        self._attr_options = description.default_options

    @property
    def current_option(self) -> str | None:
        coordinator: SLXChgCtrlUpdateCoordinator = self.coordinator
        data = coordinator.data
        if self._data_entry in data and data is not None:
            state = data[self._data_entry]
            return str(state)
        return None

    async def async_select_option(self, option: Any) -> None:
        coordinator: SLXChgCtrlUpdateCoordinator = self.coordinator
        try:
            await getattr(coordinator, self._command)(option)
            self.async_write_ha_state()
        except (ValueError, KeyError, AttributeError) as err:
            _LOGGER.warning(
                "Could not set status for %s error: %s", self._attr_name, err
            )
