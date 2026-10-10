"""Light control: one controller per light, shared by all rooms that use it.

States per light:

* auto: entering switches the light on (only when dark, time window), the
  last person leaving switches it off after the run-on time. Entering is the
  count of the room rising, or, in map mode, someone coming in through a
  door while the room is still held. Moving inside the room switches
  nothing. In map mode a person walking towards the door pre-lights the room.
* manual_off: someone switched the light off while the room was occupied.
  It stays off, also after leaving briefly (to the bathroom at night and
  back) and while someone in bed turns over. Ends when the light is switched
  on again from outside, when the room was empty for the configured time,
  when someone comes in through a door after nobody was seen there for that
  time (a held count must not keep the light off forever), or at once when
  someone comes into the home from outside through this room.

"From outside" is every change that does not come from this integration:
switches, the app, voice commands and other automations alike.

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
    manual_absent_since: float | None = None
    last_arrival: float | None = None  # newest door arrival already handled
    on_since: float | None = None  # switched on for an entry, not confirmed yet
    on_tries: int = 0
    was_allowed: bool | None = None  # light rule (dark, time window) at the last evaluation
    allowed_pending: bool = False  # became allowed while occupied: next sighting switches on
    prelit_since: float | None = None
    prelit_full: bool = False  # pre-lit at full brightness for an expected arrival
    last_off_try: float | None = None
    off_task: asyncio.Task | None = None


class LightController:
    def __init__(self, manager: RadarOccupancyManager) -> None:
        self.manager = manager
        self.hass = manager.hass
        self.state: dict[str, LightState] = {}
        for entity_id, data in manager.saved.get("lights", {}).items():
            self.state[entity_id] = LightState(
                mode=data.get("mode", AUTO),
                owned=data.get("owned", False),
                manual_absent_since=data.get("manual_absent_since"),
            )
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
        self.manager.saved["lights"] = {
            e: {"mode": s.mode, "owned": s.owned, "manual_absent_since": s.manual_absent_since}
            for e, s in self.state.items()
        }
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
            arrivals = [a for a in (t.arrival() for t in occupied_targets) if a is not None]
            arrival = max(arrivals) if arrivals else None
            new_arrival = arrival is not None and arrival > (st.last_arrival or -1e9)
            if new_arrival:
                st.last_arrival = arrival
            if st.occupied is None:
                # First evaluation after start or re-enabling: adopt, switch nothing.
                st.occupied = occupied
                st.empty_since = None if occupied else now
                continue
            if st.mode == MANUAL_OFF and new_arrival and any(t.arrived_from_outside() for t in occupied_targets):
                # Back home: switching everything off on the way out was meant
                # for the time away, not for the return. (A night trip to the
                # bathroom never comes from outside.)
                st.mode, st.manual_absent_since, changed = AUTO, None, True
            if st.mode == MANUAL_OFF and self.manual_off_reset():
                changed |= self.manual_off_expiry(st, targets, occupied, new_arrival, now)
            entered = occupied and (not st.occupied or new_arrival)
            if entered:
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
                    st.on_since, st.on_tries = now, 1
                st.prelit_since = None
            elif not occupied and st.occupied:
                st.empty_since = now
            st.occupied = occupied
            self.became_allowed(light, st, occupied_targets, entered, now)
            self.retry_on(light, st, occupied_targets, now)
            if occupied:
                continue
            empty = now - st.empty_since if st.empty_since is not None else 0
            run_on = max(float(t.entry.options.get(CONF_RUN_ON, DEFAULTS[CONF_RUN_ON])) for t in targets)
            if st.owned and empty >= run_on:
                if self.is_off(light):
                    st.owned, changed = False, True
                else:
                    self.maybe_switch_off(light, st, now)
            self.approach(light, st, targets, now)
        if changed:
            self.save()

    def manual_off_expiry(
        self, st: LightState, targets: list[Target], occupied: bool, new_arrival: bool, now: float
    ) -> bool:
        """End "switched off by hand"; returns whether anything changed.

        Only absence ends it, never movement inside the room: a sleeper
        turning over must not bring the light back."""
        reset = self.manual_off_reset()
        empty_long = not occupied and st.empty_since is not None and now - st.empty_since >= reset
        absent_long = st.manual_absent_since is not None and now - st.manual_absent_since >= reset
        if empty_long or (new_arrival and absent_long):
            st.mode, st.manual_absent_since = AUTO, None
            return True
        if any(t.observed(now) for t in targets):
            if st.manual_absent_since is not None:
                st.manual_absent_since = None
                return True
        elif st.manual_absent_since is None:
            st.manual_absent_since = now
            return True
        return False

    def became_allowed(
        self, light: str, st: LightState, occupied_targets: list[Target], entered: bool, now: float
    ) -> None:
        """Dusk, the time window opening or "only when dark" switched off while
        someone is in the room: the light comes on as soon as they are seen."""
        allowed = any(self.allowed(t) for t in occupied_targets)
        if allowed and st.was_allowed is False and occupied_targets and not entered:
            st.allowed_pending = True
        st.was_allowed = allowed if occupied_targets else None
        if not occupied_targets or not allowed or st.mode != AUTO or not self.is_off(light):
            st.allowed_pending = False
        elif st.allowed_pending and any(t.observed(now) for t in occupied_targets):
            st.allowed_pending = False
            self.switch_on(light, occupied_targets, "enter")
            st.on_since, st.on_tries = now, 1

    def retry_on(self, light: str, st: LightState, occupied_targets: list[Target], now: float) -> None:
        """Cloud lamps sometimes drop a command: try again until the light reports on."""
        if st.on_since is None:
            return
        if (
            self.hass.states.is_state(light, STATE_ON)
            or not occupied_targets
            or st.mode != AUTO
            or not self.is_off(light)
        ):
            st.on_since = None
            return
        if now - st.on_since >= const.OWN_ECHO:
            if st.on_tries >= const.OFF_ATTEMPTS:
                st.on_since = None
                return
            st.on_since, st.on_tries = now, st.on_tries + 1
            self.switch_on(light, occupied_targets, "enter")

    def manual_off_reset(self) -> float:
        if self.home is None:
            return 0  # without a home entry: ends with the next entering
        return float(self.home.entry.options.get(CONF_MANUAL_OFF_RESET, HOME_DEFAULTS[CONF_MANUAL_OFF_RESET])) * 60

    def approach(self, light: str, st: LightState, targets: list[Target], now: float) -> None:
        home = self.home
        approaching = bool(home) and any(home.approaching(t.entry_id) for t in targets)
        expected = bool(home) and any(home.expected(t.entry_id) for t in targets)
        if (
            expected
            and st.mode == AUTO
            and (self.is_off(light) or (st.prelit_since and not st.prelit_full))
            and any(self.allowed(t) for t in targets)
        ):
            # Lost at the door to this room and nobody can see the other side:
            # light it as for entering; it fades out like a pre-light if
            # nobody turns up.
            st.prelit_since, st.prelit_full = now, True
            self.switch_on(light, targets, "enter")
        elif (
            approaching
            and st.mode == AUTO
            and not st.prelit_since
            and self.is_off(light)
            and any(self.allowed(t) for t in targets)
        ):
            st.prelit_since, st.prelit_full = now, False
            self.switch_on(light, targets, "approach")
        elif st.prelit_since and not approaching and not expected and now - st.prelit_since >= const.PRELIT_TIMEOUT:
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
        native = {
            leaf
            for leaf in leaves
            if (state := self.hass.states.get(leaf))
            and int(state.attributes.get("supported_features") or 0) & TRANSITION
            and any(mode != "onoff" for mode in state.attributes.get("supported_color_modes", []))
        }
        native_next: dict[str, float] = {}

        def send(leaf: str, value: int, transition: float | None = None) -> None:
            async def run() -> None:
                async with self.slots:
                    data = {"entity_id": leaf, "brightness": value}
                    if transition is not None:
                        data["transition"] = transition
                    await self.hass.services.async_call("light", "turn_on", data, blocking=True, context=context)

            sent[leaf] = value
            inflight[leaf] = self.hass.async_create_task(run())

        try:
            # Devices may remember their last on-level while off. Establish
            # the dim starting point before asking their firmware to fade.
            for leaf in native:
                if self.is_off(leaf):
                    send(leaf, 1, 0)
            await asyncio.gather(*inflight.values(), return_exceptions=True)
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
                    # One command per lamp at a time: while a slow (cloud) command
                    # is still running, intermediate values are skipped.
                    if leaf in inflight and not inflight[leaf].done():
                        continue
                    if leaf in native:
                        # Firmware interpolates between sparse CIE L* waypoints;
                        # this keeps the low end smooth without a 20 Hz network
                        # stream. Do not restart a transition already in flight.
                        if progress + 1e-9 < native_next.get(leaf, 0) or sent.get(leaf) == max(1, goal[leaf]):
                            continue
                        endpoint = min(1, progress + const.NATIVE_FADE_STEP / duration)
                        native_next[leaf] = endpoint
                        value = max(1, perceptual(start[leaf], goal[leaf], endpoint))
                        if value != sent.get(leaf):
                            send(leaf, value, const.NATIVE_FADE_STEP)
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
                    send(leaf, max(1, goal[leaf]), const.NATIVE_FADE_STEP if leaf in native else None)
            await asyncio.gather(*inflight.values(), return_exceptions=True)
            if native:
                await asyncio.sleep(const.NATIVE_FADE_STEP)
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
        if new.state == STATE_ON:
            st.on_since = None  # an entry switch-on arrived (or someone else switched it on)
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
        if new.state == STATE_OFF:
            if st.occupied:
                st.mode = MANUAL_OFF
                st.manual_absent_since = None if any(t.observed(now) for t in self.groups().get(entity_id, [])) else now
        else:
            st.mode = AUTO
            st.manual_absent_since = None
            st.owned = bool(st.occupied)
        self.save()

    def snapshot(self) -> dict[str, Any]:
        return {
            e: {"mode": s.mode, "owned": s.owned, "occupied": s.occupied, "prelit": bool(s.prelit_since)}
            for e, s in self.state.items()
        }
