"""Room Presence integration."""
from __future__ import annotations

import logging

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]
CARD_URL = "/room_presence/room-presence-card.js"
_FRONTEND_REGISTERED = False


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Room Presence component (global, runs once)."""
    await _async_register_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Room Presence from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    await _async_register_frontend(hass)
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


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Register the card JS as a static path and inject it into every HA frontend page."""
    global _FRONTEND_REGISTERED
    if _FRONTEND_REGISTERED:
        return

    card_path = hass.config.path(
        "custom_components", "room_presence", "frontend", "room-presence-card.js"
    )

    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, card_path, False)]
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Room Presence: could not register static path: %s", err)
        return

    # Inject into every HA frontend page — no manual Lovelace resource needed.
    # Follows the same pattern as browser_mod (mod_view.py).
    add_extra_js_url(hass, CARD_URL)

    _FRONTEND_REGISTERED = True
    _LOGGER.info("Room Presence: card registered at %s", CARD_URL)
