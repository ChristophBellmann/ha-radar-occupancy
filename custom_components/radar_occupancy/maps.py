"""Floor maps from robot vacuum cameras (dreame_vacuum).

A floor is the saved map of one robot camera: background image, the
transformation between image pixels and map millimetres, room outlines and
doorways between rooms. Everything else in map mode works in map millimetres.
"""

from __future__ import annotations

import hashlib
import struct
from typing import Any

from homeassistant.core import HomeAssistant

from .const import MAP_URL
from .geometry import doorway_approaches, doorways, segment_outline


class MapUnavailable(Exception):
    """The camera has no saved map (yet)."""


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
    }
