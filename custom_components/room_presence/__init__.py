"""Room Presence integration."""
from __future__ import annotations

import logging
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]
CARD_URL = "/room_presence/room-presence-card.js"
_FRONTEND_REGISTERED = False
_LOVELACE_SCHEDULED = False


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Room Presence component (global, runs once)."""
    await _async_register_frontend(hass)
    _schedule_lovelace_registration(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Room Presence from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    await _async_register_frontend(hass)
    _schedule_lovelace_registration(hass)
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
    """Serve the frontend directory as a static path (idempotent)."""
    global _FRONTEND_REGISTERED
    if _FRONTEND_REGISTERED:
        return

    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")

    try:
        # HA 2023.9+ — async API with StaticPathConfig
        from homeassistant.components.http import StaticPathConfig  # noqa: PLC0415
        await hass.http.async_register_static_paths(
            [StaticPathConfig("/room_presence", frontend_dir, cache_headers=False)]
        )
    except (ImportError, AttributeError):
        # Fallback for HA < 2023.9
        try:
            hass.http.register_static_path(  # type: ignore[attr-defined]
                "/room_presence", frontend_dir, cache_headers=False
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Room Presence: could not register static path: %s", err)
            return
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Room Presence: could not register static path: %s", err)
        return

    _FRONTEND_REGISTERED = True
    _LOGGER.info("Room Presence frontend registered at /room_presence")


def _schedule_lovelace_registration(hass: HomeAssistant) -> None:
    """Schedule Lovelace resource registration — fires once per HA lifecycle."""
    global _LOVELACE_SCHEDULED
    if _LOVELACE_SCHEDULED:
        return
    _LOVELACE_SCHEDULED = True

    if hass.is_running:
        hass.async_create_task(_async_register_lovelace_resource(hass))
    else:
        @callback
        def _on_started(_event) -> None:
            hass.async_create_task(_async_register_lovelace_resource(hass))

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)


async def _async_register_lovelace_resource(hass: HomeAssistant) -> None:
    """Add the card JS as a Lovelace module resource if not already present."""
    try:
        lovelace_data = hass.data.get("lovelace")
        if not isinstance(lovelace_data, dict):
            _LOGGER.warning(
                "Room Presence: unexpected lovelace data type %s — "
                "add %s as a Lovelace resource manually",
                type(lovelace_data).__name__,
                CARD_URL,
            )
            return

        resources = lovelace_data.get("resources")
        if resources is None:
            _LOGGER.warning(
                "Room Presence: no resources collection in lovelace data (keys: %s) — "
                "add %s as a Lovelace resource manually",
                list(lovelace_data.keys()),
                CARD_URL,
            )
            return

        await resources.async_load()

        if any(CARD_URL in item.get("url", "") for item in resources.async_items()):
            _LOGGER.debug("Room Presence: Lovelace resource already registered")
            return

        await resources.async_create_item({"res_type": "module", "url": CARD_URL})
        _LOGGER.info("Room Presence card auto-registered as Lovelace resource")

    except Exception as err:  # noqa: BLE001
        _LOGGER.warning(
            "Room Presence: could not auto-register Lovelace resource "
            "(add %s manually): %s",
            CARD_URL,
            err,
        )
