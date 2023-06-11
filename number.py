"""Number entities for SlxChargingController"""
from __future__ import annotations

import logging
from typing import Final
from dataclasses import dataclass


from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SOC_LIMIT_MIN,
    SOC_LIMIT_MAX,
    ENT_SOC_LIMIT_MIN,
    ENT_SOC_LIMIT_MAX,
    CMD_SOC_MIN,
    CMD_SOC_MAX,
)
from .coordinator import SLXChgCtrlUpdateCoordinator
from .entity import SlxChgCtrlEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class SLXNumberEntityDescription(NumberEntityDescription):
    """Extend default NumberEntityDescription to include options and command which should be called in coordinator"""

    command: str | None = None
    data_entry: str | None = None


NUMBER_DESCRIPTIONS: Final[tuple[SLXNumberEntityDescription, ...]] = (
    SLXNumberEntityDescription(
        key=SOC_LIMIT_MIN,
        command=CMD_SOC_MIN,
        data_entry=ENT_SOC_LIMIT_MIN,
        name="SOC Limit min",
        icon="mdi:ev-plug-type2",
        native_min_value=0,
        native_max_value=100,
        native_step=5,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SLXNumberEntityDescription(
        key=SOC_LIMIT_MAX,
        command=CMD_SOC_MAX,
        data_entry=ENT_SOC_LIMIT_MAX,
        name="SOC Limit max",
        icon="mdi:ev-plug-type2",
        native_min_value=0,
        native_max_value=100,
        native_step=5,
        native_unit_of_measurement=PERCENTAGE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities = []

    for description in NUMBER_DESCRIPTIONS:
        entities.append(SlxChgCtrlNumber(coordinator, description))

    async_add_entities(entities)
    return True


# class representing entity
class SlxChgCtrlNumber(NumberEntity, SlxChgCtrlEntity):
    """number entities for Salix Charging Controller"""

    def __init__(
        self,
        coordinator: SLXChgCtrlUpdateCoordinator,
        description: SLXNumberEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self._description = description
        self._key = self._description.key
        self._command = self._description.command
        self._data_entry = self._description.data_entry
        self._attr_unique_id = f"{DOMAIN}_{self._key}"
        self._attr_icon = self._description.icon
        self._attr_name = f"{self._description.name}"
        self._attr_device_class = self._description.device_class

    @property
    def native_min_value(self):
        """Return native_min_value as reported in by the sensor"""
        return self._description.native_min_value

    @property
    def native_max_value(self):
        """Returnnative_max_value as reported in by the sensor"""
        return self._description.native_max_value

    @property
    def native_step(self):
        """Return step value as reported in by the sensor"""
        return self._description.native_step

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value was reported in by the sensor"""
        return self._description.native_unit_of_measurement

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        coordinator: SLXChgCtrlUpdateCoordinator = self.coordinator
        data = coordinator.data
        if self._data_entry in data and data is not None:
            state = data[self._data_entry]
            return float(state)
        return None

    async def async_set_native_value(self, value: float) -> None:
        coordinator: SLXChgCtrlUpdateCoordinator = self.coordinator
        try:
            await getattr(coordinator, self._command)(value)
            self.async_write_ha_state()
        except (ValueError, KeyError, AttributeError) as err:
            _LOGGER.warning(
                "Could not set status for %s error: %s", self._attr_name, err
            )
