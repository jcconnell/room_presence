"""Config flow for Room Presence integration."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import (
    DOMAIN, CONF_PERSON_ENTITY, CONF_DEBOUNCE_SECONDS, DEFAULT_DEBOUNCE_SECONDS,
    CONF_MAX_SESSIONS, DEFAULT_MAX_SESSIONS,
)
from .helpers import get_person_entities, discover_sources


class RoomPresenceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Room Presence."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        person_entities = get_person_entities(self.hass)
        if not person_entities:
            return self.async_abort(reason="no_person_entities")

        configured = {
            entry.data[CONF_PERSON_ENTITY]
            for entry in self._async_current_entries()
        }
        available = {k: v for k, v in person_entities.items() if k not in configured}
        if not available:
            return self.async_abort(reason="all_persons_configured")

        if user_input is not None:
            person_entity = user_input[CONF_PERSON_ENTITY]
            sources = discover_sources(self.hass, person_entity)

            if not sources["bermuda_area_sensor"]:
                errors["base"] = "no_bermuda_sensor"
            else:
                await self.async_set_unique_id(person_entity)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{sources['person_name']} Room Presence",
                    data={
                        CONF_PERSON_ENTITY: person_entity,
                        CONF_DEBOUNCE_SECONDS: user_input[CONF_DEBOUNCE_SECONDS],
                        "person_name": sources["person_name"],
                        "bermuda_tracker": sources["bermuda_tracker"],
                        "bermuda_area_sensor": sources["bermuda_area_sensor"],
                    },
                )

        schema = vol.Schema({
            vol.Required(CONF_PERSON_ENTITY): vol.In(available),
            vol.Optional(CONF_DEBOUNCE_SECONDS, default=DEFAULT_DEBOUNCE_SECONDS): vol.All(
                int, vol.Range(min=5, max=300)
            ),
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return RoomPresenceOptionsFlow(config_entry)


class RoomPresenceOptionsFlow(config_entries.OptionsFlowWithConfigEntry):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema({
            vol.Optional(
                CONF_DEBOUNCE_SECONDS,
                default=self.config_entry.options.get(
                    CONF_DEBOUNCE_SECONDS,
                    self.config_entry.data.get(CONF_DEBOUNCE_SECONDS, DEFAULT_DEBOUNCE_SECONDS),
                ),
            ): vol.All(int, vol.Range(min=5, max=300)),
            vol.Optional(
                CONF_MAX_SESSIONS,
                default=self.config_entry.options.get(
                    CONF_MAX_SESSIONS,
                    self.config_entry.data.get(CONF_MAX_SESSIONS, DEFAULT_MAX_SESSIONS),
                ),
            ): vol.All(int, vol.Range(min=50, max=1000)),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
