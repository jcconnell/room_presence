# Room Presence

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Debounced room presence tracking for Home Assistant with a Gantt timeline Lovelace card. Requires the [Bermuda BLE Trilateration](https://github.com/agittins/bermuda) integration.

## Features

- **Debounced sensor** — eliminates BLE flapping noise with a configurable hold time (5–300 s)
- **Session history** — tracks the last 50 room visits with entry time, exit time, and duration
- **Gantt card** — Lovelace card showing a 24 h room-presence timeline with hover tooltips
- **Auto-discovery** — finds the Bermuda area sensor automatically from the person entity's linked device trackers
- **Logbook integration** — room transitions appear in the HA logbook

## Requirements

- [Bermuda BLE Trilateration](https://github.com/agittins/bermuda) installed and configured
- At least one Person entity in Home Assistant

## Installation

### HACS (recommended)

1. In HACS, go to **Integrations** → **⋮** → **Custom repositories**
2. Add `https://github.com/jcconnell/room_presence` with category **Integration**
3. Install **Room Presence** and restart Home Assistant
4. Go to **Settings → Devices & Services → Add Integration → Room Presence**

The card JS is injected into the HA frontend automatically — no manual Lovelace resource step needed.

### Manual

Copy `custom_components/room_presence/` into your HA config `custom_components/` directory, then restart.

## Card Usage

```yaml
type: custom:room-presence-card
entity: sensor.your_name_room_presence
```

### Card Options

| Option | Default | Description |
|---|---|---|
| `entity` | **required** | Room presence sensor entity ID |
| `title` | person name | Override the card title |
| `hours` | `24` | Time window to display (hours) |
| `show_current_status` | `true` | Show current room and entry time |
| `show_legend` | `true` | Show room color legend |
| `min_duration_minutes` | `0` | Hide visits shorter than N minutes |
| `time_format` | `"12h"` | `"12h"` or `"24h"` |
| `row_height` | `34` | Gantt row height in pixels |
| `color_map` | `{}` | Custom room colors, e.g. `{"office": "#ff0000"}` |

### Example

```yaml
type: custom:room-presence-card
entity: sensor.jc_room_presence
hours: 12
time_format: 24h
min_duration_minutes: 2
color_map:
  office: "#f472b6"
  kitchen: "#34d399"
```

## Sensor Attributes

| Attribute | Description |
|---|---|
| `raw_room` | Unfiltered current Bermuda area |
| `previous_room` | Last committed room |
| `entered_at` | ISO timestamp when current room was committed |
| `duration_in_previous_room_s` | Seconds spent in the previous room |
| `debounce_seconds` | Configured hold time |
| `sessions` | List of up to 50 recent room visits |
| `person_entity` | Tracked person entity ID |
| `bermuda_sensor` | Source Bermuda area sensor |
| `bermuda_tracker` | Source Bermuda device tracker |
