"""Map mode: radar targets on robot vacuum maps and people counted through doors.

One home entry per installation. It loads the floor maps of the cameras the
rooms point to, keeps the calibration of every room sensor (radar -> map
millimetres), fuses the targets of all sensors into one picture and counts
people per room. A room becomes free only when everybody evidently walked out
through a door; people elsewhere say nothing about this room.

Rooms without a usable calibration (not placed, distorted, no outline) keep
the distance rule of the room entry, also in map mode.
"""

from __future__ import annotations

import json
import logging
import math
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from . import const
from .const import (
    CONF_DOOR_ROOMS,
    CONF_MAP_CAMERA,
    CONF_MAP_ROOM,
    CONF_PARENT,
    CONF_PRESENCE,
    CONF_X,
    CONF_X2,
    CONF_X3,
    CONF_Y,
    CONF_Y2,
    CONF_Y3,
    SIGNAL_HOME,
)
from .geometry import (
    GeometryError,
    distance,
    fit,
    inside,
    orientation,
    plausible,
    project,
    rigid,
    rms_error,
    valid_polygon,
)
from .maps import MapUnavailable, async_load_floor, floor_key
from .tracking import OUTSIDE, Door, Presence

if TYPE_CHECKING:
    from .manager import RadarOccupancyManager, RoomTarget

_LOGGER = logging.getLogger(__name__)

EDGE_TOLERANCE = 400  # mm: outline and calibration are a few decimetres off
MIN_DOOR_WIDTH = 500  # mm: narrower contacts between map rooms are no doors
APPROACH_RANGE = 1500  # mm: "in front of the room" for the zone display
TARGET_PAIRS = ((CONF_X, CONF_Y), (CONF_X2, CONF_Y2), (CONF_X3, CONF_Y3))


def effective_transform(calibration: dict[str, Any]) -> tuple[list | None, str | None]:
    """Location + heading win over the sample fit for wall sensors. A ceiling
    sensor cannot tell front from back across its antenna; there the samples
    stay authoritative."""
    if calibration.get("mount") != "ceiling" and calibration.get("location") and calibration.get("heading") is not None:
        return rigid(calibration["location"], calibration["heading"], calibration.get("mirrored", False)), "orientation"
    if calibration.get("transform"):
        return calibration["transform"], "samples"
    return None, None


def covers(transform, mount, location, point, reach=5000, half_angle=55) -> bool:
    """Is a map point safely inside a sensor's field of view?"""
    if mount == "ceiling":
        return bool(location) and math.dist(location, point) <= 2500
    (a, b, c), (d, e, f) = transform
    det = a * e - b * d
    if not det:
        return False
    dx, dy = point[0] - c, point[1] - f
    rx, ry = 1000 * (e * dx - b * dy) / det, 1000 * (-d * dx + a * dy) / det
    return 300 <= math.hypot(rx, ry) <= reach and ry > 0 and abs(math.degrees(math.atan2(rx, ry))) <= half_angle


def centroid(polygon):
    return [sum(p[0] for p in polygon) / len(polygon), sum(p[1] for p in polygon) / len(polygon)]


def door_allowed(a: str, b: str, lists: dict[str, list[str] | None]) -> bool:
    """A map contact is a door if a room lists the other side, or neither side restricts."""
    la, lb = lists.get(a), lists.get(b)
    if la and b in la or lb and a in lb:
        return True
    return not la and not lb


def number(state) -> float | None:
    if state is None:
        return None
    try:
        value = float(state.state)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    unit = state.attributes.get("unit_of_measurement", "mm")
    return value * {"mm": 1.0, "cm": 10.0, "m": 1000.0}.get(unit, 1.0)


class Home:
    def __init__(self, manager: RadarOccupancyManager, entry: ConfigEntry) -> None:
        self.manager = manager
        self.hass: HomeAssistant = manager.hass
        self.entry = entry
        settings = manager.saved.setdefault("home", {})
        self.map_mode: bool = settings.get("map_mode", True)
        self.light_automation: bool = settings.get("light_automation", True)
        # Off pauses handover between rooms of the distance rule, e.g. with visitors.
        self.handover: bool = settings.get("handover", True)
        self.fade_in: float = settings.get("fade_in", 2.0)
        self.fade_out: float = settings.get("fade_out", 3.0)
        data = manager.saved.setdefault("map", {})
        for key in ("calibrations", "floors", "exits", "doors", "people"):
            data.setdefault(key, {})
        self.data = data
        self.floors: dict[str, dict[str, Any]] = {}
        self.errors: dict[str, str] = {}
        self.tracking = Presence(counts=dict(data["people"]))
        self.signature = None
        self.rooms: dict[str, dict[str, Any]] = {}  # entry id -> room info of the last update
        self.ready: set[str] = set()  # rooms (and sub-areas) counted on the map
        self.overview: dict[str, Any] = {}
        self.targets_snapshot: list[dict[str, Any]] = []
        self._pending = None
        self._loading = None

    @property
    def entry_id(self) -> str:
        return self.entry.entry_id

    @property
    def calibrations(self) -> dict[str, dict[str, Any]]:
        return self.data["calibrations"]

    # Settings -----------------------------------------------------------

    def set_setting(self, key: str, value: Any) -> None:
        setattr(self, key, value)
        self.manager.saved["home"][key] = value
        if key == "light_automation":
            if not value:
                self.manager.lights.cancel_all()
            else:
                for st in self.manager.lights.state.values():
                    st.occupied = None
        self.manager.save()
        self.update()
        self.manager.evaluate()
        self.publish()

    # Queries used by targets and lights -----------------------------------

    def uses_map(self, entry_id: str) -> bool:
        return self.map_mode and entry_id in self.ready

    def people(self, entry_id: str) -> int:
        return self.tracking.count(entry_id)

    def reason(self, entry_id: str) -> str | None:
        """Stable reason code of the last change of a room's count."""
        reason = self.tracking.reasons.get(entry_id)
        return reason["code"] if reason else None

    def reason_rooms(self, entry_id: str) -> tuple[str | None, str | None]:
        """Rooms of the last change (display names; "outside" for outside the home)."""
        reason = self.tracking.reason(entry_id) or {}
        return reason.get("from"), reason.get("to")

    def approaching(self, entry_id: str) -> bool:
        if not self.uses_map(entry_id):
            return False
        return dt_util.utcnow().timestamp() - self.tracking.approaching.get(entry_id, -1e9) <= 2

    def release(self, entry_id: str) -> None:
        self.tracking.reset(entry_id, dt_util.utcnow().timestamp())
        for area_id, area in self.manager.areas.items():
            if area.entry.options.get(CONF_PARENT) == entry_id:
                self.tracking.reset(area_id, dt_util.utcnow().timestamp())
        self.update()

    # Maps ---------------------------------------------------------------

    def cameras(self) -> set[str]:
        return {
            r.entry.options[CONF_MAP_CAMERA]
            for r in self.manager.rooms.values()
            if r.entry.options.get(CONF_MAP_CAMERA)
        }

    def neighbours(self, camera: str) -> dict[str, set[str] | None]:
        result: dict[str, set[str] | None] = {}
        for room in self.manager.rooms.values():
            options = room.entry.options
            if options.get(CONF_MAP_CAMERA) == camera and options.get(CONF_MAP_ROOM):
                doors = options.get(CONF_DOOR_ROOMS) or []
                result[options[CONF_MAP_ROOM]] = set(doors) if doors else None
        return result

    async def async_load_maps(self, *_args) -> None:
        for camera in self.cameras():
            try:
                self.floors[camera] = await async_load_floor(self.hass, camera, self.neighbours(camera))
                self.errors.pop(camera, None)
            except MapUnavailable:
                self.errors[camera] = "map_unavailable"
            except Exception as err:  # noqa: BLE001 - a broken map must not stop the rest
                _LOGGER.warning("Loading the map of %s failed: %s", camera, err)
                self.errors[camera] = type(err).__name__
        for camera in list(self.floors):
            if camera not in self.cameras():
                self.floors.pop(camera)
        self.update()
        self.manager.evaluate()

    @callback
    def maps_outdated(self) -> bool:
        for camera in self.cameras():
            state = self.hass.states.get(camera)
            floor = self.floors.get(camera)
            if floor is None or (state and state.attributes.get("map_id") != floor.get("map_id")):
                return True
        return False

    @callback
    def reload_maps(self) -> None:
        if self._loading and not self._loading.done():
            return
        self._loading = self.hass.async_create_background_task(self.async_load_maps(), "radar_occupancy_maps")

    def unload(self) -> None:
        if self._pending:
            self._pending()
            self._pending = None
        if self._loading and not self._loading.done():
            self._loading.cancel()

    # Inputs -------------------------------------------------------------

    def inputs(self) -> set[str]:
        ids = set()
        for room in self.manager.rooms.values():
            options = room.entry.options
            for pair in TARGET_PAIRS:
                ids.update(options[k] for k in pair if options.get(k))
        return ids

    def live_targets(self, room: RoomTarget) -> list[dict[str, Any]]:
        """Fresh targets of a room sensor in its own coordinates."""
        options = room.entry.options
        if not self.hass.states.is_state(options[CONF_PRESENCE], STATE_ON):
            return []
        now = dt_util.utcnow()
        targets = []
        for index, (kx, ky) in enumerate(TARGET_PAIRS, 1):
            if not options.get(kx) or not options.get(ky):
                continue
            states = [self.hass.states.get(options[kx]), self.hass.states.get(options[ky])]
            x, y = (number(s) for s in states)
            if x is None or y is None or (x == 0 and y == 0):
                continue
            # last_reported also moves when the value stays the same.
            age = max((now - s.last_reported).total_seconds() for s in states)
            if age <= const.TARGET_MAX_AGE:
                targets.append({"target": index, "radar": [x, y]})
        return targets

    @callback
    def schedule(self) -> None:
        if self._pending:
            return

        @callback
        def run(_now) -> None:
            self._pending = None
            self.update()
            self.manager.evaluate()

        self._pending = async_call_later(self.hass, 0.15, run)

    # Update -------------------------------------------------------------

    @callback
    def update(self) -> None:
        now = dt_util.utcnow().timestamp()
        manager = self.manager
        rooms: dict[str, dict[str, Any]] = {}
        presence_rooms: dict[str, dict[str, Any]] = {}
        coverage = []
        observations = []
        all_targets = []
        labels = {}
        for room_id, room in manager.rooms.items():
            options = room.entry.options
            labels[room_id] = room.entry.title
            camera = options.get(CONF_MAP_CAMERA)
            floor = self.floors.get(camera) if camera else None
            calibration = self.calibrations.get(room_id, {})
            valid = (
                bool(floor)
                and calibration.get("map_id") is not None
                and calibration.get("map_id") == floor.get("map_id")
            )
            mount = calibration.get("mount", "wall")
            transform, source = effective_transform(calibration) if valid else (None, None)
            is_plausible = bool(transform) and plausible(transform)
            segment = next((r for r in (floor or {}).get("rooms", []) if r["name"] == options.get(CONF_MAP_ROOM)), {})
            manual = calibration.get("polygon") if valid else None
            polygon = (manual or segment.get("polygon") or []) if transform else []
            manual_approach = calibration.get("approach_polygon") if valid else None
            approach = (
                ([manual_approach] if manual_approach else segment.get("approach_polygons", [])) if transform else []
            )
            sub_areas = [(aid, a) for aid, a in manager.areas.items() if a.entry.options.get(CONF_PARENT) == room_id]
            targets = self.live_targets(room)
            for t in targets:
                t.update(sensor=room_id, room=room.entry.title, floor=camera)
                if not transform:
                    continue
                t["map"] = project(transform, *t["radar"])
                area = next(((aid, a) for aid, a in sub_areas if a.area.contains(*t["radar"])), None)
                if area:
                    t["area"], t["room"] = area[0], area[1].entry.title
                t["distance"] = round(distance(t["map"], polygon)) if polygon else None
                in_door = any(inside(t["map"], p) for p in approach)
                t["inside"] = (
                    (
                        False
                        if area
                        else (inside(t["map"], polygon) or (t["distance"] <= EDGE_TOLERANCE and not in_door))
                    )
                    if polygon
                    else None
                )
                if not area:
                    all_targets.append(t)
            map_ready = bool(transform and polygon and is_plausible)
            if map_ready:
                presence_rooms[room_id] = {"floor": camera, "polygon": polygon}
                coverage.append((camera, room_id, transform, mount, calibration.get("location")))
                for t in targets:
                    observations.append((camera, t["map"], t["area"]) if t.get("area") else (camera, t["map"]))
                for aid, area in sub_areas:
                    presence_rooms[aid] = {"floor": camera, "polygon": None, "parent": room_id}
                    labels[aid] = area.entry.title
            presence = self.hass.states.get(options[CONF_PRESENCE])
            available = bool(presence and presence.state in ("on", "off"))
            zone = "uncalibrated"
            if transform and polygon:
                if any(t.get("inside") for t in targets):
                    zone = "inside"
                elif any(
                    not t.get("area")
                    and (t.get("distance") or 0) <= APPROACH_RANGE
                    and any(inside(t["map"], p) for p in approach)
                    for t in targets
                ):
                    zone = "approach"
                else:
                    zone = "outside" if targets else "lost"
                if not is_plausible and zone != "lost":
                    zone = "unreliable"
                if not available:
                    zone = "unavailable"
            estimated = calibration.get("transform") if valid else None
            rooms[room_id] = {
                "id": room_id,
                "room": room.entry.title,
                "floor": camera,
                "map_room": options.get(CONF_MAP_ROOM) or (room.entry.title if floor and floor.get("plan") else None),
                "zone": zone,
                "available": available,
                "calibrated": bool(transform),
                "plausible": is_plausible,
                "map_ready": map_ready,
                "transform": transform,
                "transform_source": source,
                "sensor_location": calibration.get("location") if valid else None,
                "heading": calibration.get("heading") if valid else None,
                "mirrored": bool(calibration.get("mirrored")),
                "mount": mount,
                "mount_height": calibration.get("height", 2500),
                "estimated_orientation": orientation(estimated) if estimated and plausible(estimated) else None,
                "orientation_error_mm": rms_error(transform, calibration.get("samples", []))
                if source == "orientation"
                else None,
                "samples": len(calibration.get("samples", [])),
                "sample_points": calibration.get("samples", []),
                "error_mm": calibration.get("error_mm"),
                "polygon": polygon,
                "boundary_source": "manual" if manual else "map" if polygon else None,
                "approach_polygons": approach,
                "approach_source": "manual" if manual_approach else "map" if approach else None,
                "exits": self.data["exits"].get(room_id, []),
                "doors": [dict(d) for d in self.data["doors"].get(room_id, [])],
                "targets": targets,
                "sub_areas": [{"id": aid, "name": a.entry.title} for aid, a in sub_areas],
            }
        self.rooms = rooms
        self._configure(presence_rooms, coverage, labels)
        hold_off = {rid for rid, r in manager.rooms.items() if not r.room.hold}
        hold_off |= {aid for aid, info in presence_rooms.items() if info.get("parent") in hold_off}
        self.tracking.step(now, observations, hold_off)
        self.ready = set(presence_rooms)
        people = {rid: n for rid, n in self.tracking.counts.items() if rid in manager.rooms or rid in manager.areas}
        if people != self.data["people"]:
            self.data["people"] = people
            manager.save()
        self.targets_snapshot = all_targets
        self.publish()

    def _configure(self, rooms: dict[str, dict[str, Any]], coverage: list, labels: dict[str, str]) -> None:
        manager = self.manager
        doors: list[Door] = []
        for camera, floor in self.floors.items():
            segment_room = {}
            lists: dict[str, list[str] | None] = {}
            for rid, room in manager.rooms.items():
                options = room.entry.options
                if options.get(CONF_MAP_CAMERA) == camera and options.get(CONF_MAP_ROOM):
                    segment_room[options[CONF_MAP_ROOM]] = rid
                    lists[options[CONF_MAP_ROOM]] = options.get(CONF_DOOR_ROOMS) or None
            candidates = []
            for name_a, name_b, point, width in floor.get("passages", []):
                if width < MIN_DOOR_WIDTH or not door_allowed(name_a, name_b, lists):
                    continue
                a, b = segment_room.get(name_a, OUTSIDE), segment_room.get(name_b, OUTSIDE)
                if a != b:
                    candidates.append((a, b, [round(v) for v in point], False))
            for rid, points in self.data["exits"].items():
                if manager.rooms.get(rid) and manager.rooms[rid].entry.options.get(CONF_MAP_CAMERA) == camera:
                    candidates.extend((rid, OUTSIDE, [round(v) for v in p], True) for p in points)
            # Doors marked by hand, e.g. on a floor plan that has no room cells.
            for rid, marked in self.data["doors"].items():
                if manager.rooms.get(rid) and manager.rooms[rid].entry.options.get(CONF_MAP_CAMERA) == camera:
                    for door in marked:
                        other = door["to"] if door["to"] == OUTSIDE or door["to"] in manager.rooms else None
                        if other is not None:
                            candidates.append((rid, other, [round(v) for v in door["point"]], other == OUTSIDE))
            for a, b, point, exit_ in candidates:
                if any(side != OUTSIDE and side not in rooms for side in (a, b)):
                    continue
                covered = {}
                for side, other in ((a, b), (b, a)):
                    if side == OUTSIDE:
                        covered[side] = False
                        continue
                    # Probe 80 cm behind the door on `side`. Only the sensor of
                    # that room counts: the one of the room left behind no
                    # longer sees out once the door closes.
                    origin = centroid(rooms[other]["polygon"]) if other in rooms and rooms[other]["polygon"] else None
                    probe = point
                    if origin:
                        dx, dy = point[0] - origin[0], point[1] - origin[1]
                        length = math.hypot(dx, dy) or 1
                        probe = [point[0] + 800 * dx / length, point[1] + 800 * dy / length]
                    covered[side] = any(
                        covers(t, m, loc, probe) for f, r, t, m, loc in coverage if f == camera and r == side
                    )
                door = Door(a, b, camera, point, covered)
                door.exit = exit_
                doors.append(door)
        for rid, info in rooms.items():
            if info.get("parent"):
                doors.append(Door(info["parent"], rid, info["floor"], None, True))
        for rid in rooms:
            if rid not in self.tracking.counts:
                # New on the map: take over the current occupancy, never empty on suspicion.
                target = manager.target(rid)
                self.tracking.counts[rid] = 1 if target is not None and target.engine_occupied else 0
        signature = (
            json.dumps({k: (v["floor"], v["polygon"]) for k, v in rooms.items()}, sort_keys=True),
            tuple((d.a, d.b, d.floor, tuple(d.point or ()), json.dumps(d.covered, sort_keys=True)) for d in doors),
            json.dumps(labels, sort_keys=True),
        )
        if signature != self.signature:
            self.signature = signature
            self.tracking.configure(
                {k: {"floor": v["floor"], "polygon": v["polygon"]} for k, v in rooms.items()}, doors, labels
            )

    # Output -------------------------------------------------------------

    @callback
    def publish(self) -> None:
        async_dispatcher_send(self.hass, SIGNAL_HOME)

    def snapshot(self) -> dict[str, Any]:
        now = dt_util.utcnow().timestamp()
        manager = self.manager
        lights = manager.lights
        floors = {}
        for camera in self.cameras():
            info = self.floors.get(camera)
            settings = self.data["floors"].get(camera, {})
            base = {
                "camera": camera,
                "name": settings.get("name") or (info or {}).get("name"),
                "flip": bool(settings.get("flip")),
            }
            if info is None:
                floors[camera] = {**base, "error": self.errors.get(camera, "loading")}
                continue
            floors[camera] = {
                **base,
                **{k: info[k] for k in ("map_id", "width", "height", "calibration_points", "image_path")},
                "rooms": [{k: r[k] for k in ("name", "x", "y")} for r in info["rooms"]] or self._plan_labels(camera),
            }
        sensors = []
        for room_id, info in self.rooms.items():
            room = manager.rooms.get(room_id)
            if room is None:
                continue
            item = {k: v for k, v in info.items()}
            item.update(
                occupied=room.occupied,
                people=self.people(room_id) if room_id in self.ready else None,
                occupancy_reason=room.reason,
                occupancy_reason_rooms=self.reason_rooms(room_id) if room_id in self.ready else None,
                hold_enabled=room.room.hold,
                light=room.light,
                light_mode=lights.mode(room.light),
                entities=manager.entity_ids(room_id),
            )
            sensors.append(item)
        snap = self.tracking.snapshot(now)
        names = self.tracking.name
        return {
            "map_mode": self.map_mode,
            "light_automation": self.light_automation,
            "fade_in": self.fade_in,
            "fade_out": self.fade_out,
            "entities": manager.entity_ids(self.entry_id),
            "floors": floors,
            "sensors": sensors,
            "targets": self.targets_snapshot,
            "people": {names(k): v for k, v in snap["counts"].items()},
            "tracks": [{**t, "room": names(t["room"]) if t["room"] else None} for t in snap["tracks"]],
            "doors": [
                {**d, "a": names(d["a"]), "b": names(d["b"]), "covered": {names(k): v for k, v in d["covered"].items()}}
                if isinstance(d["covered"], dict)
                else {**d, "a": names(d["a"]), "b": names(d["b"])}
                for d in snap["doors"]
            ],
            "events": snap["events"],
            "lights": lights.snapshot(),
        }

    def _plan_labels(self, camera: str) -> list[dict[str, Any]]:
        """Room labels on a floor plan: centres of the drawn outlines."""
        labels = []
        for info in self.rooms.values():
            if info["floor"] == camera and info["polygon"]:
                x, y = centroid(info["polygon"])
                labels.append({"name": info["map_room"] or info["room"], "x": x, "y": y})
        return labels

    def total_people(self) -> int:
        return sum(self.tracking.count(rid) for rid in self.ready)

    # Calibration services --------------------------------------------------

    def _floor_of(self, room_id: str) -> dict[str, Any]:
        room = self.manager.rooms[room_id]
        camera = room.entry.options.get(CONF_MAP_CAMERA)
        if not camera:
            raise HomeAssistantError(translation_domain=const.DOMAIN, translation_key="no_map_camera")
        floor = self.floors.get(camera)
        if floor is None or floor.get("map_id") is None:
            raise HomeAssistantError(translation_domain=const.DOMAIN, translation_key="map_not_loaded")
        return floor

    def _current(self, room_id: str, map_id) -> dict[str, Any]:
        current = self.calibrations.get(room_id, {})
        if current and current.get("map_id") != map_id:
            raise HomeAssistantError(translation_domain=const.DOMAIN, translation_key="map_replaced")
        return current

    def _store(self, room_id: str, calibration: dict[str, Any]) -> None:
        self.calibrations[room_id] = calibration
        self.manager.save()
        self.update()
        self.manager.evaluate()

    def sample(self, room_id: str, x: float, y: float) -> None:
        floor = self._floor_of(room_id)
        targets = self.live_targets(self.manager.rooms[room_id])
        if len(targets) != 1:
            raise HomeAssistantError(translation_domain=const.DOMAIN, translation_key="one_target")
        current = self._current(room_id, floor["map_id"])
        sample = {"radar": targets[0]["radar"], "map": [x, y]}
        previous = current.get("samples", [])
        for old in previous:
            separation = min(math.dist(old["radar"], sample["radar"]), math.dist(old["map"], sample["map"]))
            if separation < 300:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key="sample_too_close",
                    translation_placeholders={"cm": str(round(separation / 10))},
                )
        samples = [*previous, sample]
        if len(samples) > 12:
            raise HomeAssistantError(translation_domain=const.DOMAIN, translation_key="too_many_samples")
        entry = {**current, "samples": samples, "map_id": floor["map_id"]}
        if len([s for s in samples if s.get("area") in (None, "room")]) >= 3:
            try:
                entry["transform"], entry["error_mm"] = fit(samples)
            except GeometryError as err:
                raise HomeAssistantError(translation_domain=const.DOMAIN, translation_key=err.code) from err
        self._store(room_id, entry)

    def undo_sample(self, room_id: str) -> None:
        current = dict(self.calibrations.get(room_id, {}))
        if not current.get("samples"):
            raise HomeAssistantError(translation_domain=const.DOMAIN, translation_key="no_samples")
        current["samples"] = current["samples"][:-1]
        current.pop("transform", None)
        current.pop("error_mm", None)
        if len([s for s in current["samples"] if s.get("area") in (None, "room")]) >= 3:
            try:
                current["transform"], current["error_mm"] = fit(current["samples"])
            except GeometryError:
                pass  # the remaining samples do not fit; calibrate again
        self._store(room_id, current)

    def sample_area(self, room_id: str, index: int, area: str) -> None:
        current = dict(self.calibrations.get(room_id, {}))
        samples = [dict(s) for s in current.get("samples", [])]
        if index < 1 or index > len(samples):
            raise HomeAssistantError(translation_domain=const.DOMAIN, translation_key="no_such_sample")
        samples[index - 1]["area"] = area
        try:
            current["transform"], current["error_mm"] = fit(samples)
        except GeometryError as err:
            raise HomeAssistantError(translation_domain=const.DOMAIN, translation_key=err.code) from err
        current["samples"] = samples
        self._store(room_id, current)

    def set_location(self, room_id: str, x: float, y: float) -> None:
        floor = self._floor_of(room_id)
        current = self._current(room_id, floor["map_id"])
        self._store(room_id, {**current, "map_id": floor["map_id"], "location": [x, y]})

    def set_orientation(self, room_id: str, data: dict[str, Any]) -> None:
        floor = self._floor_of(room_id)
        current = dict(self.calibrations.get(room_id, {}))
        if not current.get("location") or current.get("map_id") != floor["map_id"]:
            raise HomeAssistantError(translation_domain=const.DOMAIN, translation_key="place_first")
        if data.get("clear"):
            current.pop("heading", None)
            current.pop("mirrored", None)
        else:
            for key in ("mount", "height"):
                if key in data:
                    current[key] = data[key]
            if "heading" in data:
                current["heading"] = round(data["heading"] % 360, 1)
            if "mirrored" in data:
                current["mirrored"] = data["mirrored"]
        self._store(room_id, current)

    def set_boundary(self, room_id: str, points: list, kind: str) -> None:
        current = dict(self.calibrations.get(room_id, {}))
        if not effective_transform(current)[0]:
            raise HomeAssistantError(translation_domain=const.DOMAIN, translation_key="calibrate_first")
        try:
            current["approach_polygon" if kind == "approach" else "polygon"] = valid_polygon(points)
        except GeometryError as err:
            raise HomeAssistantError(translation_domain=const.DOMAIN, translation_key=err.code) from err
        self._store(room_id, current)

    def reset_calibration(self, room_id: str) -> None:
        self.calibrations.pop(room_id, None)
        self.manager.save()
        self.update()
        self.manager.evaluate()

    def set_calibration(self, room_id: str, calibration: dict[str, Any]) -> None:
        allowed = {
            "map_id",
            "samples",
            "transform",
            "error_mm",
            "location",
            "heading",
            "mirrored",
            "mount",
            "height",
            "polygon",
            "approach_polygon",
        }
        self._store(room_id, {k: v for k, v in calibration.items() if k in allowed})

    def set_exit(self, room_id: str, point: list[float] | None) -> None:
        if point is None:
            self.data["exits"].pop(room_id, None)
        else:
            self._floor_of(room_id)
            self.data["exits"].setdefault(room_id, []).append([round(point[0]), round(point[1])])
        self.manager.save()
        self.update()

    def set_door(self, room_id: str, other: str | None, point: list[float] | None) -> None:
        """Mark a door from this room to `other` (a room or OUTSIDE); None clears all."""
        if point is None:
            self.data["doors"].pop(room_id, None)
        else:
            self._floor_of(room_id)
            if other == room_id:
                raise HomeAssistantError(translation_domain=const.DOMAIN, translation_key="door_same_room")
            self.data["doors"].setdefault(room_id, []).append(
                {"to": other, "point": [round(point[0]), round(point[1])]}
            )
        self.manager.save()
        self.update()
        self.manager.evaluate()

    def set_floor(self, camera: str, name: str | None, flip: bool | None) -> None:
        settings = self.data["floors"].setdefault(camera, {})
        if name is not None:
            settings["name"] = name
        if flip is not None:
            settings["flip"] = flip
        self.manager.save()
        self.publish()

    def map_image(self, key: str) -> tuple[bytes, str] | None:
        for camera, floor in self.floors.items():
            if floor_key(camera) == key and floor.get("image"):
                return floor["image"], floor.get("content_type", "image/png")
        return None
