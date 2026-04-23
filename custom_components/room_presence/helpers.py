"""Helper functions for Room Presence integration."""
from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import BERMUDA_TRACKER_SUFFIX, BERMUDA_AREA_SUFFIX, BERMUDA_PLATFORM

_LOGGER = logging.getLogger(__name__)


def get_person_entities(hass: HomeAssistant) -> dict[str, str]:
    """Return {entity_id: friendly_name} for all person entities."""
    return {
        state.entity_id: state.attributes.get("friendly_name", state.entity_id)
        for state in hass.states.async_all("person")
    }


def find_bermuda_tracker(hass: HomeAssistant, person_entity_id: str) -> str | None:
    """Find the Bermuda device_tracker linked to a person entity."""
    state = hass.states.get(person_entity_id)
    if not state:
        return None
    for tracker in state.attributes.get("device_trackers", []):
        if tracker.endswith(BERMUDA_TRACKER_SUFFIX):
            return tracker
    return None


def find_bermuda_area_sensor(hass: HomeAssistant, bermuda_tracker: str) -> str | None:
    """
    Derive the Bermuda area sensor from a Bermuda device_tracker.

    device_tracker.jc_mobile_private_ble_bermuda_tracker
      -> sensor.jc_mobile_private_ble_area
    """
    if not bermuda_tracker.startswith("device_tracker."):
        return None
    base = bermuda_tracker[len("device_tracker."):]
    if base.endswith(BERMUDA_TRACKER_SUFFIX):
        base = base[: -len(BERMUDA_TRACKER_SUFFIX)]

    candidate = f"sensor.{base}{BERMUDA_AREA_SUFFIX}"
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(candidate)
    if entry and entry.platform == BERMUDA_PLATFORM:
        return candidate

    # Fallback: search registry by partial name
    for reg_entry in ent_reg.entities.values():
        if (
            reg_entry.platform == BERMUDA_PLATFORM
            and reg_entry.entity_id.endswith(BERMUDA_AREA_SUFFIX)
            and not reg_entry.entity_id.endswith("_area_last_seen")
            and base in reg_entry.entity_id
        ):
            _LOGGER.debug("Fallback Bermuda area sensor: %s", reg_entry.entity_id)
            return reg_entry.entity_id

    return None


def discover_sources(hass: HomeAssistant, person_entity_id: str) -> dict:
    """Discover all presence sources for a person entity."""
    state = hass.states.get(person_entity_id)
    person_name = (
        state.attributes.get("friendly_name", person_entity_id) if state else person_entity_id
    )
    bermuda_tracker = find_bermuda_tracker(hass, person_entity_id)
    bermuda_area_sensor = (
        find_bermuda_area_sensor(hass, bermuda_tracker) if bermuda_tracker else None
    )
    return {
        "person_name": person_name,
        "bermuda_tracker": bermuda_tracker,
        "bermuda_area_sensor": bermuda_area_sensor,
    }
