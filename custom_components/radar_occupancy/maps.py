"""Floor maps: robot vacuum cameras (dreame_vacuum) or floor plan images.

A floor is a background image plus the transformation between image pixels
and map millimetres. A robot map also provides room outlines and doorways;
on a floor plan, outlines and doors are drawn on the position card.
Everything else in map mode works in map millimetres.
"""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from .const import CONF_IMAGE, CONF_IMAGE_WIDTH, MAP_URL, PLAN_PREFIX
from .geometry import doorway_approaches, doorways, segment_outline


class MapUnavailable(Exception):
    """The camera has no saved map (yet), or the floor plan cannot be read."""


class InvalidImage(ValueError):
    """Not a PNG or JPEG file."""


def image_info(content: bytes) -> tuple[int, int, str]:
    """Width, height and media type of a PNG or JPEG image."""
    if content[:8] == b"\x89PNG\r\n\x1a\n" and len(content) >= 24:
        width, height = struct.unpack(">II", content[16:24])
        return width, height, "image/png"
    if content[:2] == b"\xff\xd8":
        index = 2
        while index + 9 < len(content):
            if content[index] != 0xFF:
                index += 1
                continue
            marker = content[index + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                index += 2
                continue
            length = struct.unpack(">H", content[index + 2 : index + 4])[0]
            # Start of frame markers carry the size; C4, C8 and CC are not frames.
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                height, width = struct.unpack(">HH", content[index + 5 : index + 9])
                return width, height, "image/jpeg"
            index += 2 + length
    raise InvalidImage


def plan_path(hass: HomeAssistant, image: str) -> Path:
    """Absolute path of a floor plan image; must stay inside <config>/www."""
    www = Path(hass.config.path("www")).resolve()
    path = (www / image.lstrip("/").removeprefix("local/")).resolve()
    if www not in path.parents:
        raise InvalidImage
    return path


def read_plan(hass: HomeAssistant, image: str) -> tuple[bytes, int, int, str]:
    """Blocking: read and check a floor plan image."""
    path = plan_path(hass, image)
    try:
        content = path.read_bytes()
    except OSError as err:
        raise InvalidImage from err
    return (content, *image_info(content))


def plan_floor(entry_id: str, content: bytes, width: int, height: int, content_type: str, metres: float) -> dict:
    """Floor of a plan image. Map millimetres have Y up like robot maps."""
    scale = metres * 1000 / width  # mm per pixel
    w, h = width * scale, height * scale
    revision = hashlib.sha256(content + str(metres).encode()).hexdigest()[:16]
    return {
        "camera": PLAN_PREFIX + entry_id,
        "map_id": revision,
        "width": width,
        "height": height,
        "calibration_points": [
            {"vacuum": {"x": 0, "y": h}, "map": {"x": 0, "y": 0}},
            {"vacuum": {"x": w, "y": h}, "map": {"x": width, "y": 0}},
            {"vacuum": {"x": 0, "y": 0}, "map": {"x": 0, "y": height}},
        ],
        "image_path": MAP_URL.format(floor=entry_id) + f"?v={revision}",
        "rooms": [],
        "passages": [],
        "image": content,
        "content_type": content_type,
        "plan": True,
    }


def floor_key(camera_entity_id: str) -> str:
    return camera_entity_id.split(".", 1)[-1]


def segment_name(room: dict[str, Any]) -> str:
    return room.get("custom_name") or room.get("name") or str(room.get("room_id", ""))


def map_rooms(hass: HomeAssistant, camera_entity_id: str | None) -> list[str]:
    """Segment names offered by a map camera, for the config flow."""
    state = hass.states.get(camera_entity_id) if camera_entity_id else None
    rooms = (state.attributes.get("rooms") if state else None) or {}
    if not isinstance(rooms, dict):
        return []
    return sorted({segment_name(room) for room in rooms.values() if isinstance(room, dict)})


async def async_load_floor(
    hass: HomeAssistant, camera_entity_id: str, neighbours: dict[str, set[str] | None]
) -> dict[str, Any]:
    """Render the saved map without robot, path and labels and extract geometry.

    `neighbours`: segment name -> names reachable through a real door (None:
    every adjacent segment). Used for the door approach areas.
    """
    if camera_entity_id.startswith(PLAN_PREFIX):
        return await async_load_plan(hass, camera_entity_id.removeprefix(PLAN_PREFIX))
    from homeassistant.components import camera  # only with map mode; pulls in image libraries

    await camera.async_get_image(hass, camera_entity_id)
    component = hass.data.get("camera")
    entity = component.get_entity(camera_entity_id) if component else None
    if entity is None or getattr(entity, "_map_data", None) is None or not hasattr(entity, "_renderer"):
        raise MapUnavailable(camera_entity_id)
    attributes = entity.extra_state_attributes or {}
    room_metadata = attributes.get("rooms") or {}
    ids = {int(room.get("room_id", key)): segment_name(room) for key, room in room_metadata.items()}
    by_name = {name: room_id for room_id, name in ids.items()}

    def render() -> tuple:
        base = entity._renderer
        renderer = type(base)(
            color_scheme=entity._color_scheme,
            icon_set=entity._icon_set,
            hidden_map_objects=[
                "name",
                "icon",
                "name_background",
                "order",
                "suction_level",
                "water_volume",
                "cleaning_times",
                "cleaning_mode",
                "mopping_mode",
            ],
            robot_type=entity.device.capability.robot_type,
            low_resolution=base._low_resolution,
            square=base._square,
        )
        content = renderer.render_map(entity.device.get_map_for_render(entity._map_data), 0, 0)
        data = entity._map_data
        segments = set(data.segments or {})
        rooms = []
        for room_id, name in ids.items():
            allowed = neighbours.get(name)
            allowed_ids = None if allowed is None else {by_name[n] for n in allowed if n in by_name}
            rooms.append(
                {
                    "id": room_id,
                    "name": name,
                    "polygon": segment_outline(data.pixel_type, data.dimensions, room_id),
                    "approach_polygons": doorway_approaches(
                        data.pixel_type, data.dimensions, room_id, segments, allowed_ids
                    ),
                }
            )
        passages = [
            (ids.get(int(a)), ids.get(int(b)), point, width)
            for a, b, point, width in doorways(data.pixel_type, data.dimensions, segments)
        ]
        return content, renderer.calibration_points, rooms, passages

    content, points, rooms, passages = await hass.async_add_executor_job(render)
    if not content or not points:
        raise MapUnavailable(camera_entity_id)
    width, height = struct.unpack(">II", content[16:24])
    positions = {int(room.get("room_id", key)): room for key, room in room_metadata.items()}
    for room in rooms:
        meta = positions.get(room["id"], {})
        room["x"], room["y"] = meta.get("x"), meta.get("y")
    revision = hashlib.sha256(content).hexdigest()[:16]
    return {
        "camera": camera_entity_id,
        "map_id": attributes.get("map_id"),
        "width": width,
        "height": height,
        "calibration_points": points,
        "image_path": MAP_URL.format(floor=floor_key(camera_entity_id)) + f"?v={revision}",
        "rooms": [r for r in rooms if r["x"] is not None],
        "passages": [p for p in passages if p[0] and p[1]],
        "image": content,
        "content_type": "image/png",
    }


async def async_load_plan(hass: HomeAssistant, entry_id: str) -> dict[str, Any]:
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        raise MapUnavailable(entry_id)
    options = entry.options
    try:
        content, width, height, content_type = await hass.async_add_executor_job(read_plan, hass, options[CONF_IMAGE])
    except InvalidImage as err:
        raise MapUnavailable(entry_id) from err
    floor = plan_floor(entry_id, content, width, height, content_type, float(options[CONF_IMAGE_WIDTH]))
    floor["name"] = entry.title
    return floor
