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
    UnitOfTime,
    UnitOfEnergy,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    BATTERY_ENERGY_ESTIMATION,
    BATTERY_SOC_ESTIMATION,
    CHARGING_SESSION_DURATION,
    REQUEST_SOC_UPDATE,
)
from .coordinator import SLXChgCtrlUpdateCoordinator
from .entity import SlxChgCtrlEntity

_LOGGER = logging.getLogger(__name__)

# TODO - additional charging status for now we will skip it or set this as bool. but there SensorDeviceClass.ENUM which I can use.
# CHARGING_STATUS = "charging_status"

# sensors  types: https://developers.home-assistant.io/docs/core/entity/sensor/
# mdi icons: https://pictogrammers.com/library/mdi/

SENSOR_DESCRIPTIONS: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        key=BATTERY_ENERGY_ESTIMATION,
        name="Battery Energy Estimation",
        icon="mdi:lightning-bolt",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    SensorEntityDescription(
        key=BATTERY_SOC_ESTIMATION,
        name="Battery SOC Estimation",
        icon="mdi:battery-charging",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key=CHARGING_SESSION_DURATION,
        name="Charging Session Duration",
        icon="mdi:battery-clock",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    # I cannot find a proper device and entity units (pure integer). Lets re-use percentage despite the fact that it can be a little bit confusing.
    SensorEntityDescription(
        key=REQUEST_SOC_UPDATE,
        name="Request SOC Update",
        icon="mdi:battery-sync",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
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
        self._attr_should_poll = False
        self._manager = coordinator.charging_manager
        attribute_name: str = f"_attr_{self._key}"
        if hasattr(self._manager, attribute_name):
            _LOGGER.debug("Cool %s exists", attribute_name)
        else:
            # Log non-existing attribute. Useful for WIP when not all properies are defined yet.
            self._attr_available = False
            _LOGGER.warning("Attribute %s do not exist", attribute_name)

    # Just a note - "native_value" is required property - so I need to implement it!
    # In first version we keep it simple and state is storing only native value (no attributes)
    @property
    def native_value(self):
        return self._attr_state

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value was reported in by the sensor"""
        return self._description.native_unit_of_measurement

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.warning("Coordinator is updated!!")
        attribute_name = f"_attr_{self._key}"
        if self._attr_available:
            self._attr_state = getattr(self._manager, attribute_name)
            self.async_write_ha_state()
        else:
            _LOGGER.warning("Attribute: %s do not exist", attribute_name)

    # TODO that precions set doesn't work. To be changed.
    # that is optionally property of entity. To check if this is used and working.
    @property
    def native_precision(self) -> int:
        return 2
