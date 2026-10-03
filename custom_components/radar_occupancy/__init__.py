"""Radar Occupancy: room occupancy from radar targets that survives sitting still."""

from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol
from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CARD_URL, CONF_KIND, DOMAIN, KIND_AREA, KIND_HOME, KIND_PLAN, MAP_URL
from .manager import RadarOccupancyManager

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ROOM_PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]
AREA_PLATFORMS = [Platform.BINARY_SENSOR, Platform.SWITCH]
HOME_PLATFORMS = [Platform.NUMBER, Platform.SENSOR, Platform.SWITCH]

COORD = vol.All(vol.Coerce(float), vol.Range(min=-100000, max=100000))
ROOM = {vol.Required("room"): cv.string}


def _platforms(entry: ConfigEntry) -> list[Platform]:
    kind = entry.data.get(CONF_KIND)
    if kind == KIND_PLAN:
        return []
    if kind == KIND_HOME:
        return HOME_PLATFORMS
    return AREA_PLATFORMS if kind == KIND_AREA else ROOM_PLATFORMS


def get_manager(hass: HomeAssistant) -> RadarOccupancyManager:
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = RadarOccupancyManager(hass)
    return hass.data[DOMAIN]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    _register_services(hass)
    if getattr(hass, "http", None) is not None:
        hass.http.register_view(MapImageView())
        await _register_card(hass)
    return True


async def _register_card(hass: HomeAssistant) -> None:
    """Serve the position card and load it in every dashboard."""
    from homeassistant.components.http import StaticPathConfig

    path = Path(__file__).parent / "frontend" / "radar-occupancy-card.js"
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(path), False)])
    if "frontend" in hass.config.components:
        from homeassistant.components.frontend import add_extra_js_url

        version = (await hass.async_add_executor_job(path.stat)).st_mtime_ns
        add_extra_js_url(hass, f"{CARD_URL}?v={version}")


class MapImageView(HomeAssistantView):
    url = MAP_URL
    name = "api:radar_occupancy:map"
    requires_auth = True

    async def get(self, request: web.Request, floor: str) -> web.Response:
        manager: RadarOccupancyManager | None = request.app["hass"].data.get(DOMAIN)
        image = manager.home.map_image(floor) if manager and manager.home else None
        if not image:
            raise web.HTTPNotFound
        content, content_type = image
        return web.Response(body=content, content_type=content_type, headers={"Cache-Control": "private, max-age=300"})


def _register_services(hass: HomeAssistant) -> None:
    def home():
        manager = hass.data.get(DOMAIN)
        if manager is None or manager.home is None:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="no_home")
        return manager.home

    def room(call: ServiceCall) -> str:
        try:
            return hass.data[DOMAIN].resolve(call.data["room"])
        except KeyError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_room",
                translation_placeholders={"room": call.data["room"]},
            ) from err

    async def sample(call: ServiceCall) -> None:
        home().sample(room(call), call.data["x"], call.data["y"])

    async def undo_sample(call: ServiceCall) -> None:
        home().undo_sample(room(call))

    async def sample_area(call: ServiceCall) -> None:
        home().sample_area(room(call), call.data["sample"], call.data["area"])

    async def set_location(call: ServiceCall) -> None:
        home().set_location(room(call), call.data["x"], call.data["y"])

    async def set_orientation(call: ServiceCall) -> None:
        home().set_orientation(room(call), dict(call.data))

    async def set_boundary(call: ServiceCall) -> None:
        home().set_boundary(room(call), call.data["points"], call.data["kind"])

    async def reset_calibration(call: ServiceCall) -> None:
        home().reset_calibration(room(call))

    async def set_calibration(call: ServiceCall) -> None:
        home().set_calibration(room(call), call.data["calibration"])

    async def set_exit(call: ServiceCall) -> None:
        if call.data["clear"]:
            home().set_exit(room(call), None)
        elif "x" in call.data and "y" in call.data:
            home().set_exit(room(call), [call.data["x"], call.data["y"]])
        else:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="exit_point")

    async def set_door(call: ServiceCall) -> None:
        if call.data["clear"]:
            home().set_door(room(call), None, None)
            return
        if "x" not in call.data or "y" not in call.data or "to" not in call.data:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="door_point")
        other = call.data["to"]
        if other != "outside":
            try:
                other = hass.data[DOMAIN].resolve(other)
            except KeyError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="unknown_room",
                    translation_placeholders={"room": other},
                ) from err
        home().set_door(room(call), other, [call.data["x"], call.data["y"]])

    async def set_floor(call: ServiceCall) -> None:
        home().set_floor(call.data["camera"], call.data.get("name"), call.data.get("flip"))

    async def refresh_maps(call: ServiceCall) -> None:
        await home().async_load_maps()

    async def release(call: ServiceCall) -> None:
        manager = hass.data[DOMAIN]
        target = manager.rooms[room(call)]
        if target.room.presence:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="target_present")
        target.room.release()
        if manager.home:
            manager.home.release(target.entry_id)
        manager.notify(target)
        manager.evaluate()

    point_room = vol.Schema({**ROOM, vol.Required("x"): COORD, vol.Required("y"): COORD})
    schemas = {
        "sample": (sample, point_room),
        "undo_sample": (undo_sample, vol.Schema(ROOM)),
        "sample_area": (
            sample_area,
            vol.Schema(
                {
                    **ROOM,
                    vol.Required("sample"): vol.All(vol.Coerce(int), vol.Range(min=1, max=12)),
                    vol.Required("area"): vol.In(["room", "sub_area"]),
                }
            ),
        ),
        "set_location": (set_location, point_room),
        "set_orientation": (
            set_orientation,
            vol.Schema(
                {
                    **ROOM,
                    vol.Optional("heading"): vol.All(vol.Coerce(float), vol.Range(min=-720, max=720)),
                    vol.Optional("mirrored"): cv.boolean,
                    vol.Optional("mount"): vol.In(["wall", "ceiling"]),
                    vol.Optional("height"): vol.All(vol.Coerce(int), vol.Range(min=1500, max=5000)),
                    vol.Optional("clear", default=False): cv.boolean,
                }
            ),
        ),
        "set_boundary": (
            set_boundary,
            vol.Schema(
                {
                    **ROOM,
                    vol.Required("points"): vol.All([[COORD]], vol.Length(min=3, max=30)),
                    vol.Optional("kind", default="room"): vol.In(["room", "approach"]),
                }
            ),
        ),
        "reset_calibration": (reset_calibration, vol.Schema(ROOM)),
        "set_calibration": (set_calibration, vol.Schema({**ROOM, vol.Required("calibration"): dict})),
        "set_exit": (
            set_exit,
            vol.Schema(
                {
                    **ROOM,
                    vol.Optional("x"): COORD,
                    vol.Optional("y"): COORD,
                    vol.Optional("clear", default=False): cv.boolean,
                }
            ),
        ),
        "set_door": (
            set_door,
            vol.Schema(
                {
                    **ROOM,
                    vol.Optional("to"): cv.string,
                    vol.Optional("x"): COORD,
                    vol.Optional("y"): COORD,
                    vol.Optional("clear", default=False): cv.boolean,
                }
            ),
        ),
        "set_floor": (
            set_floor,
            vol.Schema(
                {
                    vol.Required("camera"): cv.entity_id,
                    vol.Optional("name"): cv.string,
                    vol.Optional("flip"): cv.boolean,
                }
            ),
        ),
        "refresh_maps": (refresh_maps, vol.Schema({})),
        "release": (release, vol.Schema(ROOM)),
    }

    async def simulation(call: ServiceCall) -> dict:
        from .simulation import room_route, simulate

        manager = get_manager(hass)
        try:
            route = call.data.get("route")
            if route is None:
                if not call.data.get("room"):
                    raise HomeAssistantError("Choose a room or supply a simulation route.")
                route = room_route(manager, call.data["room"])
            return simulate(
                manager, route, held=call.data["held"], ignore_restrictions=call.data["ignore_restrictions"]
            )
        except KeyError as err:
            raise HomeAssistantError("Unknown room in simulation route.") from err

    waypoint = vol.Schema(
        {
            vol.Optional("room"): cv.string,
            vol.Optional("x"): COORD,
            vol.Optional("y"): COORD,
            vol.Optional("seconds", default=3): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=120)),
        }
    )
    hass.services.async_register(
        DOMAIN,
        "simulate",
        simulation,
        schema=vol.Schema(
            {
                vol.Optional("room"): cv.string,
                vol.Optional("route"): vol.All([waypoint], vol.Length(min=1, max=30)),
                vol.Optional("held", default=False): cv.boolean,
                vol.Optional("ignore_restrictions", default=False): cv.boolean,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

    for name, (handler, schema) in schemas.items():
        hass.services.async_register(DOMAIN, name, handler, schema=schema)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    manager = get_manager(hass)
    entry.runtime_data = await manager.async_add(entry)
    await hass.config_entries.async_forward_entry_setups(entry, _platforms(entry))
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    manager.evaluate()
    return True


async def _options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, _platforms(entry))
    if unloaded:
        manager = get_manager(hass)
        manager.save()
        await manager.async_remove(entry.entry_id)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await get_manager(hass).async_forget(entry.entry_id)
