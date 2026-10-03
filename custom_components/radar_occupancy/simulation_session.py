"""Animated multi-person replay; optional real light control with restoration."""

from __future__ import annotations

import asyncio
import math
from copy import deepcopy
from datetime import timedelta

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .lights import AUTO, LightController
from .simulation import hold_off, make_sandbox, observation

COLORS = ["#db36b4", "#ee7518", "#8548ec", "#e13f55", "#008f91", "#8b9611", "#467dea", "#98502b"]


class LiveLights(LightController):
    def __init__(self, manager, owner, ignore_restrictions):
        super().__init__(manager)
        self.owner = owner
        self.ignore_restrictions = ignore_restrictions

    def active(self):
        return self.owner.running and self.owner.manager.home is not None and self.owner.manager.home.light_automation

    def allowed(self, target):
        return self.ignore_restrictions or super().allowed(target)

    @callback
    def evaluate(self, now):
        previous = {light: state.occupied for light, state in self.state.items()}
        super().evaluate(now)
        for light, targets in self.groups().items():
            state = self.state.get(light)
            if (
                previous.get(light) is False
                and state
                and state.occupied
                and state.mode == AUTO
                and not self.is_off(light)
                and any(self.allowed(t) for t in targets if t.occupied)
            ):
                self.switch_on(light, [t for t in targets if t.occupied], "enter")


class SimulationSession:
    def __init__(self, manager, persons, *, live_lights=False, ignore_restrictions=False):
        self.manager = manager
        self.live_lights = live_lights
        self.sandbox, self.unavailable = make_sandbox(manager, ignore_restrictions=ignore_restrictions)
        self.paths = []
        ids = set()
        for index, person in enumerate(persons):
            pid = person["id"]
            if pid in ids:
                raise HomeAssistantError("Simulation person IDs must be unique.")
            ids.add(pid)
            path, elapsed = [], 0.0
            previous = None
            for point in person["route"]:
                elapsed += point.get("seconds", 3)
                value = observation(manager, self.sandbox.home, point)
                if (
                    previous
                    and value
                    and previous[0] == value[0]
                    and math.dist(previous[1], value[1]) / point.get("seconds", 3) > 2500
                ):
                    raise HomeAssistantError("Simulation path is too fast. Add travel time or closer waypoints.")
                path.append((elapsed, (value[0], value[1], manager.resolve(point["room"])) if value else None))
                previous = value
            self.paths.append({"id": pid, "color": COLORS[index % len(COLORS)], "path": path})
        self.duration = max(p["path"][-1][0] for p in self.paths)
        self.started = dt_util.utcnow().timestamp()
        self.running = False
        self.targets = []
        self.originals = {}
        self.manual = set()
        self._unsub = None
        self._unsub_shutdown = None
        self.stopping = False
        self._stop_lock = asyncio.Lock()
        self.error = None
        self.warnings = []
        self.automatic = False
        if live_lights:
            self.sandbox.hass = manager.hass
            self.sandbox.lights = LiveLights(self.sandbox, self, ignore_restrictions)
            for light in self.sandbox.lights.groups():
                for leaf in self.sandbox.lights.leaves(light):
                    state = manager.hass.states.get(leaf)
                    if state and state.state in ("on", "off"):
                        self.originals[leaf] = (state.state, dict(state.attributes))

    async def start(self):
        if self.live_lights:
            if not self.manager.home.light_automation:
                raise HomeAssistantError("Enable light automation before starting a real light simulation.")
            tasks = [
                *self.manager.lights.fades.values(),
                *(s.off_task for s in self.manager.lights.state.values() if s.off_task),
            ]
            self.manager.lights.cancel_all()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        self.running = True
        self.started = dt_util.utcnow().timestamp()
        self.sandbox.home.start = self.sandbox.home.now = self.started
        self.sandbox.lights.evaluate(self.started)
        if self.live_lights:
            # The test takes control of configured lamps while it runs.
            for state in self.sandbox.lights.state.values():
                state.owned = True
        self._unsub = async_track_time_interval(self.manager.hass, self.tick, timedelta(seconds=0.5))

        async def shutdown(_event):
            await self.stop()

        self._unsub_shutdown = self.manager.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)
        self.tick(dt_util.utcnow())

    @staticmethod
    def position(path, elapsed):
        previous = None
        start = 0.0
        for end, value in path:
            if elapsed <= end:
                if previous and value and previous[0] == value[0]:
                    ratio = (elapsed - start) / (end - start)
                    return (
                        value[0],
                        [previous[1][i] + (value[1][i] - previous[1][i]) * ratio for i in range(2)],
                        value[2],
                    )
                return value
            previous, start = value, end
        return path[-1][1]

    @callback
    def tick(self, now):
        if not self.running:
            return
        if self.live_lights and (not self.manager.home or not self.manager.home.light_automation):
            self.manager.hass.async_create_task(self.stop())
            return
        elapsed = max(0, now.timestamp() - self.started)
        if elapsed > self.duration:
            self.manager.hass.async_create_task(self.stop())
            return
        self.sandbox.home.now = now.timestamp()
        targets, observations = [], []
        for person in self.paths:
            value = self.position(person["path"], elapsed)
            if value:
                # Recompute sub-area membership at the interpolated position.
                value = observation(
                    self.manager, self.sandbox.home, {"room": value[2], "x": value[1][0], "y": value[1][1]}
                )
                observations.append(value)
                targets.append({"person": person["id"], "color": person["color"], "floor": value[0], "map": value[1]})
        self.targets = targets
        self.sandbox.home.tracking.step(now.timestamp(), observations, hold_off(self.manager))
        self.sandbox.lights.evaluate(now.timestamp() + 0.001)
        if self.manager.home:
            self.manager.home.publish()

    def light_changed(self, event):
        if event.time_fired.timestamp() < self.started:
            return
        light = self.sandbox.lights
        entity = event.data["entity_id"]
        state = event.data.get("new_state")
        if state:
            ctx = state.context
            if ctx.user_id is not None or (
                entity not in light.internal
                and now_age(light.last_command.get(entity, -1e9)) >= 10
                and (ctx.id not in light.contexts and ctx.parent_id not in light.contexts)
            ):
                self.manual.update([entity, *light.leaves(entity)])
        light.light_changed(event)

    async def stop(self):
        async with self._stop_lock:
            await self._stop()

    async def _stop(self):
        if self.stopping:
            return
        self.stopping = True
        if self._unsub:
            self._unsub()
            self._unsub = None
        if self._unsub_shutdown:
            self._unsub_shutdown()
            self._unsub_shutdown = None
        self.running = False
        lights = self.sandbox.lights
        tasks = [*lights.fades.values(), *(s.off_task for s in lights.state.values() if s.off_task)]
        lights.cancel_all()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self.live_lights:
            for entity, (state, attrs) in self.originals.items():
                if entity in self.manual:
                    continue
                data = {"entity_id": entity}
                if state == "on" and attrs.get("brightness"):
                    data["brightness"] = attrs["brightness"]
                try:
                    await self.manager.hass.services.async_call(
                        "light",
                        "turn_on" if state == "on" else "turn_off",
                        data,
                        blocking=True,
                        context=lights.context(),
                    )
                except Exception:  # noqa: BLE001 - restore remaining lamps even if one fails
                    self.error = "Some light states could not be restored; check device availability."
        if self.live_lights:
            self.manager.lights.contexts.extend(lights.contexts)
            self.manager.lights.last_command.update(lights.last_command)
        self.targets = []
        self.manager.simulation_result = self.snapshot()
        if self.manager.simulation is self:
            self.manager.simulation = None
        if self.live_lights:
            self.manager.lights.cancel_all()
        if self.manager.home:
            self.manager.home.publish()
        self.manager.evaluate()

    def snapshot(self):
        return {
            "running": self.running,
            "automatic": self.automatic,
            "live_lights": self.live_lights,
            "elapsed": round(max(0, dt_util.utcnow().timestamp() - self.started), 1),
            "duration": self.duration,
            "targets": deepcopy(self.targets),
            "routes": [
                {
                    "id": p["id"],
                    "color": p["color"],
                    "points": [{"floor": v[0], "map": v[1]} if v else None for _, v in p["path"]],
                }
                for p in self.paths
            ],
            "warnings": self.warnings,
            "people": dict(self.sandbox.home.tracking.counts),
            "lights": self.sandbox.lights.snapshot(),
            "unavailable_lights": self.unavailable,
            "error": self.error,
        }


def now_age(then):
    return dt_util.utcnow().timestamp() - then
