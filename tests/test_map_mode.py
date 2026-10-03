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
    await flat.walk(line([1000, 3000], [5500, 1000], 10) + line([5500, 1000], [9500, 1500], 8) + [[9500, 1500]] * 3)
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
    await flat.walk(line([5500, 1000], [6000, 200], 4))
    await flat.idle(3)
    assert flat.people("hall") == 0


async def test_overview_release_and_hold(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    await flat.setup(monkeypatch)
    await flat.walk([[1000, 3000]] * 4)
    await flat.idle(5)
    overview = hass.states.get("sensor.flat_overview")
    assert overview.state == "1"
    sensors = {s["room"]: s for s in overview.attributes["sensors"]}
    assert sensors["Bedroom"]["map_ready"] and sensors["Bedroom"]["people"] == 1
    assert sensors["Bedroom"]["entities"]["hold"] == "switch.bedroom_hold_occupancy"
    doors = {(d["a"], d["b"]) for d in overview.attributes["doors"]}
    assert ("Hall", "draußen") in doors and ("Bedroom", "Hall") in doors
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
    await flat.walk(line([1000, 3000], [5500, 1000], 10) + line([5500, 1000], [9500, 1500], 8) + [[9500, 1500]] * 3)
    await flat.idle(120)
    await flat.walk(line([9500, 1500], [5500, 1000], 8) + line([5500, 1000], [1000, 3000], 10) + [[1000, 3000]] * 3)
    assert flat.occupied("bed")
    assert not [c for c in calls if c[1]["entity_id"] == "light.bed"], "stays off after the night trip"
    # Switched on by hand: automatic again, off after leaving.
    await flat.idle(20)
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.bed"}, blocking=True, context=Context(user_id="user")
    )
    await flat.tick(1)
    assert hass.states.get("binary_sensor.bedroom").attributes["light_mode"] == "auto"
    await flat.walk(line([1000, 3000], [5500, 1000], 10) + [[5500, 1000]] * 3)
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
    await flat.walk(line([1000, 3000], [5500, 1000], 10) + [[5500, 1000]] * 3)
    await flat.idle(31 * 60)
    calls.clear()
    await flat.walk(line([5500, 1000], [1000, 3000], 10) + [[1000, 3000]] * 3)
    assert ("on", {"entity_id": "light.bed", "brightness_pct": 40}) in calls


async def test_other_automation_is_not_by_hand(hass: HomeAssistant, flat: Flat, monkeypatch) -> None:
    mock_lights(hass)
    hass.states.async_set("light.bed", "off", {"supported_color_modes": ["brightness"]})
    await flat.setup(monkeypatch, lights={"bed": "light.bed"})
    await flat.walk([[1000, 3000]] * 4)
    await flat.idle(20)
    automation = Context(parent_id="01AUTOMATION0000000000000")
    await hass.services.async_call("light", "turn_off", {"entity_id": "light.bed"}, blocking=True, context=automation)
    await flat.tick(1)
    assert hass.states.get("binary_sensor.bedroom").attributes["light_mode"] == "auto"
    # Brightness chosen by another automation is not remembered; by hand it is.
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.bed", "brightness": 200}, blocking=True, context=automation
    )
    # Service completion precedes the queued state_changed callbacks.
    await hass.async_block_till_done()
    assert "light.bed" not in hass.data[DOMAIN].lights.brightness
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.bed", "brightness": 90}, blocking=True, context=Context(user_id="u")
    )
    await hass.async_block_till_done()
    assert hass.data[DOMAIN].lights.brightness["light.bed"] == 90


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
    await flat.walk(line([1000, 3000], [5500, 1000], 10) + [[5500, 1000]] * 3)
    await flat.idle(20)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not [c for c in calls if c[0] == "on" and c[1]["entity_id"] == "light.bed_2"]
    assert ("off", {"entity_id": "light.bed"}) in calls
