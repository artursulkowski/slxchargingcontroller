"""The Salix Charging Controller integration."""
from __future__ import annotations

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import SLXChgCtrlUpdateCoordinator
from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.NUMBER, Platform.SENSOR, Platform.SELECT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Salix Charging controller from a config entry."""

    coordinator = SLXChgCtrlUpdateCoordinator(hass)
    await coordinator.initialize(entry)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.unique_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # TODO  enable when setting up services
    #     async_setup_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    #    _LOGGER.debug("Attempting to unload entities from the %s integration", DOMAIN)

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    coordinator: SLXChgCtrlUpdateCoordinator = hass.data[DOMAIN][config_entry.unique_id]
    coordinator.cleanup()

    hass.data[DOMAIN].pop(config_entry.unique_id)
    return unload_ok


# async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
#     """Unload a config entry."""
#     if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
#         hass.data[DOMAIN].pop(entry.entry_id)
#     return unload_ok


# TODO - add later for handling config compatiblity
# async def async_migrate_entry(hass, config_entry: ConfigEntry):
