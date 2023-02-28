"""Sensor entities for SlxChargingController"""

# Look at https://developers.home-assistant.io/docs/core/entity/sensor for possible device clsses

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Final


from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)


from homeassistant.const import (
    PERCENTAGE,
    TIME_MINUTES,
    ENERGY_WATT_HOUR,
    ENERGY_KILO_WATT_HOUR,
)


from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SLXChgCtrlUpdateCoordinator
from .entity import SlxChgCtrlEntity

_LOGGER = logging.getLogger(__name__)

BATTERY_ENERGY_ESTIMATION = "slx_battery_estimation"

SENSOR_DESCRIPTIONS: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        key=BATTERY_ENERGY_ESTIMATION,
        name="Battery Energy Estimation",
        icon="mdi:lightning-bolt",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
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

    for description in SENSOR_DESCRIPTIONS:
        entities.append(SlxChgCtrlSensor(coordinator, description))

    async_add_entities(entities)
    return True


# class representing entity
class SlxChgCtrlSensor(SensorEntity, SlxChgCtrlEntity):
    def __init__(
        self,
        coordinator: SLXChgCtrlUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self._description = description
        self._key = self._description.key
        self._attr_unique_id = f"{DOMAIN}_{self._key}"
        self._attr_icon = self._description.icon
        self._attr_name = f"{self._description.name}"
        self._attr_device_class = self._description.device_class

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        _LOGGER.warning("Getting a native value!")
        # return getattr(self.vehicle, self._key)  <= this will be the more efficient way in case I have more information.
        if self._key == BATTERY_ENERGY_ESTIMATION:
            return self.coordinator.ent_soc_estimated
        else:
            return 0

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value was reported in by the sensor"""
        return self._description.native_unit_of_measurement

    # TODO - check how this callback can be connected to coordinator
    # /workspaces/core/homeassistant/components/xiaomi_miio/sensor.py - look for refence.
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.warning("Coordinator is updated!!")
        self._attr_state = self.coordinator.ent_soc_estimated
        # here is an example of nicer structure of getting different entity states from
        # self._attr_is_on = self.coordinator.data[self.idx]["state"]
        self.async_write_ha_state()

    async def async_update(self) -> None:
        _LOGGER.warning("SLX Sensor: async update")

    @property
    def available(self):
        return True
