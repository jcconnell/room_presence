/**
 * room-presence-card v4
 * Gantt timeline card for the Room Presence integration.
 *
 * Config options:
 *   entity               (required) sensor.xxx_room_presence
 *   title                (optional) card title -- defaults to person name
 *   hours                (optional) time window in hours, default 24
 *   show_current_status  (optional) show "Room since HH:MM" header line, default true
 *   show_legend          (optional) show color legend, default true
 *   min_duration_minutes (optional) hide segments shorter than N minutes, default 0
 *   time_format          (optional) "12h" or "24h", default "12h"
 *   row_height           (optional) row height in px, default 34
 *   color_map            (optional) {room: "#hex"} overrides
 */

const VERSION = "4.1.3";

const DEFAULT_COLORS = {
  "living room":    "#378ADD",
  "main bedroom":   "#7F77DD",
  "bedroom":        "#7F77DD",
  "guest room":     "#EF9F27",
  "guest bathroom": "#D4537E",
  "main bathroom":  "#1D9E75",
  "bathroom":       "#1D9E75",
  "kitchen":        "#34d399",
  "office":         "#f472b6",
  "hallway":        "#94a3b8",
  "garage":         "#a0a0a0",
};

const FALLBACK_PALETTE = [
  "#60a5fa","#a78bfa","#fb923c","#34d399","#f472b6",
  "#fbbf24","#4ade80","#f87171","#c084fc","#38bdf8",
];

function resolveColor(room, customMap, dynamicMap) {
  if (customMap && customMap[room]) return customMap[room];
  const key = room.toLowerCase();
  if (DEFAULT_COLORS[key]) return DEFAULT_COLORS[key];
  if (!dynamicMap[room]) {
    const idx = Object.keys(dynamicMap).length % FALLBACK_PALETTE.length;
    dynamicMap[room] = FALLBACK_PALETTE[idx];
  }
  return dynamicMap[room];
}

function fmtTime(iso, use24h) {
  const d = new Date(iso);
  if (use24h) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  }
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", hour12: true });
}

function fmtDur(s) {
  if (s === null || s === undefined) return "now";
  const m = Math.round(s / 60);
  if (m < 1) return "<1m";
  if (m < 60) return m + "m";
  const h = Math.floor(m / 60), rm = m % 60;
  return rm ? `${h}h ${rm}m` : `${h}h`;
}

function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ----------------------------------------------------------
// Main card
// ----------------------------------------------------------
class RoomPresenceCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._dynamicColorMap = {};
  }

  setConfig(config) {
    if (!config.entity) throw new Error("room-presence-card: 'entity' is required");
    this._config = {
      hours: 24,
      show_current_status: true,
      show_legend: true,
      min_duration_minutes: 0,
      time_format: "12h",
      row_height: 34,
      color_map: {},
      ...config,
    };
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    const cfg = this._config;
    const stateObj = this._hass.states[cfg.entity];

    if (!stateObj) {
      this.shadowRoot.innerHTML = `
        <ha-card><div style="padding:16px;color:var(--error-color)">
          Entity not found: ${esc(cfg.entity)}
        </div></ha-card>`;
      return;
    }

    const sessions = stateObj.attributes.sessions || [];

    // Derive clean person name -- strip 'Room Presence' suffix from friendly_name
    const rawFriendlyName = stateObj.attributes.friendly_name || cfg.entity;
    const personName = rawFriendlyName.replace(/\s*Room Presence\s*$/i, '').trim() || rawFriendlyName;

    // Use cfg.title if explicitly set, otherwise the cleaned person name
    const displayTitle = cfg.title || personName;

    const currentRoom = stateObj.state;
    const rawRoom = stateObj.attributes.raw_room;
    const enteredAt = stateObj.attributes.entered_at;
    const use24h = cfg.time_format === "24h";
    const ROW_H = Number(cfg.row_height) || 34;
    const ROW_GAP = 6;
    const minMs = (Number(cfg.min_duration_minutes) || 0) * 60 * 1000;

    const now = Date.now();
    const windowMs = cfg.hours * 3600 * 1000;
    const tStart = now - windowMs;

    // Filter and map sessions to renderable segments
    const segments = sessions
      .filter(s => {
        const entered = new Date(s.entered_at).getTime();
        const left = s.left_at ? new Date(s.left_at).getTime() : now;
        if (left <= tStart) return false;
        if (minMs > 0 && s.left_at) {
          const dur = left - Math.max(entered, tStart);
          if (dur < minMs) return false;
        }
        return true;
      })
      .map(s => ({
        room: s.room,
        start: Math.max(new Date(s.entered_at).getTime(), tStart),
        end: s.left_at ? new Date(s.left_at).getTime() : now,
        enteredAt: s.entered_at,
        leftAt: s.left_at,
        durationS: s.duration_s,
        isCurrent: !s.left_at,
      }));

    // Unique rooms in order of appearance
    const rooms = [...new Set(segments.map(s => s.room))];

    // Fixed viewBox geometry -- no calc() in SVG attributes
    const VB_W = 600;
    const LABEL_W = 112;
    const TRACK_W = VB_W - LABEL_W;
    const PAD_T = 8;
    const PAD_B = 30;
    const svgH = Math.max(rooms.length * (ROW_H + ROW_GAP) + PAD_T + PAD_B, 60);
    const TICKS = 6;

    // Build track + segment rows
    let rowsSVG = "";
    rooms.forEach((room, ri) => {
      const y = PAD_T + ri * (ROW_H + ROW_GAP);
      const cy = y + ROW_H / 2;
      const color = resolveColor(room, cfg.color_map, this._dynamicColorMap);

      rowsSVG += `
        <text class="row-label" x="${LABEL_W - 8}" y="${cy}">${esc(room)}</text>
        <rect class="track" x="${LABEL_W}" y="${y + 2}" width="${TRACK_W}" height="${ROW_H - 4}" rx="3"/>
      `;

      segments.filter(s => s.room === room).forEach(seg => {
        const x = LABEL_W + ((seg.start - tStart) / windowMs) * TRACK_W;
        const w = Math.max(((seg.end - seg.start) / windowMs) * TRACK_W, 1.5);
        const dataTip = JSON.stringify({
          room: seg.room, from: seg.enteredAt, to: seg.leftAt,
          dur: seg.durationS, current: seg.isCurrent,
        }).replace(/'/g, "&#39;");

        rowsSVG += `
          <rect class="seg${seg.isCurrent ? " seg-current" : ""}"
            x="${x.toFixed(2)}" y="${y + 2}" rx="3"
            width="${w.toFixed(2)}" height="${ROW_H - 4}"
            fill="${color}" opacity="${seg.isCurrent ? 1 : 0.82}"
            data-tip='${dataTip}'/>
        `;
      });
    });

    // Axis ticks -- all plain numbers, no calc()
    let ticksSVG = "";
    let axisLabelsSVG = "";
    for (let i = 0; i <= TICKS; i++) {
      const frac = i / TICKS;
      const x = LABEL_W + frac * TRACK_W;
      const t = new Date(tStart + windowMs * frac);
      const anchor = i === 0 ? "start" : i === TICKS ? "end" : "middle";
      ticksSVG += `<line class="tick" x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${PAD_T}" y2="${svgH - PAD_B}"/>`;
      axisLabelsSVG += `<text class="axis-tick" text-anchor="${anchor}" x="${x.toFixed(1)}" y="${svgH - 8}">${fmtTime(t.toISOString(), use24h)}</text>`;
    }

    // Legend
    const legendHTML = cfg.show_legend ? `
      <div class="legend">
        ${rooms.map(r => {
          const c = resolveColor(r, cfg.color_map, this._dynamicColorMap);
          return `<span class="legend-item">
            <span class="legend-dot" style="background:${c}"></span>${esc(r)}
          </span>`;
        }).join("")}
      </div>` : "";

    // Status line
    const statusHTML = cfg.show_current_status ? (() => {
      let s = esc(currentRoom);
      if (enteredAt) s += ` <span class="since">since ${fmtTime(enteredAt, use24h)}</span>`;
      if (rawRoom && rawRoom !== currentRoom && !["unknown","unavailable"].includes(rawRoom)) {
        s += ` <span class="raw">(raw: ${esc(rawRoom)})</span>`;
      }
      return `<span class="status">${s}</span>`;
    })() : "";

    this.shadowRoot.innerHTML = `
      <ha-card>
        <style>
          :host { display: block; }
          ha-card { padding: 12px 16px 8px; box-sizing: border-box; }
          .header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; flex-wrap: wrap; gap: 4px; }
          .title { font-size: 14px; font-weight: 500; color: var(--primary-text-color); }
          .status { font-size: 12px; color: var(--secondary-text-color); }
          .since { opacity: 0.85; }
          .raw { opacity: 0.55; font-size: 11px; }
          .legend { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 8px; }
          .legend-item { display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--secondary-text-color); }
          .legend-dot { width: 9px; height: 9px; border-radius: 2px; flex-shrink: 0; }
          .gantt-wrap { position: relative; width: 100%; }
          svg { display: block; width: 100%; overflow: visible; }
          .row-label { font-size: 11px; fill: var(--secondary-text-color); text-anchor: end; dominant-baseline: middle; }
          .track { fill: var(--divider-color, rgba(128,128,128,0.12)); }
          .tick { stroke: var(--divider-color, rgba(128,128,128,0.15)); stroke-width: 0.5; }
          .axis-tick { font-size: 10px; fill: var(--disabled-text-color); }
          .seg { cursor: pointer; transition: opacity .1s, filter .1s; }
          .seg:hover { opacity: 1 !important; filter: brightness(1.15); }
          .seg-current { stroke: var(--primary-color); stroke-width: 1.5; }
          .tooltip {
            position: absolute;
            background: var(--card-background-color, #1c1c1e);
            border: 1px solid var(--divider-color);
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 11px;
            pointer-events: none;
            z-index: 100;
            white-space: nowrap;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            color: var(--primary-text-color);
            display: none;
            min-width: 140px;
          }
          .tt-room { font-size: 12px; font-weight: 500; margin-bottom: 3px; }
          .tt-time, .tt-dur { color: var(--secondary-text-color); margin-top: 1px; }
          .footer { font-size: 10px; color: var(--disabled-text-color); margin-top: 4px; text-align: right; }
        </style>

        <div class="header">
          <span class="title">${esc(displayTitle)}</span>
          ${statusHTML}
        </div>

        ${legendHTML}

        <div class="gantt-wrap" id="wrap">
          <svg viewBox="0 0 600 ${svgH}" preserveAspectRatio="none" style="width:100%;height:${svgH}px;">
            ${ticksSVG}
            ${rowsSVG}
            ${axisLabelsSVG}
          </svg>
          <div class="tooltip" id="tt">
            <div class="tt-room" id="tt-room"></div>
            <div class="tt-time" id="tt-time"></div>
            <div class="tt-dur" id="tt-dur"></div>
          </div>
        </div>

        <div class="footer">Last ${cfg.hours}h &mdash; ${window.matchMedia("(hover: none)").matches ? "tap" : "hover"} for details</div>
      </ha-card>
    `;

    this._bindTooltips();
  }

  _bindTooltips() {
    const wrap = this.shadowRoot.querySelector("#wrap");
    const tt = this.shadowRoot.querySelector("#tt");
    const ttRoom = this.shadowRoot.querySelector("#tt-room");
    const ttTime = this.shadowRoot.querySelector("#tt-time");
    const ttDur = this.shadowRoot.querySelector("#tt-dur");
    const use24h = this._config.time_format === "24h";

    const showTip = (clientX, clientY, data) => {
      ttRoom.textContent = data.room;
      ttTime.textContent = data.current
        ? `${fmtTime(data.from, use24h)} -> now`
        : `${fmtTime(data.from, use24h)} -> ${fmtTime(data.to, use24h)}`;
      ttDur.textContent = data.current ? "current room" : fmtDur(data.dur);

      const wRect = wrap.getBoundingClientRect();
      let x = clientX - wRect.left;
      let y = clientY - wRect.top - 72;
      if (y < 4) y = clientY - wRect.top + 8;

      tt.style.display = "block";
      tt.style.left = Math.max(0, Math.min(x - 70, wRect.width - 160)) + "px";
      tt.style.top = y + "px";
    };

    const hideTip = () => { tt.style.display = "none"; };

    this.shadowRoot.querySelectorAll(".seg").forEach(seg => {
      const data = JSON.parse(seg.dataset.tip);

      seg.addEventListener("mousemove", e => showTip(e.clientX, e.clientY, data));
      seg.addEventListener("mouseleave", hideTip);

      seg.addEventListener("touchstart", e => {
        e.preventDefault();
        const t = e.touches[0];
        showTip(t.clientX, t.clientY, data);
      }, { passive: false });
      seg.addEventListener("touchend", () => {
        setTimeout(hideTip, 1800);
      });
      seg.addEventListener("touchcancel", hideTip);
    });

    // Hide tooltip on touch outside the chart
    wrap.addEventListener("touchstart", e => {
      if (!e.target.classList.contains("seg")) hideTip();
    }, { passive: true });
  }

  getCardSize() {
    const sessions = this._hass?.states[this._config?.entity]?.attributes?.sessions || [];
    const rooms = [...new Set(sessions.map(s => s.room))];
    return Math.max(2, Math.ceil(rooms.length * 0.7) + 2);
  }

  static getConfigElement() {
    return document.createElement("room-presence-card-editor");
  }

  static getStubConfig() {
    return {
      entity: "sensor.jc_room_presence",
      hours: 24,
      show_current_status: true,
      show_legend: true,
      min_duration_minutes: 0,
      time_format: "12h",
      row_height: 34,
    };
  }
}

if (!customElements.get("room-presence-card")) {
  customElements.define("room-presence-card", RoomPresenceCard);
}

// ----------------------------------------------------------
// UI Editor
// ----------------------------------------------------------
class RoomPresenceCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
  }

  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    // Populate entity picker options on first set
    if (!this._rendered) this._render();
  }

  _render() {
    this._rendered = true;
    const cfg = this._config;

    this.shadowRoot.innerHTML = `
      <style>
        .editor { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
        label { font-size: 12px; color: var(--secondary-text-color); display: block; margin-bottom: 3px; }
        input, select { width: 100%; padding: 8px 10px; border-radius: 6px;
          border: 1px solid var(--divider-color); background: var(--card-background-color);
          color: var(--primary-text-color); font-size: 13px; box-sizing: border-box; }
        input:focus, select:focus { outline: 2px solid var(--primary-color); outline-offset: -1px; }
        .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .toggle-row { display: flex; align-items: center; justify-content: space-between; }
        .toggle-row label { margin: 0; font-size: 13px; color: var(--primary-text-color); }
        .hint { font-size: 11px; color: var(--disabled-text-color); margin-top: 2px; }
        ha-switch { --mdc-theme-secondary: var(--primary-color); }
      </style>
      <div class="editor">

        <div>
          <label>Entity *</label>
          <select id="entity">${this._entityOptions()}</select>
        </div>

        <div>
          <label>Title</label>
          <input id="title" type="text" placeholder="Defaults to person name" value="${esc(cfg.title || "")}"/>
        </div>

        <div class="row">
          <div>
            <label>Time window (hours)</label>
            <input id="hours" type="number" min="1" max="168" value="${cfg.hours ?? 24}"/>
          </div>
          <div>
            <label>Min duration filter (minutes)</label>
            <input id="min_duration_minutes" type="number" min="0" max="60" value="${cfg.min_duration_minutes ?? 0}"/>
            <div class="hint">Hide segments shorter than this</div>
          </div>
        </div>

        <div class="row">
          <div>
            <label>Time format</label>
            <select id="time_format">
              <option value="12h" ${(cfg.time_format ?? "12h") === "12h" ? "selected" : ""}>12h (3:00 PM)</option>
              <option value="24h" ${cfg.time_format === "24h" ? "selected" : ""}>24h (15:00)</option>
            </select>
          </div>
          <div>
            <label>Row height (px)</label>
            <input id="row_height" type="number" min="20" max="80" value="${cfg.row_height ?? 34}"/>
          </div>
        </div>

        <div class="toggle-row">
          <label>Show current status</label>
          <input id="show_current_status" type="checkbox" ${cfg.show_current_status !== false ? "checked" : ""}
            style="width:auto;"/>
        </div>

        <div class="toggle-row">
          <label>Show legend</label>
          <input id="show_legend" type="checkbox" ${cfg.show_legend !== false ? "checked" : ""}
            style="width:auto;"/>
        </div>

      </div>
    `;

    this.shadowRoot.querySelectorAll("input, select").forEach(el => {
      el.addEventListener("change", () => this._valueChanged());
    });
  }

  _entityOptions() {
    if (!this._hass) return `<option value="${esc(this._config.entity || "")}">${esc(this._config.entity || "")}</option>`;
    const sensors = Object.keys(this._hass.states)
      .filter(e => e.startsWith("sensor.") && e.endsWith("_room_presence"));
    if (!sensors.includes(this._config.entity) && this._config.entity) {
      sensors.unshift(this._config.entity);
    }
    return sensors.map(e =>
      `<option value="${esc(e)}" ${e === this._config.entity ? "selected" : ""}>${esc(e)}</option>`
    ).join("");
  }

  _valueChanged() {
    const get = id => this.shadowRoot.getElementById(id);
    const newConfig = {
      ...this._config,
      entity: get("entity").value,
      hours: parseInt(get("hours").value) || 24,
      min_duration_minutes: parseInt(get("min_duration_minutes").value) || 0,
      time_format: get("time_format").value,
      row_height: parseInt(get("row_height").value) || 34,
      show_current_status: get("show_current_status").checked,
      show_legend: get("show_legend").checked,
    };
    const title = get("title").value.trim();
    if (title) newConfig.title = title;
    else delete newConfig.title;

    this._config = newConfig;
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: newConfig }, bubbles: true, composed: true }));
  }
}

if (!customElements.get("room-presence-card-editor")) {
  customElements.define("room-presence-card-editor", RoomPresenceCardEditor);
}

// Register with HA card picker
window.customCards = window.customCards || [];
window.customCards.push({
  type: "room-presence-card",
  name: "Room Presence Gantt",
  description: "Gantt timeline showing room presence history. Requires the Room Presence integration.",
  preview: false,
  documentationURL: "https://github.com/jcconnell/room_presence",
});

console.info(`%c ROOM-PRESENCE-CARD %c v${VERSION} `, "color:#fff;background:#378ADD;font-weight:bold", "color:#378ADD;background:#fff");
