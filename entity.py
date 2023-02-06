from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


class SlxChgCtrlEntity(CoordinatorEntity):
    """base entity class for Salix Charging Controller entities"""

    def __init__(self, coordinator):
        """Initialize the base entity."""
        super().__init__(coordinator)

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, "SlxCharger")},
            manufacturer="Salix Planters",
            model="SLX Charger Ctrl",
            name="Salix Charger Controller",
        )
