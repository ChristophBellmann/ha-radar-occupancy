"""Config flow: one entry per room or sub-area."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector as sel

from .const import (
    CONF_APPROACH_BRIGHTNESS,
    CONF_BRIGHTNESS,
    CONF_DISTANCE,
    CONF_DOOR_FROM,
    CONF_DOOR_ROOMS,
    CONF_DOOR_TO,
    CONF_HANDOVER,
    CONF_HANDOVER_ANYWHERE,
    CONF_IMAGE,
    CONF_IMAGE_WIDTH,
    CONF_KIND,
    CONF_LIGHT,
    CONF_MANUAL_OFF_RESET,
    CONF_MAP_CAMERA,
    CONF_MAP_ROOM,
    CONF_PARENT,
    CONF_PRESENCE,
    CONF_REMEMBER_BRIGHTNESS,
    CONF_RUN_ON,
    CONF_SAFETY_TIMEOUT,
    CONF_TAKEOVER_MIN,
    CONF_WINDOW_END,
    CONF_WINDOW_START,
    CONF_X,
    CONF_X2,
    CONF_X3,
    CONF_X_MAX,
    CONF_X_MIN,
    CONF_Y,
    CONF_Y2,
    CONF_Y3,
    CONF_Y_MAX,
    CONF_Y_MIN,
    DEFAULTS,
    DOMAIN,
    HOME_DEFAULTS,
    KIND_AREA,
    KIND_HOME,
    KIND_PLAN,
    KIND_ROOM,
    PLAN_PREFIX,
)
from .maps import InvalidImage, map_rooms, read_plan
from .radar import Candidate, suggest

CONF_DEVICE = "device"


def device_suggestions(hass, device_id: str) -> dict[str, str]:
    """Inputs suggested from the entities of a radar device."""
    registry = er.async_get(hass)
    candidates = [
        Candidate(
            entity.entity_id,
            (entity.name or entity.original_name or "").lower(),
            entity.device_class or entity.original_device_class,
            entity.disabled_by is not None,
        )
        for entity in er.async_entries_for_device(registry, device_id)
    ]
    return suggest(candidates)


def device_name(hass, device_id: str) -> str | None:
    """Area of the device, else its name: a sensible default room name."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return None
    area = ar.async_get(hass).async_get_area(device.area_id) if device.area_id else None
    return area.name if area else device.name_by_user or device.name


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


def room_inputs(values: dict[str, Any], further: bool = False) -> dict:
    schema = {
        vol.Required(CONF_PRESENCE, default=values.get(CONF_PRESENCE, vol.UNDEFINED)): _entity("binary_sensor"),
        _optional(CONF_DISTANCE, values): _entity("sensor"),
        _optional(CONF_X, values): _entity("sensor"),
        _optional(CONF_Y, values): _entity("sensor"),
    }
    if further:
        for key in (CONF_X2, CONF_Y2, CONF_X3, CONF_Y3):
            schema[_optional(key, values)] = _entity("sensor")
    return schema


def _names(options: list[str]) -> sel.SelectSelector:
    return sel.SelectSelector(sel.SelectSelectorConfig(options=options, custom_value=True, sort=True))


def map_sources(hass) -> list[sel.SelectOptionDict]:
    """Robot map cameras (they carry room metadata) and floor plan entries."""
    sources = [
        sel.SelectOptionDict(value=state.entity_id, label=state.name)
        for state in hass.states.async_all("camera")
        if isinstance(state.attributes.get("rooms"), dict)
    ]
    sources += [
        sel.SelectOptionDict(value=PLAN_PREFIX + entry.entry_id, label=entry.title)
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data.get(CONF_KIND) == KIND_PLAN
    ]
    return sources


def room_map(hass, values: dict[str, Any]) -> dict:
    """Map mode: further targets, map source and the room on it, real doors."""
    segments = map_rooms(hass, values.get(CONF_MAP_CAMERA))
    return {
        _optional(CONF_X2, values): _entity("sensor"),
        _optional(CONF_Y2, values): _entity("sensor"),
        _optional(CONF_X3, values): _entity("sensor"),
        _optional(CONF_Y3, values): _entity("sensor"),
        _optional(CONF_MAP_CAMERA, values): sel.SelectSelector(
            sel.SelectSelectorConfig(options=map_sources(hass), custom_value=True)
        ),
        _optional(CONF_MAP_ROOM, values): _names(segments),
        vol.Optional(CONF_DOOR_ROOMS, default=list(values.get(CONF_DOOR_ROOMS) or [])): sel.SelectSelector(
            sel.SelectSelectorConfig(options=segments, custom_value=True, multiple=True, sort=True)
        ),
    }


def home_settings(values: dict[str, Any]) -> dict:
    values = {**HOME_DEFAULTS, **values}
    return {
        _default(CONF_MANUAL_OFF_RESET, values): _number(0, 1440, "min"),
        _default(CONF_APPROACH_BRIGHTNESS, values): _number(1, 100, "%"),
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
        _default(CONF_REMEMBER_BRIGHTNESS, values): sel.BooleanSelector(),
    }


def plan_schema(values: dict[str, Any]) -> dict:
    return {
        vol.Required(CONF_IMAGE, default=values.get(CONF_IMAGE, vol.UNDEFINED)): sel.TextSelector(),
        vol.Required(CONF_IMAGE_WIDTH, default=values.get(CONF_IMAGE_WIDTH, vol.UNDEFINED)): sel.NumberSelector(
            sel.NumberSelectorConfig(
                min=1, max=500, step=0.01, unit_of_measurement="m", mode=sel.NumberSelectorMode.BOX
            )
        ),
    }


async def _plan_valid(hass, data: dict[str, Any]) -> bool:
    try:
        await hass.async_add_executor_job(read_plan, hass, data[CONF_IMAGE])
    except InvalidImage:
        return False
    return True


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
        if not any(e.data.get(CONF_KIND) == KIND_HOME for e in self._async_current_entries()):
            options.append("home")
        options.append("plan")
        return self.async_show_menu(step_id="user", menu_options=options)

    async def async_step_plan(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if await _plan_valid(self.hass, user_input):
                name = user_input.pop(CONF_NAME)
                return self.async_create_entry(title=name, data={CONF_KIND: KIND_PLAN}, options=user_input)
            errors[CONF_IMAGE] = "plan_image"
        schema = vol.Schema({vol.Required(CONF_NAME): sel.TextSelector(), **plan_schema(user_input or {})})
        return self.async_show_form(step_id="plan", data_schema=schema, errors=errors)

    async def async_step_home(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            await self.async_set_unique_id(KIND_HOME)
            self._abort_if_unique_id_configured()
            name = user_input.pop(CONF_NAME)
            return self.async_create_entry(
                title=name, data={CONF_KIND: KIND_HOME}, options={**HOME_DEFAULTS, **user_input}
            )
        schema = vol.Schema({vol.Required(CONF_NAME): sel.TextSelector()})
        return self.async_show_form(step_id="home", data_schema=schema)

    async def async_step_room(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """First the radar device (optional): its entities are suggested next."""
        errors: dict[str, str] = {}
        if user_input is not None:
            device = user_input.get(CONF_DEVICE)
            name = user_input.get(CONF_NAME) or (device_name(self.hass, device) if device else None)
            if name:
                self._room = {CONF_NAME: name, CONF_LIGHT: user_input.get(CONF_LIGHT)}
                self._suggested = device_suggestions(self.hass, device) if device else {}
                return await self.async_step_room_inputs()
            errors[CONF_NAME] = "name_required"
        schema = vol.Schema(
            {
                vol.Optional(CONF_DEVICE): sel.DeviceSelector(sel.DeviceSelectorConfig()),
                vol.Optional(CONF_NAME): sel.TextSelector(),
                _optional(CONF_LIGHT, {}): _entity("light"),
            }
        )
        return self.async_show_form(step_id="room", data_schema=schema, errors=errors)

    async def async_step_room_inputs(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            options = {**DEFAULTS, **user_input}
            if self._room.get(CONF_LIGHT):
                options[CONF_LIGHT] = self._room[CONF_LIGHT]
            return self.async_create_entry(title=self._room[CONF_NAME], data={CONF_KIND: KIND_ROOM}, options=options)
        schema = vol.Schema(room_inputs(self._suggested, further=True))
        return self.async_show_form(
            step_id="room_inputs",
            data_schema=schema,
            description_placeholders={"room": self._room[CONF_NAME], "found": str(len(self._suggested))},
        )

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
        if entry.data.get(CONF_KIND) == KIND_HOME:
            if user_input is not None:
                return self.async_create_entry(data=user_input)
            return self.async_show_form(step_id="home", data_schema=vol.Schema(home_settings(values)))
        if entry.data.get(CONF_KIND) == KIND_PLAN:
            if user_input is not None:
                if await _plan_valid(self.hass, user_input):
                    return self.async_create_entry(data=user_input)
                errors[CONF_IMAGE] = "plan_image"
            schema = vol.Schema(plan_schema(user_input or entry.options))
            return self.async_show_form(step_id="plan", data_schema=schema, errors=errors)
        if user_input is not None:
            if not is_area or _box_valid(user_input):
                keep = {CONF_PARENT: entry.options[CONF_PARENT]} if is_area else {}
                return self.async_create_entry(data={**keep, **user_input})
            errors["base"] = "invalid_box"
            values.update(user_input)
        if is_area:
            schema = vol.Schema({**area_box(values), **light_settings(values)})
        else:
            schema = vol.Schema(
                {
                    **room_inputs(values),
                    **room_behaviour(values),
                    **room_map(self.hass, values),
                    **light_settings(values),
                }
            )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
