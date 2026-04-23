"""Constants for the Room Presence integration."""

DOMAIN = "room_presence"

CONF_PERSON_ENTITY = "person_entity"
CONF_DEBOUNCE_SECONDS = "debounce_seconds"

DEFAULT_DEBOUNCE_SECONDS = 30
MAX_SESSIONS = 50

IGNORE_STATES = {"unknown", "unavailable", "not_home"}

ATTR_PREVIOUS_ROOM = "previous_room"
ATTR_ENTERED_AT = "entered_at"
ATTR_DURATION_IN_PREVIOUS = "duration_in_previous_room_s"
ATTR_RAW_ROOM = "raw_room"
ATTR_PERSON_ENTITY = "person_entity"
ATTR_BERMUDA_SENSOR = "bermuda_sensor"
ATTR_BERMUDA_TRACKER = "bermuda_tracker"
ATTR_DEBOUNCE_SECONDS = "debounce_seconds"
ATTR_SESSIONS = "sessions"

BERMUDA_TRACKER_SUFFIX = "_bermuda_tracker"
BERMUDA_AREA_SUFFIX = "_area"
BERMUDA_PLATFORM = "bermuda"
