"""Map mode and light control end to end, on a synthetic floor.

Floor plan (map mm): bedroom left, hall in the middle, bathroom right.
  Bedroom 0..4000 x 0..4000, door at (4000, 1000)
  Hall 4000..8000 x 0..2000, stairs (exit) at (6000, 0)
  Bathroom 8000..11000 x 0..3000, door at (8000, 1000)
Every sensor looks along +Y (heading 90°), so radar = map - sensor location.
"""

import asyncio
from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.radar_occupancy import home as home_module
from custom_components.radar_occupancy import lights as lights_module
from custom_components.radar_occupancy.const import (
    CONF_BRIGHTNESS,
    CONF_KIND,
    CONF_LIGHT,
    CONF_MAP_CAMERA,
    CONF_MAP_ROOM,
    CONF_PRESENCE,
    CONF_RUN_ON,
    CONF_X,
    CONF_Y,
    DEFAULTS,
    DOMAIN,
    HOME_DEFAULTS,
    KIND_HOME,
    KIND_ROOM,
)

POLYGONS = {
    "Bedroom": [[0, 0], [4000, 0], [4000, 4000], [0, 4000]],
    "Hall": [[4000, 0], [8000, 0], [8000, 2000], [4000, 2000]],
    "Bathroom": [[8000, 0], [11000, 0], [11000, 3000], [8000, 3000]],
}
SENSORS = {"bed": ("Bedroom", (2000, 0)), "hall": ("Hall", (6000, -500)), "bath": ("Bathroom", (9500, 0))}
FLOOR = {
    "camera": "camera.map",
    "map_id": 7,
    "width": 1100,
    "height": 400,
    "calibration_points": [
        {"vacuum": {"x": 0, "y": 0}, "map": {"x": 0, "y": 0}},
        {"vacuum": {"x": 10000, "y": 0}, "map": {"x": 1000, "y": 0}},
        {"vacuum": {"x": 0, "y": 10000}, "map": {"x": 0, "y": 1000}},
    ],
    "image_path": "/api/radar_occupancy/map/map?v=1",
    "rooms": [
        {"id": i, "name": name, "x": poly[0][0] + 1000, "y": 1000, "polygon": poly, "approach_polygons": []}
        for i, (name, poly) in enumerate(POLYGONS.items(), 1)
    ],
    "passages": [("Bedroom", "Hall", [4000, 1000], 900), ("Bathroom", "Hall", [8000, 1000], 900)],
    "image": b"png",
}


def room_entry(key: str, **options) -> MockConfigEntry:
    name, _ = SENSORS[key]
    return MockConfigEntry(
        domain=DOMAIN,
        title=name,
        data={CONF_KIND: KIND_ROOM},
        options={
            **DEFAULTS,
            CONF_PRESENCE: f"binary_sensor.{key}_presence",
            CONF_X: f"sensor.{key}_x",
            CONF_Y: f"sensor.{key}_y",
            CONF_MAP_CAMERA: "camera.map",
            CONF_MAP_ROOM: name,
            **options,
        },
    )


def mock_lights(hass: HomeAssistant, groups: dict[str, list[str]] | None = None) -> list:
    """light.turn_on/off that change the state like real lights; groups are on if a member is."""
    calls = []

    def sync_groups():
        for group, members in (groups or {}).items():
            on = any(hass.states.is_state(m, "on") for m in members)
            hass.states.async_set(group, "on" if on else "off", {"entity_id": members})

    async def turn_on(call):
        calls.append(("on", dict(call.data)))
        brightness = call.data.get("brightness") or round(call.data.get("brightness_pct", 100) * 2.55)
        hass.states.async_set(
            call.data["entity_id"],
            "on",
            {"brightness": brightness, "supported_color_modes": ["brightness"]},
            context=call.context,
        )
        sync_groups()

    async def turn_off(call):
        calls.append(("off", dict(call.data)))
        hass.states.async_set(
            call.data["entity_id"], "off", {"supported_color_modes": ["brightness"]}, context=call.context
        )
        if call.data["entity_id"] in (groups or {}):
            for member in groups[call.data["entity_id"]]:
                hass.states.async_set(member, "off", {"supported_color_modes": ["brightness"]})
        sync_groups()

    hass.services.async_register("light", "turn_on", turn_on)
    hass.services.async_register("light", "turn_off", turn_off)
    return calls


class Flat:
    def __init__(self, hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
        self.hass, self.freezer = hass, freezer
        self.entries: dict[str, MockConfigEntry] = {}

    async def setup(self, monkeypatch, lights: dict[str, str] | None = None, **room_options) -> None:
        hass = self.hass

        async def fake_load(hass_, camera, neighbours):
            return FLOOR

        monkeypatch.setattr(home_module, "async_load_floor", fake_load)
        hass.states.async_set("camera.map", "idle", {"map_id": 7})
        hass.states.async_set("sun.sun", "below_horizon")
        for key in SENSORS:
            self.gone(key)
        home = MockConfigEntry(
            domain=DOMAIN, title="Flat", data={CONF_KIND: KIND_HOME}, options=dict(HOME_DEFAULTS), unique_id="home"
        )
        home.add_to_hass(hass)
        await hass.config_entries.async_setup(home.entry_id)
        await hass.async_block_till_done()
        for key in SENSORS:
            extra = {**room_options}
            if lights and key in lights:
                extra.update({CONF_LIGHT: lights[key], CONF_RUN_ON: 15, CONF_BRIGHTNESS: 40})
            entry = room_entry(key, **extra)
            entry.add_to_hass(hass)
            self.entries[key] = entry
            await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await self.set_fade(0, 0)
        for key, (_, location) in SENSORS.items():
            await hass.services.async_call(
                DOMAIN,
                "set_calibration",
                {
                    "room": self.entries[key].entry_id,
                    "calibration": {"map_id": 7, "location": list(location), "heading": 90},
                },
                blocking=True,
            )
        await hass.services.async_call(
            DOMAIN,
            "set_exit",
            {"room": f"binary_sensor.{SENSORS['hall'][0].lower()}", "x": 6000, "y": 0},
            blocking=True,
        )
        await self.tick(1)

    async def set_fade(self, fade_in: float, fade_out: float) -> None:
        for key, value in (("fade_in", fade_in), ("fade_out", fade_out)):
            await self.hass.services.async_call(
                "number", "set_value", {"entity_id": f"number.flat_{key}", "value": value}, blocking=True
            )

    def at(self, key: str, point) -> None:
        _, (lx, ly) = SENSORS[key]
        self.hass.states.async_set(f"sensor.{key}_x", str(point[0] - lx), {"unit_of_measurement": "mm"})
        self.hass.states.async_set(f"sensor.{key}_y", str(point[1] - ly), {"unit_of_measurement": "mm"})
        self.hass.states.async_set(f"binary_sensor.{key}_presence", "on")

    def gone(self, key: str) -> None:
        self.hass.states.async_set(f"binary_sensor.{key}_presence", "off")
        self.hass.states.async_set(f"sensor.{key}_x", "0", {"unit_of_measurement": "mm"})
        self.hass.states.async_set(f"sensor.{key}_y", "0", {"unit_of_measurement": "mm"})

    def sensor_for(self, point) -> str | None:
        for key, (name, _) in SENSORS.items():
            poly = POLYGONS[name]
            xs, ys = [p[0] for p in poly], [p[1] for p in poly]
            if min(xs) <= point[0] <= max(xs) and min(ys) <= point[1] <= max(ys):
                return key
        if 5800 <= point[0] <= 6200 and -400 <= point[1] < 0:
            return "hall"  # The radar sees the stair threshold being crossed.
        return None

    async def tick(self, seconds: float = 0.5) -> None:
        await self.hass.async_block_till_done()
        self.freezer.tick(timedelta(seconds=seconds))
        async_fire_time_changed(self.hass)
        await self.hass.async_block_till_done()

    async def walk(self, points, dt: float = 0.5) -> None:
        for point in points:
            seen = self.sensor_for(point)
            for key in SENSORS:
                if key == seen:
                    self.at(key, point)
                else:
                    self.gone(key)
            await self.tick(dt)

    async def idle(self, seconds: float) -> None:
        for key in SENSORS:
            self.gone(key)
        step = 1 if seconds <= 120 else 30
        for _ in range(int(seconds / step)):
            await self.tick(step)

    def people(self, key: str) -> int:
        return self.hass.states.get(f"binary_sensor.{SENSORS[key][0].lower()}").attributes.get("people")

    def occupied(self, key: str) -> bool:
        return self.hass.states.get(f"binary_sensor.{SENSORS[key][0].lower()}").state == "on"


def line(start, end, steps=8):
    return [
        [start[0] + (end[0] - start[0]) * i / steps, start[1] + (end[1] - start[1]) * i / steps]
        for i in range(steps + 1)
    ]


@pytest.fixture
def flat(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> Flat:
    return Flat(hass, freezer)


async def test_people_counted_through_doors(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    await flat.setup(monkeypatch)
    state = hass.states.get("binary_sensor.bedroom")
    assert state.attributes["mode"] == "map"
    await flat.walk([[1000, 3000]] * 4)
    assert flat.people("bed") == 1
    await flat.idle(600)  # sits still, the radar loses them
    assert flat.occupied("bed")
    await flat.walk(
        (line([1000, 3000], [3500, 1000], 5) + line([3500, 1000], [5500, 1000], 5))
        + line([5500, 1000], [9500, 1500], 8)
        + [[9500, 1500]] * 3
    )
    assert flat.people("bed") == 0
    assert not flat.occupied("bed")
    assert flat.people("bath") == 1
    assert flat.people("hall") == 0


async def test_second_person_leaving_keeps_still_person(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    await flat.setup(monkeypatch)
    await flat.walk([[1000, 3000]] * 4)
    await flat.idle(60)
    # Someone comes up the stairs, into the bedroom and back out.
    await flat.walk(line([6000, 100], [5500, 1000], 4) + line([5500, 1000], [2000, 1500], 8) + [[2000, 1500]] * 3)
    assert flat.people("bed") == 2
    await flat.walk(line([2000, 1500], [5500, 1000], 8) + [[5500, 1000]] * 3)
    assert flat.people("bed") == 1
    assert flat.occupied("bed")
    await flat.walk(line([5500, 1000], [6000, -200], 4))
    await flat.idle(3)
    assert flat.people("hall") == 0


async def test_overview_release_and_hold(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    await flat.setup(monkeypatch)
    await flat.walk([[1000, 3000]] * 4)
    await flat.idle(5)
    overview = hass.states.get("sensor.flat_overview")
    assert overview.state == "0"  # No live target; occupancy is held separately.
    sensors = {s["room"]: s for s in overview.attributes["sensors"]}
    assert sensors["Bedroom"]["map_ready"] and sensors["Bedroom"]["people"] == 1
    assert sensors["Bedroom"]["visible_people"] == 0
    assert sensors["Bedroom"]["entities"]["hold"] == "switch.bedroom_hold_occupancy"
    doors = {(d["a"], d["b"]) for d in overview.attributes["doors"]}
    assert ("Hall", "outside") in doors and ("Bedroom", "Hall") in doors
    await hass.services.async_call(DOMAIN, "release", {"room": "binary_sensor.bedroom"}, blocking=True)
    await flat.tick(1)
    assert not flat.occupied("bed")
    await flat.walk([[1000, 3000]] * 4)
    assert flat.occupied("bed")
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.bedroom_hold_occupancy"}, blocking=True)
    await flat.idle(3)
    assert not flat.occupied("bed")


async def test_map_mode_off_uses_distance_rule(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    await flat.setup(monkeypatch)
    await flat.walk([[1000, 3000]] * 4)
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.flat_map_mode"}, blocking=True)
    await flat.tick(1)
    assert hass.states.get("binary_sensor.bedroom").attributes["mode"] == "distance"
    await flat.idle(2)
    assert not flat.occupied("bed")  # default door range: every loss is leaving


async def test_door_arrival_lights_a_held_room_movement_does_not(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    mock_lights(hass)
    for light in ("light.bed", "light.bath"):
        hass.states.async_set(light, "off", {"supported_color_modes": ["brightness"]})
    await flat.setup(monkeypatch, lights={"bed": "light.bed", "bath": "light.bath"})
    manager = hass.data[DOMAIN]
    manager.home.set_setting("light_automation", False)
    for key in ("bed", "bath"):
        manager.home.tracking.counts[flat.entries[key].entry_id] = 1
    manager.home.set_setting("light_automation", True)
    await flat.idle(2)
    assert hass.states.get("light.bed").state == "off"
    assert hass.states.get("light.bath").state == "off"
    # Moving inside a held room (turning over in bed) switches nothing ...
    await flat.walk([[1000, 3000]] * 4)
    assert hass.states.get("light.bed").state == "off"
    # ... coming in through the door does, even though the count stays held.
    await flat.walk(line([9500, 1500], [5500, 1000], 8) + line([5500, 1000], [9500, 1500], 8) + [[9500, 1500]] * 3)
    assert hass.states.get("light.bath").state == "on"


async def test_daylight_release_lights_a_visible_occupied_room(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    mock_lights(hass)
    hass.states.async_set("light.bed", "off", {"supported_color_modes": ["brightness"]})
    await flat.setup(monkeypatch, lights={"bed": "light.bed"})
    hass.states.async_set("sun.sun", "above_horizon")
    await flat.walk([[1000, 3000]] * 4)
    assert flat.occupied("bed")
    assert hass.states.get("light.bed").state == "off"
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.bedroom_only_when_dark"}, blocking=True)
    await flat.tick(1)
    assert hass.states.get("light.bed").state == "on"


async def test_manual_off_survives_toilet_trip(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    calls = mock_lights(hass)
    hass.states.async_set("light.bed", "off", {"supported_color_modes": ["brightness"]})
    await flat.setup(monkeypatch, lights={"bed": "light.bed"})
    await flat.walk([[1000, 3000]] * 4)
    assert ("on", {"entity_id": "light.bed", "brightness_pct": 40}) in calls
    await flat.idle(20)
    # Switched off by hand in bed.
    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.bed"}, blocking=True, context=Context(user_id="user")
    )
    await flat.tick(1)
    assert hass.states.get("binary_sensor.bedroom").attributes["light_mode"] == "manual_off"
    calls.clear()
    await flat.walk(
        (line([1000, 3000], [3500, 1000], 5) + line([3500, 1000], [5500, 1000], 5))
        + line([5500, 1000], [9500, 1500], 8)
        + [[9500, 1500]] * 3
    )
    await flat.idle(120)
    await flat.walk(
        line([9500, 1500], [5500, 1000], 8)
        + (line([5500, 1000], [3500, 1000], 5) + line([3500, 1000], [1000, 3000], 5))
        + [[1000, 3000]] * 3
    )
    assert flat.occupied("bed")
    assert not [c for c in calls if c[1]["entity_id"] == "light.bed"], "stays off after the night trip"
    # Switched on by hand: automatic again, off after leaving.
    await flat.idle(20)
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.bed"}, blocking=True, context=Context(user_id="user")
    )
    await flat.tick(1)
    assert hass.states.get("binary_sensor.bedroom").attributes["light_mode"] == "auto"
    await flat.walk((line([1000, 3000], [3500, 1000], 5) + line([3500, 1000], [5500, 1000], 5)) + [[5500, 1000]] * 3)
    await flat.idle(20)
    assert hass.states.get("light.bed").state == "off"


async def test_manual_off_ends_after_empty_time(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    calls = mock_lights(hass)
    hass.states.async_set("light.bed", "off", {"supported_color_modes": ["brightness"]})
    await flat.setup(monkeypatch, lights={"bed": "light.bed"})
    await flat.walk([[1000, 3000]] * 4)
    await flat.idle(20)
    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.bed"}, blocking=True, context=Context(user_id="user")
    )
    await flat.walk((line([1000, 3000], [3500, 1000], 5) + line([3500, 1000], [5500, 1000], 5)) + [[5500, 1000]] * 3)
    await flat.idle(31 * 60)
    calls.clear()
    await flat.walk((line([5500, 1000], [3500, 1000], 5) + line([3500, 1000], [1000, 3000], 5)) + [[1000, 3000]] * 3)
    assert ("on", {"entity_id": "light.bed", "brightness_pct": 40}) in calls


async def test_voice_or_automation_off_counts_like_by_hand(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    """ "Licht aus" by voice or a dashboard slider runs through an automation;
    it must keep the light off just like the wall switch."""
    mock_lights(hass)
    hass.states.async_set("light.bed", "off", {"supported_color_modes": ["brightness"]})
    await flat.setup(monkeypatch, lights={"bed": "light.bed"})
    await flat.walk([[1000, 3000]] * 4)
    await flat.idle(20)
    automation = Context(parent_id="01AUTOMATION0000000000000")
    await hass.services.async_call("light", "turn_off", {"entity_id": "light.bed"}, blocking=True, context=automation)
    await flat.tick(1)
    assert hass.states.get("binary_sensor.bedroom").attributes["light_mode"] == "manual_off"
    # Turning over in bed does not bring it back.
    await flat.walk([[1200, 3100]] * 6)
    assert hass.states.get("light.bed").state == "off"
    # Brightness chosen through a voice command or slider is remembered as well.
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.bed", "brightness": 200}, blocking=True, context=automation
    )
    await hass.async_block_till_done()
    assert hass.data[DOMAIN].lights.brightness["light.bed"] == 200
    assert hass.states.get("binary_sensor.bedroom").attributes["light_mode"] == "auto"


async def test_light_automation_switch(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    calls = mock_lights(hass)
    hass.states.async_set("light.bed", "off", {"supported_color_modes": ["brightness"]})
    await flat.setup(monkeypatch, lights={"bed": "light.bed"})
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.flat_light_automation"}, blocking=True)
    await flat.walk([[1000, 3000]] * 4)
    assert not calls


async def test_fade_in_steps_and_fade_out_never_switches_on(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    real_sleep = asyncio.sleep

    async def no_wait(_seconds):  # the frozen clock would never let a fade step pass
        await real_sleep(0)

    monkeypatch.setattr(lights_module.asyncio, "sleep", no_wait)
    calls = mock_lights(hass, {"light.bed": ["light.bed_1", "light.bed_2"]})
    hass.states.async_set("light.bed", "off", {"entity_id": ["light.bed_1", "light.bed_2"]})
    for leaf in ("light.bed_1", "light.bed_2"):
        hass.states.async_set(leaf, "off", {"supported_color_modes": ["brightness"]})
    await flat.setup(monkeypatch, lights={"bed": "light.bed"})
    await flat.set_fade(0.5, 0.5)
    await flat.walk([[1000, 3000]] * 4)
    await hass.async_block_till_done(wait_background_tasks=True)
    steps = [c[1]["brightness"] for c in calls if c[0] == "on" and c[1]["entity_id"] == "light.bed_1"]
    assert len(steps) >= 3 and steps == sorted(steps) and steps[-1] == 102
    # One lamp switched off by hand at the switch; fading out leaves it alone.
    hass.states.async_set("light.bed_2", "off", {"supported_color_modes": ["brightness"]})
    calls.clear()
    await flat.walk((line([1000, 3000], [3500, 1000], 5) + line([3500, 1000], [5500, 1000], 5)) + [[5500, 1000]] * 3)
    await flat.idle(20)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not [c for c in calls if c[0] == "on" and c[1]["entity_id"] == "light.bed_2"]
    assert ("off", {"entity_id": "light.bed"}) in calls


@pytest.mark.parametrize("direction", ["enter", "off"])
async def test_native_fade_uses_interpolated_perceptual_waypoints(hass, flat, monkeypatch, direction):
    real_sleep = asyncio.sleep

    async def no_wait(_seconds):
        await real_sleep(0)

    monkeypatch.setattr(lights_module.asyncio, "sleep", no_wait)
    attrs = {"supported_color_modes": ["brightness"], "supported_features": 32, "brightness": 102}
    hass.states.async_set("light.bed", "off" if direction == "enter" else "on", attrs)
    calls = []

    async def record(call):
        calls.append((call.service, dict(call.data)))
        hass.states.async_set(
            "light.bed",
            "on" if call.service == "turn_on" else "off",
            {**attrs, "brightness": call.data.get("brightness", 102)},
            context=call.context,
        )

    hass.services.async_register("light", "turn_on", record)
    hass.services.async_register("light", "turn_off", record)
    await flat.setup(monkeypatch, lights={"bed": "light.bed"})
    await flat.set_fade(3, 3)
    controller = hass.data[DOMAIN].lights
    await controller.start_fade("light.bed", controller.groups()["light.bed"], direction)
    values = [data["brightness"] for service, data in calls if service == "turn_on"]
    transitions = [data["transition"] for service, data in calls if service == "turn_on"]
    assert len(values) >= 10, "native interpolation must follow the perceptual curve"
    assert values == sorted(values, reverse=direction == "off")
    if direction == "enter":
        assert values[0] == 1 and transitions[0] == 0, "off lamps start dim, never at their recalled on-level"
        assert values[-1] == 102
        transitions = transitions[1:]
    else:
        assert values[-1] == 1
        assert calls[-1][0] == "turn_off"
    assert all(value == 0.2 for value in transitions)
    assert len(transitions) <= 16, "device interpolation must not become a 20 Hz command stream"


def test_legacy_ghost_counts_migrate_once_preserving_occupancy():
    from types import SimpleNamespace
    from unittest.mock import Mock

    manager = SimpleNamespace(hass=None, saved={"map": {"people": {"hall": 14, "bed": 2, "bath": 0}}}, save=Mock())
    home = home_module.Home(manager, SimpleNamespace(entry_id="home"))
    assert home.tracking.counts == {"hall": 1, "bed": 1, "bath": 0}
    manager.save.assert_called_once()
    manager.saved["map"]["people"]["bed"] = 2
    home = home_module.Home(manager, SimpleNamespace(entry_id="home"))
    assert home.people("bed") == 2
    manager.save.assert_called_once()


async def test_own_sensor_near_wrong_wall_keeps_light_on(hass, flat, monkeypatch):
    mock_lights(hass)
    hass.states.async_set("light.bed", "off", {"supported_color_modes": ["brightness"]})
    await flat.setup(monkeypatch, lights={"bed": "light.bed"})
    for point in [[3700, 1900]] * 4 + [[4600, 1900]] * 8:
        flat.at("bed", point)  # Its projected point is across a wall, not the doorway.
        await flat.tick()
    assert flat.people("bed") == 1
    assert flat.people("hall") == 0
    assert hass.states.get("light.bed").state == "on"
    await flat.idle(60)
    assert flat.people("bed") == 1
    assert hass.states.get("light.bed").state == "on"


async def test_receiving_radar_cannot_be_locked_to_previous_room(hass, flat, monkeypatch):
    """A short observation gap hides the door passage, not the destination."""
    mock_lights(hass)
    hass.states.async_set("light.hall", "off", {"supported_color_modes": ["brightness"]})
    await flat.setup(monkeypatch, lights={"hall": "light.hall"})
    # Last source sighting and first receiving sighting are close enough for
    # nearest-neighbour matching, but the measured segment misses the door.
    for _ in range(4):
        flat.at("bed", [3700, 1900])
        await flat.tick()
    flat.gone("bed")
    for _ in range(8):
        flat.at("hall", [4600, 1900])
        await flat.tick()
    home = hass.data[DOMAIN].home
    assert home.tracking.observed(flat.entries["hall"].entry_id, home.tracking.last_step)
    assert not home.tracking.observed(flat.entries["bed"].entry_id, home.tracking.last_step)
    assert flat.occupied("hall")
    assert hass.states.get("light.hall").state == "on"
    # No invented wall crossing: the previous room remains held until there
    # is evidence of departure or the configured household limit applies.
    assert flat.occupied("bed")


async def test_household_limit_removes_the_place_someone_just_left(
    hass: HomeAssistant, flat: Flat, monkeypatch
) -> None:
    await flat.setup(monkeypatch)
    home = hass.data[DOMAIN].home
    hall = flat.entries["hall"].entry_id
    home.tracking.counts[hall] = 1  # a stale place nobody confirmed for a long time
    await flat.walk([[1000, 3000]] * 4)
    assert flat.people("bed") == 1 and flat.people("hall") == 1
    # Vanishes in the middle of the bedroom (a departure the radar missed) and
    # turns up in the bathroom a few seconds later.
    await flat.idle(4)
    await flat.walk([[9500, 1500]] * 6)
    assert flat.people("bath") == 1
    assert flat.people("bed") == 0, "the person who vanished moved on"
    assert flat.people("hall") == 1, "the limit allows a second, unseen person"


async def test_inflated_counts_shrink_to_the_household(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    await flat.setup(monkeypatch)
    home = hass.data[DOMAIN].home
    for key, n in (("bed", 3), ("hall", 2), ("bath", 3)):
        home.tracking.counts[flat.entries[key].entry_id] = n
    await flat.walk([[9500, 1500]] * 4)
    assert sum(flat.people(k) for k in ("bed", "hall", "bath")) == 2
    assert flat.people("bath") >= 1, "the visible person stays"
    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.flat_people_in_the_home_at_most", "value": 1}, blocking=True
    )
    await flat.tick(1)
    assert [flat.people(k) for k in ("bed", "hall", "bath")] == [0, 0, 1]


async def test_dropped_switch_on_is_repeated(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    calls = mock_lights(hass)
    hass.states.async_set("light.bed", "off", {"supported_color_modes": ["brightness"]})
    original = hass.services._services["light"]["turn_on"].job.target
    dropped = []

    async def flaky(call):
        if not dropped:
            dropped.append(call)  # the cloud swallowed the first command
            return
        await original(call)

    hass.services.async_register("light", "turn_on", flaky)
    await flat.setup(monkeypatch, lights={"bed": "light.bed"})
    await flat.walk([[1000, 3000]] * 4)
    assert dropped and hass.states.get("light.bed").state == "off"
    await flat.walk([[1000, 3000]] * 24)
    assert hass.states.get("light.bed").state == "on"
    assert len([c for c in calls if c[0] == "on"]) == 1


async def test_echo_right_in_front_of_the_sensor_is_no_person(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    await flat.setup(monkeypatch)
    _, (lx, ly) = SENSORS["hall"]
    for _ in range(10):
        flat.at("hall", [lx + 10, ly + 200])  # 20 cm in front of the hall sensor
        await flat.tick(0.5)
    assert flat.people("hall") == 0


async def _leave_with_lights_switched_off(hass: HomeAssistant, flat: Flat) -> None:
    """In bed, out to the hall, lights still on: switch everything off by hand and leave."""
    await flat.walk([[1000, 3000]] * 4)
    await flat.walk(line([1000, 3000], [3500, 1000], 6) + line([3500, 1000], [5500, 1000], 6) + [[5500, 1000]] * 3)
    assert hass.states.get("light.bed").state == "on" and hass.states.get("light.hall").state == "on"
    # The radar missed leaving the bedroom: still held there.
    hass.data[DOMAIN].home.tracking.counts[flat.entries["bed"].entry_id] = 1
    await flat.idle(12)
    for light in ("light.bed", "light.hall"):
        await hass.services.async_call(
            "light", "turn_off", {"entity_id": light}, blocking=True, context=Context(user_id="user")
        )
    await flat.tick(1)
    assert hass.states.get("binary_sensor.bedroom").attributes["light_mode"] == "manual_off"
    assert hass.states.get("binary_sensor.hall").attributes["light_mode"] == "manual_off"
    # On the way out the radar loses and finds the person again near the stairs:
    # that is no homecoming, the hall light stays off.
    await flat.walk(line([5500, 1000], [6000, 150], 6))
    assert hass.states.get("light.hall").state == "off"


async def test_lights_come_back_when_returning_after_hours(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    mock_lights(hass)
    for light in ("light.bed", "light.hall"):
        hass.states.async_set(light, "off", {"supported_color_modes": ["brightness"]})
    await flat.setup(monkeypatch, lights={"bed": "light.bed", "hall": "light.hall"})
    await _leave_with_lights_switched_off(hass, flat)
    await flat.idle(3 * 3600)
    assert hass.states.get("light.hall").state == "off"
    await flat.walk(line([6000, 150], [5500, 1000], 6) + [[5500, 1000]] * 3)
    assert hass.states.get("light.hall").state == "on", "back home: hall light on"
    await flat.walk(line([5500, 1000], [3500, 1000], 6) + line([3500, 1000], [1000, 3000], 6) + [[1000, 3000]] * 3)
    assert hass.states.get("light.bed").state == "on", "bedroom light follows"


async def test_hall_light_on_after_a_short_errand(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    mock_lights(hass)
    for light in ("light.bed", "light.hall"):
        hass.states.async_set(light, "off", {"supported_color_modes": ["brightness"]})
    await flat.setup(monkeypatch, lights={"bed": "light.bed", "hall": "light.hall"})
    await _leave_with_lights_switched_off(hass, flat)
    await flat.idle(20 * 60)
    await flat.walk(line([6000, 150], [5500, 1000], 6) + [[5500, 1000]] * 3)
    assert hass.states.get("light.hall").state == "on", "coming in from outside ends switched off by hand"


async def test_lost_at_unseen_door_lights_next_room_without_moving_anyone(
    hass: HomeAssistant, flat: Flat, monkeypatch
) -> None:
    # No sensor sees behind the doors: whoever vanishes at the bedroom door
    # walking towards it gets the hall lit at once, at full brightness.
    monkeypatch.setattr(home_module, "covers", lambda *args, **kwargs: False)
    real_sleep = asyncio.sleep

    async def no_wait(_seconds):  # the frozen clock would never let a fade step pass
        await real_sleep(0)

    monkeypatch.setattr(lights_module.asyncio, "sleep", no_wait)
    calls = mock_lights(hass)
    for light in ("light.bed", "light.hall"):
        hass.states.async_set(light, "off", {"supported_color_modes": ["brightness"]})
    await flat.setup(monkeypatch, lights={"bed": "light.bed", "hall": "light.hall"})
    await flat.walk([[1500, 1000]] * 4 + line([1500, 1000], [3700, 1000], 5))
    calls.clear()
    await flat.idle(2)
    hall = [c[1] for c in calls if c[0] == "on" and c[1]["entity_id"] == "light.hall"]
    assert hall and hall[-1]["brightness_pct"] == 40
    # Nobody counted in the hall, the bedroom stays held with its light on.
    assert flat.occupied("bed") and not flat.occupied("hall")
    assert hass.states.get("light.bed").state == "on"
    # Nobody turns up: the hall fades out like a pre-light.
    await flat.idle(25)
    assert hass.states.get("light.hall").state == "off"
    assert hass.states.get("light.bed").state == "on"


async def test_map_that_failed_at_start_is_loaded_again(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    # The robot's camera entity exists but is not ready yet when the maps load.
    attempts = []

    async def flaky_load(hass_, camera, neighbours):
        attempts.append(camera)
        if len(attempts) == 1:
            raise HomeAssistantError("Camera not found")
        return FLOOR

    await flat.setup(monkeypatch)
    manager = hass.data[DOMAIN]
    monkeypatch.setattr(home_module, "async_load_floor", flaky_load)
    manager.home.floors.clear()
    manager.home.reload_maps()
    await hass.async_block_till_done()
    assert manager.home.errors
    for _ in range(16):
        await flat.tick(1)
    assert not manager.home.errors
    assert manager.home.floors
