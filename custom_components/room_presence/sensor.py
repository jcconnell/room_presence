"""Room Presence sensor — debounced, sessions-tracking, logbook-integrated."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN, CONF_PERSON_ENTITY, CONF_DEBOUNCE_SECONDS, DEFAULT_DEBOUNCE_SECONDS,
    CONF_MAX_SESSIONS, DEFAULT_MAX_SESSIONS, IGNORE_STATES,
    ATTR_PREVIOUS_ROOM, ATTR_ENTERED_AT, ATTR_DURATION_IN_PREVIOUS,
    ATTR_RAW_ROOM, ATTR_PERSON_ENTITY, ATTR_BERMUDA_SENSOR,
    ATTR_BERMUDA_TRACKER, ATTR_DEBOUNCE_SECONDS, ATTR_SESSIONS,
)
from .helpers import discover_sources

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Room Presence sensor from config entry."""
    person_entity = entry.data[CONF_PERSON_ENTITY]
    person_name = entry.data.get("person_name", person_entity)
    bermuda_area_sensor = entry.data.get("bermuda_area_sensor")
    bermuda_tracker = entry.data.get("bermuda_tracker")
    debounce_seconds = entry.options.get(
        CONF_DEBOUNCE_SECONDS,
        entry.data.get(CONF_DEBOUNCE_SECONDS, DEFAULT_DEBOUNCE_SECONDS),
    )
    max_sessions = entry.options.get(
        CONF_MAX_SESSIONS,
        entry.data.get(CONF_MAX_SESSIONS, DEFAULT_MAX_SESSIONS),
    )

    if not bermuda_area_sensor:
        sources = discover_sources(hass, person_entity)
        bermuda_area_sensor = sources.get("bermuda_area_sensor")
        bermuda_tracker = sources.get("bermuda_tracker")

    if not bermuda_area_sensor:
        _LOGGER.error("Room Presence: no Bermuda area sensor found for %s", person_entity)
        return

    async_add_entities([
        RoomPresenceSensor(
            hass, entry, person_entity, person_name,
            bermuda_area_sensor, bermuda_tracker, debounce_seconds, max_sessions,
        )
    ], True)


class RoomPresenceSensor(SensorEntity):
    """
    Debounced room presence sensor.

    sessions attribute (list, newest first, max 50):
      {"room": str, "entered_at": iso, "left_at": iso|None, "duration_s": int|None}
    """

    _attr_has_entity_name = False
    _attr_icon = "mdi:map-marker-account"
    _attr_should_poll = False

    def __init__(self, hass, entry, person_entity, person_name,
                 bermuda_area_sensor, bermuda_tracker, debounce_seconds, max_sessions=DEFAULT_MAX_SESSIONS):
        self.hass = hass
        self._entry = entry
        self._person_entity = person_entity
        self._person_name = person_name
        self._bermuda_area_sensor = bermuda_area_sensor
        self._bermuda_tracker = bermuda_tracker
        self._debounce_seconds = debounce_seconds
        self._max_sessions = max_sessions

        self._attr_unique_id = f"{DOMAIN}_{person_entity}"
        self._attr_name = f"{person_name} Room Presence"

        self._committed_room: str | None = None
        self._pending_room: str | None = None
        self._raw_room: str | None = None
        self._previous_room: str | None = None
        self._entered_at: datetime | None = None
        self._duration_in_previous: int | None = None
        self._debounce_task: asyncio.Task | None = None
        self._sessions: list[dict] = []

        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._person_entity)},
            "name": f"{self._person_name} Room Presence",
            "manufacturer": "Room Presence",
            "model": "Debounced BLE Area Tracker",
            "entry_type": DeviceEntryType.SERVICE,
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._bermuda_area_sensor], self._handle_area_change
            )
        )
        source_state = self.hass.states.get(self._bermuda_area_sensor)
        if source_state and source_state.state not in IGNORE_STATES:
            room = source_state.state
            self._raw_room = room
            self._committed_room = room
            self._pending_room = room
            self._entered_at = dt_util.utcnow()
            self._attr_native_value = room
            self._open_session(room, self._entered_at)
            self._write_attributes()
            self.async_write_ha_state()

    @callback
    def _handle_area_change(self, event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        new_room = new_state.state
        self._raw_room = new_room

        if new_room in IGNORE_STATES:
            self._write_attributes()
            self.async_write_ha_state()
            return

        if new_room == self._committed_room:
            if self._debounce_task and not self._debounce_task.done():
                self._debounce_task.cancel()
                self._debounce_task = None
            self._pending_room = new_room
            self._write_attributes()
            self.async_write_ha_state()
            return

        if new_room == self._pending_room:
            return

        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

        self._pending_room = new_room
        self._write_attributes()
        self.async_write_ha_state()
        self._debounce_task = self.hass.async_create_task(
            self._commit_after_debounce(new_room)
        )

    async def _commit_after_debounce(self, room: str) -> None:
        try:
            await asyncio.sleep(self._debounce_seconds)
        except asyncio.CancelledError:
            return

        if room != self._pending_room:
            return

        previous = self._committed_room
        entered_previous = self._entered_at
        now = dt_util.utcnow()
        duration_s = int((now - entered_previous).total_seconds()) if entered_previous else None

        if self._sessions and self._sessions[0].get("left_at") is None:
            self._sessions[0]["left_at"] = now.isoformat()
            self._sessions[0]["duration_s"] = duration_s

        self._previous_room = previous
        self._committed_room = room
        self._entered_at = now
        self._duration_in_previous = duration_s
        self._attr_native_value = room

        self._open_session(room, now)
        self._write_attributes()
        self.async_write_ha_state()
        self._log_transition(room, previous, duration_s)

        _LOGGER.debug("%s: %s -> %s", self._person_name, previous, room)

    def _open_session(self, room: str, entered_at: datetime) -> None:
        self._sessions.insert(0, {
            "room": room,
            "entered_at": entered_at.isoformat(),
            "left_at": None,
            "duration_s": None,
        })
        if len(self._sessions) > self._max_sessions:
            self._sessions = self._sessions[:self._max_sessions]

    def _write_attributes(self) -> None:
        attrs: dict = {
            ATTR_PERSON_ENTITY: self._person_entity,
            ATTR_BERMUDA_SENSOR: self._bermuda_area_sensor,
            ATTR_DEBOUNCE_SECONDS: self._debounce_seconds,
            ATTR_RAW_ROOM: self._raw_room,
            ATTR_SESSIONS: self._sessions,
        }
        if self._bermuda_tracker:
            attrs[ATTR_BERMUDA_TRACKER] = self._bermuda_tracker
        if self._previous_room:
            attrs[ATTR_PREVIOUS_ROOM] = self._previous_room
        if self._entered_at:
            attrs[ATTR_ENTERED_AT] = self._entered_at.isoformat()
        if self._duration_in_previous is not None:
            attrs[ATTR_DURATION_IN_PREVIOUS] = self._duration_in_previous
        self._attr_extra_state_attributes = attrs

    def _log_transition(self, room, previous, duration_s):
        if previous and duration_s is not None:
            mins, secs = divmod(duration_s, 60)
            dur_str = f"{mins}m {secs}s" if mins and secs else (f"{mins}m" if mins else f"{secs}s")
            message = f"moved to {room} (was in {previous} for {dur_str})"
        elif previous:
            message = f"moved to {room} from {previous}"
        else:
            message = f"is in {room}"

        try:
            self.hass.components.logbook.async_log_entry(
                name=self._person_name,
                message=message,
                domain=DOMAIN,
                entity_id=self.entity_id,
            )
        except Exception:  # noqa: BLE001
            pass
