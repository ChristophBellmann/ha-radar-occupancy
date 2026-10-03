"""Config flow: one entry per room or sub-area."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector as sel

from .const import (
    CONF_BRIGHTNESS,
    CONF_DISTANCE,
    CONF_DOOR_FROM,
    CONF_DOOR_TO,
    CONF_HANDOVER,
    CONF_HANDOVER_ANYWHERE,
    CONF_KIND,
    CONF_LIGHT,
    CONF_PARENT,
    CONF_PRESENCE,
    CONF_RUN_ON,
    CONF_SAFETY_TIMEOUT,
    CONF_TAKEOVER_MIN,
    CONF_WINDOW_END,
    CONF_WINDOW_START,
    CONF_X,
    CONF_X_MAX,
    CONF_X_MIN,
    CONF_Y,
    CONF_Y_MAX,
    CONF_Y_MIN,
    DEFAULTS,
    DOMAIN,
    KIND_AREA,
    KIND_ROOM,
)


def _mm(maximum: int = 10000, minimum: int = 0, step: int = 50) -> sel.NumberSelector:
    return sel.NumberSelector(
        sel.NumberSelectorConfig(
            min=minimum, max=maximum, step=step, unit_of_measurement="mm", mode=sel.NumberSelectorMode.BOX
        )
    )


def _number(minimum: int, maximum: int, unit: str, step: int = 1) -> sel.NumberSelector:
    return sel.NumberSelector(
        sel.NumberSelectorConfig(
            min=minimum, max=maximum, step=step, unit_of_measurement=unit, mode=sel.NumberSelectorMode.BOX
        )
    )


def _entity(domain: str, device_class: str | None = None) -> sel.EntitySelector:
    config = sel.EntitySelectorConfig(domain=domain)
    if device_class:
        config = sel.EntitySelectorConfig(domain=domain, device_class=device_class)
    return sel.EntitySelector(config)


def _optional(key: str, values: dict[str, Any]) -> vol.Optional:
    """Optional with the current value suggested, so it can also be cleared."""
    if values.get(key) not in (None, ""):
        return vol.Optional(key, description={"suggested_value": values[key]})
    return vol.Optional(key)


def _default(key: str, values: dict[str, Any]) -> vol.Required:
    return vol.Required(key, default=values.get(key, DEFAULTS.get(key)))


def room_inputs(values: dict[str, Any]) -> dict:
    return {
        vol.Required(CONF_PRESENCE, default=values.get(CONF_PRESENCE, vol.UNDEFINED)): _entity("binary_sensor"),
        _optional(CONF_DISTANCE, values): _entity("sensor"),
        _optional(CONF_X, values): _entity("sensor"),
        _optional(CONF_Y, values): _entity("sensor"),
    }


def room_behaviour(values: dict[str, Any]) -> dict:
    return {
        _default(CONF_DOOR_FROM, values): _mm(),
        _default(CONF_DOOR_TO, values): _mm(),
        _default(CONF_SAFETY_TIMEOUT, values): _number(0, 1440, "min"),
        _default(CONF_HANDOVER, values): sel.BooleanSelector(),
        _default(CONF_HANDOVER_ANYWHERE, values): sel.BooleanSelector(),
        _default(CONF_TAKEOVER_MIN, values): _mm(3000),
    }


def area_box(values: dict[str, Any]) -> dict:
    return {
        vol.Required(CONF_X_MIN, default=values.get(CONF_X_MIN, vol.UNDEFINED)): _mm(10000, -10000),
        vol.Required(CONF_X_MAX, default=values.get(CONF_X_MAX, vol.UNDEFINED)): _mm(10000, -10000),
        vol.Required(CONF_Y_MIN, default=values.get(CONF_Y_MIN, vol.UNDEFINED)): _mm(),
        vol.Required(CONF_Y_MAX, default=values.get(CONF_Y_MAX, vol.UNDEFINED)): _mm(),
    }


def light_settings(values: dict[str, Any]) -> dict:
    return {
        _optional(CONF_LIGHT, values): _entity("light"),
        _default(CONF_BRIGHTNESS, values): _number(1, 100, "%"),
        _default(CONF_RUN_ON, values): _number(0, 3600, "s"),
        _default(CONF_WINDOW_START, values): sel.TimeSelector(),
        _default(CONF_WINDOW_END, values): sel.TimeSelector(),
    }


def _box_valid(data: dict[str, Any]) -> bool:
    return data[CONF_X_MIN] < data[CONF_X_MAX] and data[CONF_Y_MIN] < data[CONF_Y_MAX]


class RadarOccupancyConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return RadarOccupancyOptionsFlow()

    def _rooms(self) -> list[sel.SelectOptionDict]:
        return [
            sel.SelectOptionDict(value=e.entry_id, label=e.title)
            for e in self._async_current_entries()
            if e.data.get(CONF_KIND) == KIND_ROOM
        ]

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = ["room", "area"] if self._rooms() else ["room"]
        return self.async_show_menu(step_id="user", menu_options=options)

    async def async_step_room(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            name = user_input.pop(CONF_NAME)
            return self.async_create_entry(title=name, data={CONF_KIND: KIND_ROOM}, options={**DEFAULTS, **user_input})
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): sel.TextSelector(),
                **room_inputs({}),
                _optional(CONF_LIGHT, {}): _entity("light"),
            }
        )
        return self.async_show_form(step_id="room", data_schema=schema)

    async def async_step_area(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if _box_valid(user_input):
                name = user_input.pop(CONF_NAME)
                return self.async_create_entry(
                    title=name, data={CONF_KIND: KIND_AREA}, options={**DEFAULTS, **user_input}
                )
            errors["base"] = "invalid_box"
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): sel.TextSelector(),
                vol.Required(CONF_PARENT): sel.SelectSelector(sel.SelectSelectorConfig(options=self._rooms())),
                **area_box(user_input or {}),
                _optional(CONF_LIGHT, {}): _entity("light"),
            }
        )
        return self.async_show_form(step_id="area", data_schema=schema, errors=errors)


class RadarOccupancyOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.config_entry
        values = {**DEFAULTS, **entry.options}
        errors: dict[str, str] = {}
        is_area = entry.data.get(CONF_KIND) == KIND_AREA
        if user_input is not None:
            if not is_area or _box_valid(user_input):
                keep = {CONF_PARENT: entry.options[CONF_PARENT]} if is_area else {}
                return self.async_create_entry(data={**keep, **user_input})
            errors["base"] = "invalid_box"
            values.update(user_input)
        if is_area:
            schema = vol.Schema({**area_box(values), **light_settings(values)})
        else:
            schema = vol.Schema({**room_inputs(values), **room_behaviour(values), **light_settings(values)})
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
