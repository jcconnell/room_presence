"""Room Presence integration."""
from __future__ import annotations

import logging
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]
_FRONTEND_REGISTERED = False


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Room Presence component (global, runs once)."""
    _register_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Room Presence from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    _register_frontend(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — reload entry."""
    await hass.config_entries.async_reload(entry.entry_id)


def _register_frontend(hass: HomeAssistant) -> None:
    """Register the frontend directory as a static path (sync, idempotent)."""
    global _FRONTEND_REGISTERED
    if _FRONTEND_REGISTERED:
        return

    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")

    try:
        hass.http.register_static_path(
            "/room_presence",
            frontend_dir,
            cache_headers=False,
        )
        _FRONTEND_REGISTERED = True
        _LOGGER.info("Room Presence frontend registered at /room_presence")
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Room Presence frontend path already registered: %s", err)
        _FRONTEND_REGISTERED = True
