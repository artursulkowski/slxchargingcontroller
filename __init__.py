"""The Salix Charging Controller integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import SLXChgCtrlUpdateCoordinator
from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.NUMBER, Platform.SENSOR, Platform.SELECT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Salix Charging controller from a config entry."""

    coordinator = SLXChgCtrlUpdateCoordinator(hass, entry)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.unique_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # TODO  enable when setting up services
    #     async_setup_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    # TODO - add once we have services
    # if not hass.data[DOMAIN]:
    #    async_unload_services(hass)
    return unload_ok


# TODO - add later for handling config compatiblity
# async def async_migrate_entry(hass, config_entry: ConfigEntry):
