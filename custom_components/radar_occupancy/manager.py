"""Runtime shared by all rooms: inputs, handover, light control, persistence."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import const
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
    KIND_AREA,
    SIGNAL_UPDATE,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .engine import Area, Room, RoomConfig, handover

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


def in_window(start: str, end: str, now: str) -> bool:
    """Time window check on HH:MM:SS strings; start == end means always."""
    if start == end:
        return True
    if start < end:
        return start <= now < end
    return now >= start or now < end


class Target:
    """Something with an occupancy and optionally a light: a room or a sub-area."""

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry
        self.auto_light = True
        self.only_dark = True
        self.owned = False  # we switched the light on, so we switch it off
        self.was_occupied = False
        self.unoccupied_since: float | None = None
        self.last_off_try: float | None = None
        self.off_task: asyncio.Task | None = None

    @property
    def entry_id(self) -> str:
        return self.entry.entry_id

    @property
    def light(self) -> str | None:
        return self.entry.options.get(CONF_LIGHT) or None

    @property
    def occupied(self) -> bool:
        raise NotImplementedError

    def persist(self) -> dict[str, Any]:
        return {
            "auto_light": self.auto_light,
            "only_dark": self.only_dark,
            "owned": self.owned,
            "occupied": self.occupied,
        }

    def restore(self, data: dict[str, Any]) -> None:
        self.auto_light = data.get("auto_light", True)
        self.only_dark = data.get("only_dark", True)
        self.owned = data.get("owned", False)


class RoomTarget(Target):
    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
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
    def occupied(self) -> bool:
        return self.room.occupied

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
        super().__init__(entry)
        self.manager = manager

    @property
    def parent(self) -> RoomTarget | None:
        return self.manager.rooms.get(self.entry.options.get(CONF_PARENT, ""))

    @property
    def area(self) -> Area:
        o = self.entry.options
        return Area(float(o[CONF_X_MIN]), float(o[CONF_X_MAX]), float(o[CONF_Y_MIN]), float(o[CONF_Y_MAX]))

    @property
    def occupied(self) -> bool:
        parent = self.parent
        return bool(parent and parent.room.area_occupied(self.area))

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
        self._unsub_states = None
        self._unsub_tick = None
        self._loaded = False

    @property
    def targets(self) -> list[Target]:
        return [*self.rooms.values(), *self.areas.values()]

    def target(self, entry_id: str) -> Target | None:
        return self.rooms.get(entry_id) or self.areas.get(entry_id)

    async def async_add(self, entry: ConfigEntry) -> Target:
        if not self._loaded:
            self.saved = await self.store.async_load() or {}
            self._loaded = True
        now = dt_util.utcnow().timestamp()
        target: Target
        if entry.data.get(CONF_KIND) == KIND_AREA:
            target = AreaTarget(entry, self)
            target.restore(self.saved.get(entry.entry_id, {}))
            self.areas[entry.entry_id] = target
        else:
            target = RoomTarget(entry)
            target.restore(self.saved.get(entry.entry_id, {}))
            restored_presence = target.room.presence
            target.read_inputs(self.hass, now)
            if target.room.presence != restored_presence:
                # Changed while we were not running: count from now.
                target.room.presence_changed = now
            self.rooms[entry.entry_id] = target
        if not target.occupied and target.unoccupied_since is None:
            # Restart: a light we own in an empty room goes off after run-on.
            target.unoccupied_since = now
        self._link_areas()
        self._subscribe()
        if self._unsub_tick is None:
            self._unsub_tick = async_track_time_interval(self.hass, self._tick, timedelta(seconds=1))
        return target

    async def async_remove(self, entry_id: str) -> None:
        target = self.rooms.pop(entry_id, None) or self.areas.pop(entry_id, None)
        if target and target.off_task:
            target.off_task.cancel()
        self._link_areas()
        self._subscribe()
        if not self.targets:
            if self._unsub_tick:
                self._unsub_tick()
                self._unsub_tick = None
            await self.store.async_save(self.saved)

    async def async_forget(self, entry_id: str) -> None:
        self.saved.pop(entry_id, None)
        await self.store.async_save(self.saved)

    def _link_areas(self) -> None:
        for room_id, room in self.rooms.items():
            room.room.areas = [a.area for a in self.areas.values() if a.entry.options.get(CONF_PARENT) == room_id]

    def _subscribe(self) -> None:
        if self._unsub_states:
            self._unsub_states()
            self._unsub_states = None
        ids = {i for r in self.rooms.values() for i in r.inputs}
        ids |= {t.light for t in self.targets if t.light}
        if ids:
            self._unsub_states = async_track_state_change_event(self.hass, sorted(ids), self._state_changed)

    @callback
    def _state_changed(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        new = event.data["new_state"]
        now = dt_util.utcnow().timestamp()
        for target in self.targets:
            if target.light == entity_id and new is not None and new.state == STATE_OFF:
                # Switched off (by us or anyone): nothing left to switch off.
                target.owned = False
        for room in self.rooms.values():
            if entity_id in room.inputs:
                room.apply(entity_id, new, now)
                if entity_id == room.entry.options[CONF_PRESENCE]:
                    # Publish the last seen position when presence changes,
                    # not on every position update: that would flood the recorder.
                    async_dispatcher_send(self.hass, SIGNAL_UPDATE.format(room.entry_id))
        self.evaluate(now)

    @callback
    def _tick(self, _now) -> None:
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
        for target in self.targets:
            occupied = target.occupied
            if occupied != target.was_occupied:
                changed.add(target.entry_id)
                target.was_occupied = occupied
                if occupied:
                    target.unoccupied_since = None
                    self._entered(target)
                else:
                    target.unoccupied_since = now
            self._maybe_switch_off(target, now)
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

    # Light control ------------------------------------------------------

    def _dark_enough(self, target: Target) -> bool:
        if not target.only_dark:
            return True
        sun = self.hass.states.get("sun.sun")
        return sun is None or sun.state == "below_horizon"

    def _entered(self, target: Target) -> None:
        if not target.light or not target.auto_light:
            return
        # Whoever entered owns switching off on leaving, even if the light
        # was already on or stays off because it is daytime.
        target.owned = True
        if not self._dark_enough(target):
            return
        options = target.entry.options
        start = options.get(CONF_WINDOW_START, DEFAULTS[CONF_WINDOW_START])
        end = options.get(CONF_WINDOW_END, DEFAULTS[CONF_WINDOW_END])
        if not in_window(start, end, dt_util.now().strftime("%H:%M:%S")):
            return
        # "unavailable" is not a switched-off light.
        if not self.hass.states.is_state(target.light, STATE_OFF):
            return
        brightness = int(options.get(CONF_BRIGHTNESS, DEFAULTS[CONF_BRIGHTNESS]))
        self.hass.async_create_task(
            self.hass.services.async_call("light", "turn_on", {"entity_id": target.light, "brightness_pct": brightness})
        )

    def _shared_and_occupied(self, target: Target) -> bool:
        return any(
            other is not target and other.light == target.light and other.auto_light and other.occupied
            for other in self.targets
        )

    def _maybe_switch_off(self, target: Target, now: float) -> None:
        if not target.owned or target.occupied or target.unoccupied_since is None:
            return
        if not target.light:
            target.owned = False
            return
        run_on = float(target.entry.options.get(CONF_RUN_ON, DEFAULTS[CONF_RUN_ON]))
        if now - target.unoccupied_since < run_on:
            return
        if target.off_task and not target.off_task.done():
            return
        if target.last_off_try is not None and now - target.last_off_try < const.OFF_RECHECK:
            return
        if self._shared_and_occupied(target):
            return
        target.last_off_try = now
        target.off_task = self.hass.async_create_task(self._switch_off(target))

    async def _switch_off(self, target: Target) -> None:
        light = target.light
        for _ in range(const.OFF_ATTEMPTS):
            if target.occupied or not target.owned:
                return
            try:
                await self.hass.services.async_call("light", "turn_off", {"entity_id": light}, blocking=True)
            except Exception as err:  # noqa: BLE001 - keep trying, report once
                _LOGGER.debug("Switching off %s failed: %s", light, err)
            await asyncio.sleep(const.OFF_RETRY_DELAY)
            if not self.hass.states.is_state(light, STATE_ON):
                break
        # A command to an unreachable lamp is dropped silently; keep ownership
        # until the light really is off, the next try follows OFF_RECHECK later.
        if not self.hass.states.is_state(light, STATE_ON):
            target.owned = False
            self.save()
