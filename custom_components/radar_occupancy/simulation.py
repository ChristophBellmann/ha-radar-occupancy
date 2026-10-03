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

from .geometry import inside
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
    return (info["floor"], point)


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
