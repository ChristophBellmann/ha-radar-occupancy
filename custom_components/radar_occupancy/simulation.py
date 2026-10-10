"""Bounded, isolated replay of map observations with the production controllers.

No HA states, services, config entries or persisted occupancy are modified.
Fades are reported as intentions, not hardware timing measurements.
"""

from __future__ import annotations

from copy import copy, deepcopy
from types import SimpleNamespace

from homeassistant.core import State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .const import REPORT_INTERVAL
from .geometry import distance, inside
from .home import covers
from .lights import LightController
from .tracking import Presence


class VirtualStates:
    def __init__(self, hass):
        self.values = {s.entity_id: State(s.entity_id, s.state, dict(s.attributes)) for s in hass.states.async_all()}

    def get(self, entity):
        return self.values.get(entity)

    def is_state(self, entity, state):
        value = self.get(entity)
        return value is not None and value.state == state


class ReplayLights(LightController):
    """Reuse decision logic; capture commands instead of scheduling real I/O."""

    def __init__(self, manager, ignore_restrictions):
        super().__init__(manager)
        self.commands = []
        self.switched = []  # decisions to switch on, for the latency report
        self.ignore_restrictions = ignore_restrictions

    def allowed(self, target):
        return self.ignore_restrictions or super().allowed(target)

    def mark(self, light):
        for entity in [light, *self.leaves(light)]:
            self.last_command[entity] = self.home.now

    def _call(self, service, data):
        self.commands.append({"time": self.home.now - self.home.start, "service": service, **data})
        entity = data["entity_id"]
        for leaf in {entity, *self.leaves(entity)}:
            old = self.hass.states.get(leaf)
            if old is None or old.state not in ("on", "off"):
                continue
            attrs = dict(old.attributes)
            if "brightness" in data:
                attrs["brightness"] = data["brightness"]
            elif "brightness_pct" in data:
                attrs["brightness"] = round(data["brightness_pct"] * 2.55)
            self.hass.states.values[leaf] = State(leaf, "on" if service == "turn_on" else "off", attrs)

    def switch_on(self, light, targets, direction):
        self.switched.append({"time": self.home.now, "light": light, "reason": direction})
        self.mark(light)
        factor = self.approach_factor() if direction == "approach" else 1
        for leaf, brightness in self.target_brightness(light, targets).items():
            self._call(
                "turn_on",
                {
                    "entity_id": leaf,
                    "brightness": max(1, round(brightness * factor)),
                    "reason": direction,
                    "fade_seconds": self.fade_time(direction),
                },
            )
        # The virtual group reflects the commanded leaves as well.
        old = self.hass.states.get(light)
        if old:
            self.hass.states.values[light] = State(light, "on", dict(old.attributes))

    def maybe_switch_off(self, light, st, now):
        self.mark(light)
        self._call("turn_off", {"entity_id": light, "fade_seconds": self.fade_time("off")})
        st.owned = False

    def start_fade(self, light, targets, direction):
        if direction == "off":
            self._call("turn_off", {"entity_id": light, "fade_seconds": self.fade_time("off")})
        else:
            self.switch_on(light, targets, direction)


class ReplayHome:
    def __init__(self, source, counts):
        self.entry = source.entry
        self.light_automation = True
        self.fade_in, self.fade_out = source.fade_in, source.fade_out
        self.start = self.now = dt_util.utcnow().timestamp()
        self.tracking = Presence(
            deepcopy(source.tracking.rooms), deepcopy(source.tracking.doors), counts, deepcopy(source.tracking.labels)
        )
        self.tracking.max_people = source.tracking.max_people

    def uses_map(self, room):
        return room in self.tracking.rooms

    def people(self, room):
        return self.tracking.count(room)

    def approaching(self, room):
        return self.now - self.tracking.approaching.get(room, -1e9) <= 2


def make_sandbox(manager, *, held=False, ignore_restrictions=False):
    """Create independent occupancy and light decision state."""
    if manager.home is None or not manager.home.tracking.rooms:
        raise HomeAssistantError("Simulation requires a loaded, calibrated home map.")
    sandbox = SimpleNamespace(
        hass=SimpleNamespace(states=VirtualStates(manager.hass)),
        saved={"brightness": dict(manager.saved.get("brightness", {}))},
        save=lambda: None,
    )
    sandbox.home = ReplayHome(manager.home, {r: 1 if held else 0 for r in manager.home.tracking.rooms})
    sandbox.targets = []
    for source in manager.targets:
        if not sandbox.home.uses_map(source.entry_id):
            continue
        target = copy(source)
        target.manager = sandbox
        target.only_dark = source.only_dark
        sandbox.targets.append(target)
    sandbox.lights = ReplayLights(sandbox, ignore_restrictions)
    # Start with virtual lights off. Real unavailable members remain unavailable.
    unavailable = []
    for light in sandbox.lights.groups():
        for entity in {light, *sandbox.lights.leaves(light)}:
            state = sandbox.hass.states.get(entity)
            if state and state.state in ("on", "off"):
                sandbox.hass.states.values[entity] = State(entity, "off", dict(state.attributes))
            else:
                unavailable.append(entity)
    sandbox.lights.evaluate(sandbox.home.now)
    return sandbox, unavailable


def observation(manager, home, waypoint):
    if not waypoint.get("room"):
        return None
    rid = manager.resolve(waypoint["room"])
    info = home.tracking.rooms.get(rid)
    if not info:
        raise HomeAssistantError("Selected room has no usable map calibration.")
    if "x" not in waypoint or "y" not in waypoint:
        raise HomeAssistantError("A room waypoint needs map x and y coordinates in millimetres.")
    point = [waypoint["x"], waypoint["y"]]
    transform = manager.home.rooms.get(rid, {}).get("transform")
    if transform:
        (a, b, c), (d, e, f) = transform
        det = a * e - b * d
        if det:
            dx, dy = point[0] - c, point[1] - f
            radar = [1000 * (e * dx - b * dy) / det, 1000 * (-d * dx + a * dy) / det]
            for aid, area in manager.areas.items():
                if area.parent and area.parent.entry_id == rid and area.area.contains(*radar):
                    return (info["floor"], point, aid)
    # The room selects the observing radar, just like a real sensor report.
    # Preserve its room assignment at uncertain edges instead of testing a
    # different (geometry-only) matching path from the live installation.
    polygon = info.get("polygon")
    assigned = rid if polygon and distance(point, polygon) <= 800 else None
    return (info["floor"], point, assigned)


WALL_REACH = 800  # mm beyond its room outline a sensor still reports someone (doorway, thin wall)


class RadarModel:
    """What the room sensors would report for the true positions of people.

    A sensor reports only people inside its field of view and its own room
    (plus WALL_REACH), once per report interval, each sensor at its own phase.
    Between reports production keeps evaluating the last coordinates; so does
    the model. Interval 0 without field of view is the ideal sensor of earlier
    versions: everybody is seen everywhere at every step."""

    def __init__(self, manager, start, interval=REPORT_INTERVAL, field_of_view=True):
        self.manager = manager
        self.interval = max(0.0, float(interval))
        self.field_of_view = field_of_view
        self.sensors = []
        rooms = manager.home.rooms if manager.home else {}
        for index, rid in enumerate(sorted(rooms)):
            info = rooms[rid]
            if not info.get("map_ready"):
                continue
            self.sensors.append(
                {
                    "room": rid,
                    "floor": info["floor"],
                    "polygon": info["polygon"],
                    "transform": info["transform"],
                    "mount": info.get("mount", "wall"),
                    "location": info.get("sensor_location"),
                    # Real sensors do not report in step.
                    "next": start + self.interval * ((index * 0.37) % 1),
                    "report": [],
                }
            )

    def sees(self, sensor, floor, point):
        polygon = sensor["polygon"]
        if floor != sensor["floor"] or (not inside(point, polygon) and distance(point, polygon) > WALL_REACH):
            return False
        return not self.field_of_view or covers(sensor["transform"], sensor["mount"], sensor["location"], point)

    def observe(self, home, now, people):
        """people: true (floor, point) of everybody in the home."""
        observations = []
        for sensor in self.sensors:
            if now + 1e-9 >= sensor["next"]:
                sensor["report"] = [list(p) for f, p in people if self.sees(sensor, f, p)]
                sensor["next"] = now + self.interval
            observations.extend(
                observation(self.manager, home, {"room": sensor["room"], "x": p[0], "y": p[1]})
                for p in sensor["report"]
            )
        return observations


class Latency:
    """Delay between somebody really entering a room and its light decision.

    `prelit`: switched on for an approach, `lit`: switched on for entering.
    Negative values: decided before the person was through the door. Device
    latency and the fade come on top."""

    WINDOW = 15.0  # s around entering in which a decision still belongs to it

    def __init__(self, manager, home, lights):
        self.home, self.lights = home, lights
        self.light_of = {t.entry_id: t.light for t in lights.manager.targets if t.light and t.auto_light}
        self.labels = {rid: t.entry.title for rid, t in manager.rooms.items()}
        self.where = {}
        self.entries = []

    def room(self, floor, point):
        rooms = self.home.tracking.rooms
        return next(
            (r for r, i in rooms.items() if i["floor"] == floor and i.get("polygon") and inside(point, i["polygon"])),
            None,
        )

    def update(self, now, people):
        """people: person id -> true (floor, point), None while away."""
        for pid, value in people.items():
            room = self.room(*value) if value else None
            if pid in self.where and self.where[pid] == room:
                continue
            first = pid not in self.where
            self.where[pid] = room
            light = self.light_of.get(room)
            if first or light is None:
                continue
            self.entries.append(
                {"person": pid, "room": room, "time": now, "light": light, "already_on": not self.lights.is_off(light)}
            )

    def report(self, start):
        result = []
        for index, entry in enumerate(self.entries):
            same = [e["time"] for i, e in enumerate(self.entries) if e["light"] == entry["light"] and i != index]
            begin = max([entry["time"] - self.WINDOW, *(t for t in same if t < entry["time"])])
            end = min([entry["time"] + self.WINDOW, *(t for t in same if t > entry["time"])])

            def first(reason, entry=entry, begin=begin, end=end):
                times = [
                    s["time"]
                    for s in self.lights.switched
                    if s["light"] == entry["light"] and s["reason"] == reason and begin < s["time"] <= end
                ]
                return round(min(times) - entry["time"], 2) if times else None

            prelit = first("approach")
            result.append(
                {
                    "person": entry["person"],
                    "room": self.labels.get(entry["room"], entry["room"]),
                    "time": round(entry["time"] - start, 2),
                    # On already for someone else, not pre-lit for this person.
                    "already_on": entry["already_on"] and (prelit is None or prelit > 0),
                    "prelit": prelit,
                    "lit": first("enter"),
                }
            )
        return result


def hold_off(manager):
    rooms = {rid for rid, target in manager.rooms.items() if not target.room.hold}
    return rooms | {aid for aid, area in manager.areas.items() if area.parent and area.parent.entry_id in rooms}


def simulate(manager, route, *, held=False, ignore_restrictions=False):
    """Instant dry run, preserved for scripting and regression tests."""
    sandbox, unavailable = make_sandbox(manager, held=held, ignore_restrictions=ignore_restrictions)
    timeline = []
    for waypoint in route:
        value = observation(manager, sandbox.home, waypoint)
        observations = [value] if value else []
        for _ in range(round(waypoint.get("seconds", 3) * 2)):
            sandbox.home.now += 0.5
            sandbox.home.tracking.step(sandbox.home.now, observations, hold_off(manager))
            sandbox.lights.evaluate(sandbox.home.now + 0.001)
        timeline.append(
            {
                "time": sandbox.home.now - sandbox.home.start,
                "people": dict(sandbox.home.tracking.counts),
                "lights": sandbox.lights.snapshot(),
            }
        )
    return {
        "dry_run": True,
        "commands": sandbox.lights.commands,
        "timeline": timeline,
        "unavailable_lights": sorted(set(unavailable)),
        "note": "Virtual light commands; no hardware, sensor or stored occupancy changes. Fade timing is not measured.",
    }


def room_route(manager, room):
    """Find an interior point without assuming polygon centroids are inside."""
    rid = manager.resolve(room)
    info = manager.home.tracking.rooms.get(rid) if manager.home else None
    polygon = (info or {}).get("polygon")
    if not polygon:
        raise HomeAssistantError("Selected room has no usable map calibration.")
    xs, ys = zip(*polygon)
    candidates = sorted(
        (
            [min(xs) + (max(xs) - min(xs)) * x / 20, min(ys) + (max(ys) - min(ys)) * y / 20]
            for x in range(1, 20)
            for y in range(1, 20)
            if inside([min(xs) + (max(xs) - min(xs)) * x / 20, min(ys) + (max(ys) - min(ys)) * y / 20], polygon)
        ),
        key=lambda p: (p[0] - (min(xs) + max(xs)) / 2) ** 2 + (p[1] - (min(ys) + max(ys)) / 2) ** 2,
    )
    point = candidates[0] if candidates else None
    if point is None:
        raise HomeAssistantError("No interior test point found. Supply an explicit route.")
    return [{"room": rid, "x": point[0], "y": point[1], "seconds": 4}, {"seconds": 5}]
