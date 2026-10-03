"""Runtime shared by all rooms: inputs, handover, light control, persistence."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DISTANCE,
    CONF_DOOR_FROM,
    CONF_DOOR_TO,
    CONF_HANDOVER,
    CONF_HANDOVER_ANYWHERE,
    CONF_KIND,
    CONF_LIGHT,
    CONF_PARENT,
    CONF_PRESENCE,
    CONF_SAFETY_TIMEOUT,
    CONF_TAKEOVER_MIN,
    CONF_X,
    CONF_X_MAX,
    CONF_X_MIN,
    CONF_Y,
    CONF_Y_MAX,
    CONF_Y_MIN,
    DEFAULTS,
    KIND_AREA,
    KIND_HOME,
    KIND_PLAN,
    SIGNAL_UPDATE,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .engine import Area, Room, RoomConfig, handover
from .home import Home
from .lights import LightController, LightState, in_window  # noqa: F401 - in_window re-exported

_LOGGER = logging.getLogger(__name__)


_TO_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0}


def _number(state: State | None) -> float | None:
    """Numeric state in millimetres; sensors without a unit are taken as mm."""
    if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, ""):
        return None
    try:
        value = float(state.state)
    except ValueError:
        return None
    return value * _TO_MM.get(state.attributes.get("unit_of_measurement", "mm"), 1.0)


def _option(entry: ConfigEntry, key: str) -> Any:
    return entry.options.get(key, DEFAULTS.get(key))


class Target:
    """Something with an occupancy and optionally a light: a room or a sub-area."""

    def __init__(self, entry: ConfigEntry, manager: RadarOccupancyManager) -> None:
        self.entry = entry
        self.manager = manager
        self.auto_light = True
        self.only_dark = True
        self.was_occupied = False
        self.published: tuple | None = None  # what the entities show

    @property
    def entry_id(self) -> str:
        return self.entry.entry_id

    @property
    def light(self) -> str | None:
        return self.entry.options.get(CONF_LIGHT) or None

    @property
    def owned(self) -> bool:
        """We switched the light on (or someone entered), so we switch it off."""
        return self.manager.lights.owned(self.light)

    @property
    def on_map(self) -> bool:
        home = self.manager.home
        return bool(home and home.uses_map(self.entry_id))

    @property
    def occupied(self) -> bool:
        if self.on_map:
            return self.manager.home.people(self.entry_id) > 0
        return self.engine_occupied

    @property
    def engine_occupied(self) -> bool:
        raise NotImplementedError

    @property
    def people(self) -> int | None:
        return self.manager.home.people(self.entry_id) if self.on_map else None

    def persist(self) -> dict[str, Any]:
        return {
            "auto_light": self.auto_light,
            "only_dark": self.only_dark,
            "occupied": self.engine_occupied,
        }

    def restore(self, data: dict[str, Any]) -> None:
        self.auto_light = data.get("auto_light", True)
        self.only_dark = data.get("only_dark", True)
        if data.get("owned") and self.light:
            # Stored by version 0.1 per room; now kept per light.
            self.manager.saved.setdefault("lights", {}).setdefault(self.light, {"mode": "auto", "owned": True})


class RoomTarget(Target):
    def __init__(self, entry: ConfigEntry, manager: RadarOccupancyManager) -> None:
        super().__init__(entry, manager)
        self.room = Room()
        self._x: float | None = None
        self._y: float | None = None
        self.apply_options()

    def apply_options(self) -> None:
        self.room.config = RoomConfig(
            door_from=float(_option(self.entry, CONF_DOOR_FROM)),
            door_to=float(_option(self.entry, CONF_DOOR_TO)),
            safety_timeout=float(_option(self.entry, CONF_SAFETY_TIMEOUT)) * 60,
            handover=bool(_option(self.entry, CONF_HANDOVER)),
            handover_anywhere=bool(_option(self.entry, CONF_HANDOVER_ANYWHERE)),
            takeover_min=float(_option(self.entry, CONF_TAKEOVER_MIN)),
        )

    @property
    def inputs(self) -> list[str]:
        keys = (CONF_PRESENCE, CONF_DISTANCE, CONF_X, CONF_Y)
        return [self.entry.options[k] for k in keys if self.entry.options.get(k)]

    @property
    def engine_occupied(self) -> bool:
        return self.room.occupied

    @property
    def reason(self) -> str:
        if self.on_map:
            return self.manager.home.reason(self.entry_id) or self.room.reason
        return self.room.reason

    def read_inputs(self, hass: HomeAssistant, now: float) -> None:
        """Take all inputs from the current states (setup)."""
        for entity_id in self.inputs:
            self.apply(entity_id, hass.states.get(entity_id), now)

    def apply(self, entity_id: str, state: State | None, now: float) -> None:
        """Take one input from a state change.

        Uses the state carried by the event, not the current one: presence
        off and distance unknown arrive almost together, and the distance
        just before the target vanished is the one that matters.
        """
        options = self.entry.options
        room = self.room
        if entity_id == options[CONF_PRESENCE]:
            presence = None
            if state is not None and state.state in (STATE_ON, STATE_OFF):
                presence = state.state == STATE_ON
            room.set_presence(presence, now)
        if entity_id == options.get(CONF_DISTANCE):
            room.set_distance(_number(state))
        if entity_id == options.get(CONF_X):
            self._x = _number(state)
        if entity_id == options.get(CONF_Y):
            self._y = _number(state)
        if entity_id in (options.get(CONF_X), options.get(CONF_Y)):
            room.set_position(self._x, self._y)

    def persist(self) -> dict[str, Any]:
        room = self.room
        return {
            **super().persist(),
            "reason": room.reason,
            "hold": room.hold,
            "presence": room.presence,
            "presence_changed": room.presence_changed,
            "last_distance": room.last_distance,
            "last_x": room.last_x,
            "last_y": room.last_y,
        }

    def restore(self, data: dict[str, Any]) -> None:
        super().restore(data)
        room = self.room
        room.occupied = data.get("occupied", False)
        room.reason = data.get("reason", room.reason)
        room.hold = data.get("hold", True)
        room.presence = data.get("presence")
        room.presence_changed = data.get("presence_changed", 0.0)
        room.last_distance = data.get("last_distance")
        room.last_x = data.get("last_x")
        room.last_y = data.get("last_y")
        self.was_occupied = room.occupied


class AreaTarget(Target):
    def __init__(self, entry: ConfigEntry, manager: RadarOccupancyManager) -> None:
        super().__init__(entry, manager)

    @property
    def parent(self) -> RoomTarget | None:
        return self.manager.rooms.get(self.entry.options.get(CONF_PARENT, ""))

    @property
    def area(self) -> Area:
        o = self.entry.options
        return Area(float(o[CONF_X_MIN]), float(o[CONF_X_MAX]), float(o[CONF_Y_MIN]), float(o[CONF_Y_MAX]))

    @property
    def engine_occupied(self) -> bool:
        parent = self.parent
        return bool(parent and parent.room.area_occupied(self.area))

    @property
    def reason(self) -> str | None:
        return self.manager.home.reason(self.entry_id) if self.on_map else None

    def restore(self, data: dict[str, Any]) -> None:
        super().restore(data)
        self.was_occupied = data.get("occupied", False)


class RadarOccupancyManager:
    """One instance per Home Assistant, shared by all config entries."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.saved: dict[str, Any] = {}
        self.rooms: dict[str, RoomTarget] = {}
        self.areas: dict[str, AreaTarget] = {}
        self.home: Home | None = None
        self.plans: set[str] = set()  # floor plan entries
        self.lights: LightController | None = None
        self._unsub_states = None
        self._unsub_tick = None
        self._loaded = False
        self._watching: set[str] = set()
        self._ticks = 0

    @property
    def targets(self) -> list[Target]:
        return [*self.rooms.values(), *self.areas.values()]

    def target(self, entry_id: str) -> Target | None:
        return self.rooms.get(entry_id) or self.areas.get(entry_id)

    async def _async_load(self) -> None:
        if not self._loaded:
            self.saved = await self.store.async_load() or {}
            self._loaded = True
            self.lights = LightController(self)

    async def async_add(self, entry: ConfigEntry) -> Target | Home:
        await self._async_load()
        now = dt_util.utcnow().timestamp()
        if entry.data.get(CONF_KIND) == KIND_PLAN:
            # A floor plan has no entities; it is a map source for the home.
            self.plans.add(entry.entry_id)
            if self.home:
                self.home.reload_maps()
            return None
        if entry.data.get(CONF_KIND) == KIND_HOME:
            self.home = Home(self, entry)
            self._subscribe()
            self._start_tick()
            self.home.update()
            self.home.reload_maps()
            return self.home
        target: Target
        if entry.data.get(CONF_KIND) == KIND_AREA:
            target = AreaTarget(entry, self)
            target.restore(self.saved.get(entry.entry_id, {}))
            self.areas[entry.entry_id] = target
        else:
            target = RoomTarget(entry, self)
            target.restore(self.saved.get(entry.entry_id, {}))
            restored_presence = target.room.presence
            target.read_inputs(self.hass, now)
            if target.room.presence != restored_presence:
                # Changed while we were not running: count from now.
                target.room.presence_changed = now
            self.rooms[entry.entry_id] = target
        # Ownership restored from a version 0.1 room is kept per light now.
        for light, data in self.saved.get("lights", {}).items():
            self.lights.state.setdefault(
                light, LightState(mode=data.get("mode", "auto"), owned=data.get("owned", False))
            )
        self._link_areas()
        self._subscribe()
        self._start_tick()
        if self.home:
            self.home.reload_maps()
        return target

    def _start_tick(self) -> None:
        if self._unsub_tick is None:
            self._unsub_tick = async_track_time_interval(self.hass, self._tick, timedelta(seconds=1))

    async def async_remove(self, entry_id: str) -> None:
        if entry_id in self.plans:
            self.plans.discard(entry_id)
            if self.home:
                self.home.reload_maps()
            return
        if self.home and self.home.entry_id == entry_id:
            self.home.unload()
            self.home = None
            self.lights.cancel_all()
        else:
            self.rooms.pop(entry_id, None)
            self.areas.pop(entry_id, None)
        self._link_areas()
        self._subscribe()
        if not self.targets and self.home is None:
            if self._unsub_tick:
                self._unsub_tick()
                self._unsub_tick = None
            await self.store.async_save(self.saved)

    async def async_forget(self, entry_id: str) -> None:
        self.saved.pop(entry_id, None)
        if self.saved.get("map"):
            for key in ("calibrations", "exits", "doors", "people"):
                self.saved["map"].get(key, {}).pop(entry_id, None)
        await self.store.async_save(self.saved)

    def _link_areas(self) -> None:
        for room_id, room in self.rooms.items():
            room.room.areas = [a.area for a in self.areas.values() if a.entry.options.get(CONF_PARENT) == room_id]

    def _watched(self) -> set[str]:
        ids = {i for r in self.rooms.values() for i in r.inputs}
        lights = {t.light for t in self.targets if t.light}
        ids |= lights
        ids |= {leaf for light in lights for leaf in self.lights.leaves(light)}
        if self.home:
            ids |= self.home.inputs()
            ids |= {c for c in self.home.cameras() if c.startswith("camera.")}
        return ids

    def _subscribe(self) -> None:
        if self._unsub_states:
            self._unsub_states()
            self._unsub_states = None
        self._watching = self._watched()
        if self._watching:
            self._unsub_states = async_track_state_change_event(self.hass, sorted(self._watching), self._state_changed)

    @callback
    def _state_changed(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        new = event.data["new_state"]
        now = dt_util.utcnow().timestamp()
        if entity_id.startswith("light."):
            self.lights.light_changed(event)
        home = self.home
        if home and entity_id.startswith("camera."):
            if home.maps_outdated():
                home.reload_maps()
            return
        for room in self.rooms.values():
            if entity_id in room.inputs:
                room.apply(entity_id, new, now)
                if entity_id == room.entry.options[CONF_PRESENCE]:
                    # Publish the last seen position when presence changes,
                    # not on every position update: that would flood the recorder.
                    async_dispatcher_send(self.hass, SIGNAL_UPDATE.format(room.entry_id))
        if home and entity_id in home.inputs() | {r.entry.options[CONF_PRESENCE] for r in self.rooms.values()}:
            home.schedule()
        self.evaluate(now)

    @callback
    def _tick(self, _now) -> None:
        self._ticks += 1
        if self._ticks % 60 == 0 and self._watched() != self._watching:
            # Light groups that appeared after the start: follow their members too.
            self._subscribe()
        if self.home:
            self.home.update()
        self.evaluate(dt_util.utcnow().timestamp())

    @callback
    def evaluate(self, now: float | None = None) -> None:
        now = dt_util.utcnow().timestamp() if now is None else now
        changed: set[str] = set()
        for entry_id, room in self.rooms.items():
            if room.room.update(now):
                changed.add(entry_id)
        rooms = list(self.rooms.values())
        for released in handover([r.room for r in rooms], now):
            changed.update(r.entry_id for r in rooms if r.room is released)
        self.lights.evaluate(now)
        for target in self.targets:
            occupied = target.occupied
            target.was_occupied = occupied
            published = (
                occupied,
                target.on_map,
                target.people,
                getattr(target, "reason", None),
                self.lights.mode(target.light),
                target.owned,
            )
            if published != target.published:
                target.published = published
                changed.add(target.entry_id)
        if changed:
            for entry_id in changed:
                async_dispatcher_send(self.hass, SIGNAL_UPDATE.format(entry_id))
            self.save()

    @callback
    def save(self) -> None:
        for target in self.targets:
            self.saved[target.entry_id] = target.persist()
        self.store.async_delay_save(lambda: self.saved, 5)

    @callback
    def notify(self, target: Target) -> None:
        async_dispatcher_send(self.hass, SIGNAL_UPDATE.format(target.entry_id))
        self.save()

    def entity_ids(self, entry_id: str) -> dict[str, str]:
        """Entity ids of an entry by key (occupancy, hold, ...), for the card."""
        registry = er.async_get(self.hass)
        prefix = f"{entry_id}_"
        return {
            e.unique_id[len(prefix) :]: e.entity_id
            for e in er.async_entries_for_config_entry(registry, entry_id)
            if e.unique_id.startswith(prefix)
        }

    def resolve(self, value: str) -> str:
        """Room entry id from an entry id or any entity of that room."""
        if value in self.rooms:
            return value
        entity = er.async_get(self.hass).async_get(value)
        if entity and entity.config_entry_id in self.rooms:
            return entity.config_entry_id
        raise KeyError(value)
