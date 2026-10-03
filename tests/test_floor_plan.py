"""Map mode on a floor plan image: no robot vacuum, outlines and doors drawn by hand."""

import struct
import zlib
from datetime import timedelta
from pathlib import Path

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.radar_occupancy.const import (
    CONF_IMAGE,
    CONF_IMAGE_WIDTH,
    CONF_KIND,
    CONF_MAP_CAMERA,
    CONF_PRESENCE,
    CONF_X,
    CONF_Y,
    DEFAULTS,
    DOMAIN,
    HOME_DEFAULTS,
    KIND_HOME,
    KIND_PLAN,
    KIND_ROOM,
    PLAN_PREFIX,
)
from custom_components.radar_occupancy.maps import InvalidImage, image_info, plan_floor, plan_path


def png(width: int, height: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    pixels = zlib.compress(b"".join(b"\x00" + b"\xff" * width for _ in range(height)))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")


def jpeg(width: int, height: int) -> bytes:
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, height, width, 1) + b"\x01\x11\x00"
    return b"\xff\xd8" + app0 + sof + b"\xff\xd9"


def test_image_info() -> None:
    assert image_info(png(110, 40)) == (110, 40, "image/png")
    assert image_info(jpeg(640, 480)) == (640, 480, "image/jpeg")
    with pytest.raises(InvalidImage):
        image_info(b"GIF89a....")


def test_plan_path_stays_in_www(hass: HomeAssistant, tmp_path: Path) -> None:
    hass.config.config_dir = str(tmp_path)
    assert plan_path(hass, "plans/ground.png") == tmp_path / "www" / "plans" / "ground.png"
    assert plan_path(hass, "/local/plans/ground.png") == tmp_path / "www" / "plans" / "ground.png"
    with pytest.raises(InvalidImage):
        plan_path(hass, "../secrets.yaml")


def test_plan_floor_maps_pixels_to_millimetres() -> None:
    floor = plan_floor("abc", b"x", 1100, 400, "image/png", 11.0)
    points = floor["calibration_points"]
    # 10 mm per pixel; map Y points up, image Y down.
    assert points[0] == {"vacuum": {"x": 0, "y": 4000}, "map": {"x": 0, "y": 0}}
    assert points[1]["vacuum"]["x"] == pytest.approx(11000)
    assert points[2] == {"vacuum": {"x": 0, "y": 0}, "map": {"x": 0, "y": 400}}
    assert floor["camera"] == PLAN_PREFIX + "abc"
    assert floor["image_path"].startswith("/api/radar_occupancy/map/abc?v=")
    assert plan_floor("abc", b"x", 1100, 400, "image/png", 12.0)["map_id"] != floor["map_id"]


async def test_config_flow_checks_the_image(hass: HomeAssistant, tmp_path: Path) -> None:
    hass.config.config_dir = str(tmp_path)
    (tmp_path / "www").mkdir()
    (tmp_path / "www" / "ground.png").write_bytes(png(110, 40))
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert "plan" in result["menu_options"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "plan"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Ground floor", CONF_IMAGE: "missing.png", CONF_IMAGE_WIDTH: 11}
    )
    assert result["errors"] == {CONF_IMAGE: "plan_image"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Ground floor", CONF_IMAGE: "ground.png", CONF_IMAGE_WIDTH: 11}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {CONF_KIND: KIND_PLAN}


# Bedroom 0..4000 x 0..4000, hall 4000..8000 x 0..2000; door at (4000, 1000).
OUTLINES = {
    "bed": [[0, 0], [4000, 0], [4000, 4000], [0, 4000]],
    "hall": [[4000, 0], [8000, 0], [8000, 2000], [4000, 2000]],
}
LOCATIONS = {"bed": (2000, 0), "hall": (6000, -500)}


class Plan:
    def __init__(self, hass: HomeAssistant, freezer: FrozenDateTimeFactory, tmp_path: Path) -> None:
        self.hass, self.freezer, self.tmp_path = hass, freezer, tmp_path
        self.rooms: dict[str, MockConfigEntry] = {}

    async def setup(self) -> None:
        hass = self.hass
        hass.config.config_dir = str(self.tmp_path)
        (self.tmp_path / "www").mkdir()
        (self.tmp_path / "www" / "ground.png").write_bytes(png(1100, 400))
        hass.states.async_set("sun.sun", "below_horizon")
        for key in OUTLINES:
            self.gone(key)
        home = MockConfigEntry(
            domain=DOMAIN, title="Flat", data={CONF_KIND: KIND_HOME}, options=dict(HOME_DEFAULTS), unique_id="home"
        )
        plan = MockConfigEntry(
            domain=DOMAIN,
            title="Ground floor",
            data={CONF_KIND: KIND_PLAN},
            options={CONF_IMAGE: "ground.png", CONF_IMAGE_WIDTH: 11},
        )
        for entry in (home, plan):
            entry.add_to_hass(hass)
            await hass.config_entries.async_setup(entry.entry_id)
        for key in OUTLINES:
            entry = MockConfigEntry(
                domain=DOMAIN,
                title=key.title(),
                data={CONF_KIND: KIND_ROOM},
                options={
                    **DEFAULTS,
                    CONF_PRESENCE: f"binary_sensor.{key}_presence",
                    CONF_X: f"sensor.{key}_x",
                    CONF_Y: f"sensor.{key}_y",
                    CONF_MAP_CAMERA: PLAN_PREFIX + plan.entry_id,
                },
            )
            entry.add_to_hass(hass)
            self.rooms[key] = entry
            await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        manager = hass.data[DOMAIN]
        await manager.home.async_load_maps()
        self.floor = manager.home.floors[PLAN_PREFIX + plan.entry_id]
        for key, outline in OUTLINES.items():
            room = self.rooms[key].entry_id
            calibration = {"map_id": self.floor["map_id"], "location": list(LOCATIONS[key]), "heading": 90}
            await self.call("set_calibration", room=room, calibration=calibration)
            await self.call("set_boundary", room=room, points=outline)
        await self.call("set_door", room=self.rooms["bed"].entry_id, to=self.rooms["hall"].entry_id, x=4000, y=1000)
        await self.call("set_door", room=self.rooms["hall"].entry_id, to="outside", x=6000, y=0)
        await self.tick(1)

    async def call(self, service: str, **data) -> None:
        await self.hass.services.async_call(DOMAIN, service, data, blocking=True)

    def at(self, key: str, point) -> None:
        lx, ly = LOCATIONS[key]
        self.hass.states.async_set(f"sensor.{key}_x", str(point[0] - lx), {"unit_of_measurement": "mm"})
        self.hass.states.async_set(f"sensor.{key}_y", str(point[1] - ly), {"unit_of_measurement": "mm"})
        self.hass.states.async_set(f"binary_sensor.{key}_presence", "on")

    def gone(self, key: str) -> None:
        self.hass.states.async_set(f"binary_sensor.{key}_presence", "off")
        self.hass.states.async_set(f"sensor.{key}_x", "0", {"unit_of_measurement": "mm"})
        self.hass.states.async_set(f"sensor.{key}_y", "0", {"unit_of_measurement": "mm"})

    async def tick(self, seconds: float = 0.5) -> None:
        await self.hass.async_block_till_done()
        self.freezer.tick(timedelta(seconds=seconds))
        async_fire_time_changed(self.hass)
        await self.hass.async_block_till_done()

    async def walk(self, points) -> None:
        for point in points:
            inside = "bed" if point[0] < 4000 else "hall"
            for key in OUTLINES:
                self.at(key, point) if key == inside else self.gone(key)
            await self.tick()

    def people(self, key: str) -> int:
        return self.hass.states.get(f"binary_sensor.{key}").attributes.get("people")


def line(start, end, steps=8):
    return [[start[i] + (end[i] - start[i]) * k / steps for i in range(2)] for k in range(steps + 1)]


async def test_people_counted_on_a_floor_plan(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tmp_path: Path
) -> None:
    plan = Plan(hass, freezer, tmp_path)
    await plan.setup()
    state = hass.states.get("binary_sensor.bed")
    assert state.attributes["mode"] == "map"
    await plan.walk([[1000, 3000]] * 4)
    assert plan.people("bed") == 1
    for _ in range(20):  # sitting still: the radar loses them
        plan.gone("bed")
        await plan.tick(30)
    assert hass.states.get("binary_sensor.bed").state == "on"
    await plan.walk((line([1000, 3000], [3500, 1000], 5) + line([3500, 1000], [5500, 1000], 5)) + [[5500, 1000]] * 3)
    assert plan.people("bed") == 0
    assert plan.people("hall") == 1
    state = hass.states.get("binary_sensor.hall")
    assert state.attributes["reason"] == "moved"
    assert (state.attributes["reason_from"], state.attributes["reason_to"]) == ("Bed", "Hall")
    # Labels for the card come from the drawn outlines.
    overview = hass.states.get("sensor.flat_overview").attributes
    floor = next(iter(overview["floors"].values()))
    assert floor["name"] == "Ground floor"
    assert {r["name"] for r in floor["rooms"]} == {"Bed", "Hall"}


async def test_door_to_the_same_room_is_refused(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tmp_path: Path
) -> None:
    plan = Plan(hass, freezer, tmp_path)
    await plan.setup()
    room = plan.rooms["bed"].entry_id
    with pytest.raises(HomeAssistantError):
        await plan.call("set_door", room=room, to=room, x=1, y=1)
    await plan.call("set_door", room=room, clear=True)
    assert hass.data[DOMAIN].home.data["doors"].get(room) is None


async def test_plan_image_is_served(hass: HomeAssistant, freezer, tmp_path: Path, hass_client) -> None:
    assert await async_setup_component(hass, "http", {})
    plan = Plan(hass, freezer, tmp_path)
    await plan.setup()
    client = await hass_client()
    path = plan.floor["image_path"].split("?")[0]
    response = await client.get(path)
    assert response.status == 200
    assert response.headers["Content-Type"] == "image/png"


async def test_diagnostics(hass: HomeAssistant, freezer: FrozenDateTimeFactory, tmp_path: Path) -> None:
    from custom_components.radar_occupancy.diagnostics import async_get_config_entry_diagnostics

    plan = Plan(hass, freezer, tmp_path)
    await plan.setup()
    entries = {e.data[CONF_KIND]: e for e in hass.config_entries.async_entries(DOMAIN)}
    home = await async_get_config_entry_diagnostics(hass, entries[KIND_HOME])
    assert home["home"]["marked_doors"]
    floor = await async_get_config_entry_diagnostics(hass, entries[KIND_PLAN])
    assert "image" not in floor["floor"] and floor["floor"]["width"] == 1100
    room = await async_get_config_entry_diagnostics(hass, plan.rooms["bed"])
    assert room["on_map"] is True and room["map"]["calibrated"]
