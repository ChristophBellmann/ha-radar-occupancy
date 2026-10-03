"""Light control: one controller per light, shared by all rooms that use it.

States per light:

* auto: entering switches the light on (only when dark, time window), the
  last person leaving switches it off after the run-on time. In map mode a
  person walking towards the door pre-lights the room.
* manual_off: someone switched the light off by hand while the room was
  occupied. It stays off, also after leaving briefly (to the bathroom at
  night and back). Ends when the light is switched on by hand, or after the
  room was empty for the configured time.

"By hand" is every change that neither comes from this integration nor from
another automation (a context with a parent but without a user).

Whoever entered owns the light: it is switched off on leaving even if it was
already on. A light switched on while nobody entered stays on.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import Context, Event, callback
from homeassistant.util import dt as dt_util

from . import const
from .const import (
    CONF_APPROACH_BRIGHTNESS,
    CONF_BRIGHTNESS,
    CONF_MANUAL_OFF_RESET,
    CONF_REMEMBER_BRIGHTNESS,
    CONF_RUN_ON,
    CONF_WINDOW_END,
    CONF_WINDOW_START,
    DEFAULTS,
    HOME_DEFAULTS,
)

if TYPE_CHECKING:
    from .manager import RadarOccupancyManager, Target

_LOGGER = logging.getLogger(__name__)

AUTO = "auto"
MANUAL_OFF = "manual_off"
TRANSITION = 32  # LightEntityFeature.TRANSITION


def in_window(start: str, end: str, now: str) -> bool:
    """Time window check on HH:MM:SS strings; start == end means always."""
    if start == end:
        return True
    if start < end:
        return start <= now < end
    return now >= start or now < end


def lightness(brightness: float) -> float:
    y = max(0, min(255, brightness)) / 255
    return 116 * y ** (1 / 3) - 16 if y > 0.008856 else 903.3 * y


def perceptual(start: float, end: float, progress: float) -> int:
    """Intermediate brightness, evenly spaced in perceived lightness (CIE L*).

    Linear steps in brightness values look like jumps at the low end."""
    value = lightness(start) + (lightness(end) - lightness(start)) * max(0, min(1, progress))
    y = ((value + 16) / 116) ** 3 if value > 8 else value / 903.3
    return round(y * 255)


@dataclass
class LightState:
    mode: str = AUTO
    owned: bool = False
    occupied: bool | None = None  # None: not evaluated since start
    empty_since: float | None = None
    prelit_since: float | None = None
    last_off_try: float | None = None
    off_task: asyncio.Task | None = None


class LightController:
    def __init__(self, manager: RadarOccupancyManager) -> None:
        self.manager = manager
        self.hass = manager.hass
        self.state: dict[str, LightState] = {}
        for entity_id, data in manager.saved.get("lights", {}).items():
            self.state[entity_id] = LightState(mode=data.get("mode", AUTO), owned=data.get("owned", False))
        self.brightness: dict[str, int] = manager.saved.setdefault("brightness", {})
        self.contexts: deque[str] = deque(maxlen=300)
        self.last_command: dict[str, float] = {}
        self.internal: set[str] = set()
        self.fades: dict[str, asyncio.Task] = {}
        self.slots = asyncio.Semaphore(const.LIGHT_SLOTS)

    # Helpers ------------------------------------------------------------

    @property
    def home(self):
        return self.manager.home

    def active(self) -> bool:
        return self.home is None or self.home.light_automation

    def owned(self, light: str | None) -> bool:
        st = self.state.get(light) if light else None
        return bool(st and st.owned)

    def mode(self, light: str | None) -> str | None:
        st = self.state.get(light) if light else None
        return st.mode if st else None

    def leaves(self, entity_id: str, visited: set[str] | None = None) -> list[str]:
        """Member lights of (nested) light groups; a plain light is its own leaf."""
        visited = (visited or set()) | {entity_id}
        state = self.hass.states.get(entity_id)
        members = state.attributes.get("entity_id") if state else None
        if not members or not isinstance(members, (list, tuple)):
            return [entity_id]
        return list(dict.fromkeys(leaf for m in members if m not in visited for leaf in self.leaves(m, visited)))

    def context(self) -> Context:
        ctx = Context()
        self.contexts.append(ctx.id)
        return ctx

    def mark(self, light: str) -> None:
        now = dt_util.utcnow().timestamp()
        for entity_id in [light, *self.leaves(light)]:
            self.last_command[entity_id] = now

    def groups(self) -> dict[str, list[Target]]:
        groups: dict[str, list[Target]] = {}
        for target in self.manager.targets:
            if target.light and target.auto_light:
                groups.setdefault(target.light, []).append(target)
        return groups

    def allowed(self, target: Target) -> bool:
        if target.only_dark:
            sun = self.hass.states.get("sun.sun")
            if sun is not None and sun.state != "below_horizon":
                return False
        options = target.entry.options
        start = options.get(CONF_WINDOW_START, DEFAULTS[CONF_WINDOW_START])
        end = options.get(CONF_WINDOW_END, DEFAULTS[CONF_WINDOW_END])
        return in_window(start, end, dt_util.now().strftime("%H:%M:%S"))

    def light_occupied(self, light: str) -> bool:
        return any(t.occupied for t in self.groups().get(light, []))

    def is_off(self, light: str) -> bool:
        # "unavailable" is not a switched-off light.
        return self.hass.states.is_state(light, STATE_OFF)

    def save(self) -> None:
        self.manager.saved["lights"] = {e: {"mode": s.mode, "owned": s.owned} for e, s in self.state.items()}
        self.manager.save()

    # Evaluation ---------------------------------------------------------

    @callback
    def evaluate(self, now: float) -> None:
        if not self.active():
            return
        changed = False
        for light, targets in self.groups().items():
            st = self.state.setdefault(light, LightState())
            occupied_targets = [t for t in targets if t.occupied]
            occupied = bool(occupied_targets)
            if st.occupied is None:
                # First evaluation after start or re-enabling: adopt, switch nothing.
                st.occupied = occupied
                st.empty_since = None if occupied else now
                continue
            if occupied and not st.occupied:
                st.empty_since = None
                if st.mode == MANUAL_OFF and not self.manual_off_reset():
                    st.mode, changed = AUTO, True  # without a home entry: ends with the next entering
                if not st.owned:
                    st.owned = changed = True
                if (
                    st.mode == AUTO
                    and any(self.allowed(t) for t in occupied_targets)
                    and (self.is_off(light) or st.prelit_since)
                ):
                    self.switch_on(light, occupied_targets, "enter")
                st.prelit_since = None
            elif not occupied and st.occupied:
                st.empty_since = now
            st.occupied = occupied
            if occupied:
                continue
            empty = now - st.empty_since if st.empty_since is not None else 0
            run_on = max(float(t.entry.options.get(CONF_RUN_ON, DEFAULTS[CONF_RUN_ON])) for t in targets)
            if st.owned and empty >= run_on:
                if self.is_off(light):
                    st.owned, changed = False, True
                else:
                    self.maybe_switch_off(light, st, now)
            reset = self.manual_off_reset()
            if st.mode == MANUAL_OFF and reset and empty >= reset:
                st.mode, changed = AUTO, True
            self.approach(light, st, targets, now)
        if changed:
            self.save()

    def manual_off_reset(self) -> float:
        if self.home is None:
            return 0  # without a home entry: ends with the next entering
        return float(self.home.entry.options.get(CONF_MANUAL_OFF_RESET, HOME_DEFAULTS[CONF_MANUAL_OFF_RESET])) * 60

    def approach(self, light: str, st: LightState, targets: list[Target], now: float) -> None:
        home = self.home
        approaching = bool(home) and any(home.approaching(t.entry_id) for t in targets)
        if (
            approaching
            and st.mode == AUTO
            and not st.prelit_since
            and self.is_off(light)
            and any(self.allowed(t) for t in targets)
        ):
            st.prelit_since = now
            self.switch_on(light, targets, "approach")
        elif st.prelit_since and not approaching and now - st.prelit_since >= const.PRELIT_TIMEOUT:
            st.prelit_since = None
            if self.hass.states.is_state(light, STATE_ON):
                self.start_fade(light, targets, "off")

    # Commands -----------------------------------------------------------

    def target_brightness(self, light: str, targets: list[Target]) -> dict[str, int]:
        """Brightness (0-255) per leaf: the last one set by hand, or the configured one."""
        percent = max(int(t.entry.options.get(CONF_BRIGHTNESS, DEFAULTS[CONF_BRIGHTNESS])) for t in targets)
        fixed = max(1, round(percent * 2.55))
        remember = any(t.entry.options.get(CONF_REMEMBER_BRIGHTNESS) for t in targets)
        return {leaf: (self.brightness.get(leaf) if remember else None) or fixed for leaf in self.leaves(light)}

    def fade_time(self, direction: str) -> float:
        if self.home is None:
            return 0.0
        return self.home.fade_out if direction == "off" else self.home.fade_in

    def switch_on(self, light: str, targets: list[Target], direction: str) -> None:
        self.cancel_fade(light)
        if self.fade_time(direction) > 0:
            self.start_fade(light, targets, direction)
            return
        self.mark(light)
        if any(t.entry.options.get(CONF_REMEMBER_BRIGHTNESS) for t in targets) or direction == "approach":
            factor = self.approach_factor() if direction == "approach" else 1
            for leaf, value in self.target_brightness(light, targets).items():
                self._call("turn_on", {"entity_id": leaf, "brightness": max(1, round(value * factor))})
        else:
            percent = max(int(t.entry.options.get(CONF_BRIGHTNESS, DEFAULTS[CONF_BRIGHTNESS])) for t in targets)
            self._call("turn_on", {"entity_id": light, "brightness_pct": percent})

    def approach_factor(self) -> float:
        if self.home is None:
            return HOME_DEFAULTS[CONF_APPROACH_BRIGHTNESS] / 100
        return (
            float(self.home.entry.options.get(CONF_APPROACH_BRIGHTNESS, HOME_DEFAULTS[CONF_APPROACH_BRIGHTNESS])) / 100
        )

    def _call(self, service: str, data: dict[str, Any]) -> None:
        self.hass.async_create_task(self.hass.services.async_call("light", service, data, context=self.context()))

    def maybe_switch_off(self, light: str, st: LightState, now: float) -> None:
        if st.off_task and not st.off_task.done():
            return
        if st.last_off_try is not None and now - st.last_off_try < const.OFF_RECHECK:
            return
        st.last_off_try = now
        st.off_task = self.hass.async_create_task(self._switch_off(light, st))

    async def _switch_off(self, light: str, st: LightState) -> None:
        targets = self.groups().get(light, [])
        if self.fade_time("off") > 0 and self.hass.states.is_state(light, STATE_ON):
            task = self.start_fade(light, targets, "off")
            await asyncio.gather(task, return_exceptions=True)
            if self.light_occupied(light):
                return
        for _ in range(const.OFF_ATTEMPTS):
            if st.occupied or not st.owned:
                return
            self.mark(light)
            try:
                await self.hass.services.async_call(
                    "light", "turn_off", {"entity_id": light}, blocking=True, context=self.context()
                )
            except Exception as err:  # noqa: BLE001 - keep trying, report once
                _LOGGER.debug("Switching off %s failed: %s", light, err)
            await asyncio.sleep(const.OFF_RETRY_DELAY)
            if not self.hass.states.is_state(light, STATE_ON):
                break
        # A command to an unreachable lamp is dropped silently; keep ownership
        # until the light really is off, the next try follows OFF_RECHECK later.
        if not self.hass.states.is_state(light, STATE_ON):
            st.owned = False
            self.save()

    # Fades --------------------------------------------------------------

    def cancel_fade(self, light: str) -> None:
        task = self.fades.get(light)
        if task and not task.done():
            task.cancel()

    def cancel_all(self) -> None:
        for task in list(self.fades.values()):
            task.cancel()
        for st in self.state.values():
            st.occupied = None  # adopt again when re-enabled
            st.prelit_since = None

    def start_fade(self, light: str, targets: list[Target], direction: str) -> asyncio.Task:
        self.cancel_fade(light)
        self.mark(light)
        task = self.hass.async_create_task(self._fade(light, targets, direction, self.context()))
        self.fades[light] = task
        # State reports arriving after the fade are still our own.
        task.add_done_callback(lambda _: self.mark(light))
        return task

    async def _fade(self, light: str, targets: list[Target], direction: str, context: Context) -> None:
        leaves = self.leaves(light)
        if direction == "off":
            # Fading out never switches anything on: lights already off stay untouched.
            leaves = [leaf for leaf in leaves if not self.is_off(leaf)]
            if not leaves:
                return
        self.internal.update([*leaves, light])
        goal = self.target_brightness(light, targets)
        if direction == "approach":
            goal = {leaf: max(1, round(v * self.approach_factor())) for leaf, v in goal.items()}
        elif direction == "off":
            goal = dict.fromkeys(leaves, 1)
        start = {}
        for leaf in leaves:
            state = self.hass.states.get(leaf)
            on = state is not None and state.state == STATE_ON
            start[leaf] = max(1, int(state.attributes.get("brightness") or 255)) if on else 1
        duration = max(self.fade_time(direction), const.FADE_STEP)
        sent: dict[str, int] = {}
        inflight: dict[str, asyncio.Task] = {}

        def send(leaf: str, value: int) -> None:
            async def run() -> None:
                async with self.slots:
                    await self.hass.services.async_call(
                        "light", "turn_on", {"entity_id": leaf, "brightness": value}, blocking=True, context=context
                    )

            sent[leaf] = value
            inflight[leaf] = self.hass.async_create_task(run())

        try:
            steps = max(1, round(duration / const.FADE_STEP))
            loop = asyncio.get_running_loop()
            started = loop.time()
            for i in range(1, steps + 1):
                if not self.active():
                    return
                if direction == "off" and self.light_occupied(light):
                    # Someone came back: straight back to the target brightness.
                    await asyncio.gather(*inflight.values(), return_exceptions=True)
                    for leaf, value in self.target_brightness(light, targets).items():
                        if leaf in leaves:
                            await self.hass.services.async_call(
                                "light",
                                "turn_on",
                                {"entity_id": leaf, "brightness": value},
                                blocking=True,
                                context=context,
                            )
                    return
                progress = max(i / steps, min(1, (loop.time() - started) / duration))
                commands = []
                for leaf in leaves:
                    state = self.hass.states.get(leaf)
                    if state is None or state.state not in (STATE_ON, STATE_OFF):
                        continue
                    modes = state.attributes.get("supported_color_modes") or []
                    if not any(m != "onoff" for m in modes):
                        if i == steps:
                            commands.append(
                                self.hass.services.async_call(
                                    "light",
                                    "turn_off" if direction == "off" else "turn_on",
                                    {"entity_id": leaf},
                                    blocking=True,
                                    context=context,
                                )
                            )
                        continue
                    if int(state.attributes.get("supported_features") or 0) & TRANSITION:
                        if i == 1:
                            data = {"entity_id": leaf, "brightness": max(1, goal[leaf]), "transition": duration}
                            commands.append(
                                self.hass.services.async_call("light", "turn_on", data, blocking=True, context=context)
                            )
                        continue
                    # One command per lamp at a time: while a slow (cloud) command
                    # is still running, intermediate values are skipped.
                    if leaf in inflight and not inflight[leaf].done():
                        continue
                    value = max(1, perceptual(start[leaf], goal[leaf], progress))
                    if value != sent.get(leaf):
                        send(leaf, value)
                if commands:
                    await asyncio.gather(*commands, return_exceptions=True)
                await asyncio.sleep(max(0, started + duration * i / steps - loop.time()))
                if progress >= 1:
                    break
            # Make sure the final value arrives even if steps were skipped.
            await asyncio.gather(*inflight.values(), return_exceptions=True)
            for leaf in leaves:
                if leaf in sent and sent[leaf] != max(1, goal[leaf]):
                    send(leaf, max(1, goal[leaf]))
            await asyncio.gather(*inflight.values(), return_exceptions=True)
            if direction == "off" and not self.light_occupied(light):
                await self.hass.services.async_call(
                    "light", "turn_off", {"entity_id": light}, blocking=True, context=context
                )
            await asyncio.sleep(0.8)
        finally:
            for task in inflight.values():
                if not task.done():
                    task.cancel()
            # A replaced fade must not clear the lock of its successor.
            if self.fades.get(light) is asyncio.current_task():
                self.fades.pop(light, None)
                self.internal.difference_update([*leaves, light])

    # Changes from outside -------------------------------------------------

    @callback
    def light_changed(self, event: Event) -> None:
        entity_id = event.data["entity_id"]
        old, new = event.data.get("old_state"), event.data.get("new_state")
        if new is None or entity_id in self.internal:
            return
        now = dt_util.utcnow().timestamp()
        ctx = new.context
        own = now - self.last_command.get(entity_id, -1e9) < const.OWN_ECHO or (
            ctx is not None and (ctx.id in self.contexts or ctx.parent_id in self.contexts)
        )
        brightness = new.attributes.get("brightness")
        if new.state == STATE_ON and not own and brightness and self.brightness.get(entity_id) != brightness:
            self.brightness[entity_id] = brightness
            self.manager.save()
        st = self.state.get(entity_id)
        if st is None:
            return
        if new.state == STATE_OFF:
            # Switched off, by us or anyone: nothing left to switch off.
            st.owned = False
            st.prelit_since = None
        if old is None or old.state == new.state or {old.state, new.state} - {STATE_ON, STATE_OFF}:
            self.save()
            return
        if not self.active() or own:
            self.save()
            return
        if ctx is not None and ctx.parent_id is not None and ctx.user_id is None:
            self.save()
            return  # another automation, not by hand
        if new.state == STATE_OFF:
            if st.occupied:
                st.mode = MANUAL_OFF
        else:
            st.mode = AUTO
            st.owned = bool(st.occupied)
        self.save()

    def snapshot(self) -> dict[str, Any]:
        return {
            e: {"mode": s.mode, "owned": s.owned, "occupied": s.occupied, "prelit": bool(s.prelit_since)}
            for e, s in self.state.items()
        }
