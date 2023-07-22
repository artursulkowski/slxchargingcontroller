"""The Salix Charging Controller integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import SLXChgCtrlUpdateCoordinator
from .const import DOMAIN

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.NUMBER, Platform.SENSOR, Platform.SELECT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Salix Charging controller from a config entry."""

    # TODO 1. Create API instance
    coordinator = SLXChgCtrlUpdateCoordinator(hass, entry)
    # TODO 2. Validate the API connection (and authentication)
    # SKIP

    hass.data.setdefault(DOMAIN, {})

    # TODO 3. Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)
    hass.data[DOMAIN][entry.unique_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # TODO  enable when setting up services
    #     async_setup_services(hass)

    # TODO - this one I probably don't need to use at all
    # await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    # TODO - add once we have services
    # if not hass.data[DOMAIN]:
    #    async_unload_services(hass)
    return unload_ok


# TODO - add later for compatiblity
# async def async_migrate_entry(hass, config_entry: ConfigEntry):
