"""Animated positions, simultaneous people, light takeover and cleanup."""

from copy import deepcopy

import pytest
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError

from custom_components.radar_occupancy import get_manager
from custom_components.radar_occupancy.simulation_session import SimulationSession
from tests.test_map_mode import Flat, mock_lights


@pytest.fixture
def flat(hass, freezer):
    return Flat(hass, freezer)


async def elapsed(flat, seconds):
    for _ in range(round(seconds * 2)):
        await flat.tick(0.5)


async def start(hass, persons, **options):
    await hass.async_block_till_done()
    await hass.services.async_call(
        "radar_occupancy",
        "start_simulation",
        {"persons": persons, "ignore_restrictions": True, **options},
        blocking=True,
    )
    return get_manager(hass).simulation


async def test_multiple_animated_people_leave_one_behind(hass, flat, monkeypatch):
    await flat.setup(monkeypatch, lights={"bed": "light.bed", "hall": "light.hall"})
    hass.states.async_set("light.bed", "off")
    hass.states.async_set("light.hall", "off")
    manager = get_manager(hass)
    await hass.async_block_till_done()
    before = deepcopy(manager.saved)
    bed, hall = (flat.entries[k].entry_id for k in ("bed", "hall"))
    session = await start(
        hass,
        [
            {
                "id": "Walker",
                "route": [
                    {"room": bed, "x": 1000, "y": 3000, "seconds": 6},
                    {"room": bed, "x": 3500, "y": 1000, "seconds": 4},
                    {"room": hall, "x": 5500, "y": 1000, "seconds": 4},
                    {"room": hall, "x": 5500, "y": 1000, "seconds": 30},
                ],
            },
            {"id": "Sitting", "route": [{"room": bed, "x": 2900, "y": 3000, "seconds": 6}]},
        ],
    )
    await elapsed(flat, 5)
    assert session.sandbox.home.people(bed) == 2
    assert len(session.snapshot()["targets"]) == 2
    await elapsed(flat, 4)
    moving = next(t for t in session.targets if t["person"] == "Walker")
    assert 1000 < moving["map"][0] < 5500
    await elapsed(flat, 7)
    assert session.sandbox.home.people(bed) == 1
    assert session.sandbox.home.people(hall) == 1
    assert session.sandbox.lights.state["light.bed"].occupied
    assert hass.states.get("light.bed").state == "off"
    assert manager.saved == before
    assert manager.home.people(bed) == 0
    await session.stop()
    assert manager.simulation is None


async def test_live_lights_restore_without_writing_sensor_positions(hass, flat, monkeypatch):
    await flat.setup(monkeypatch, lights={"bed": "light.bed"})
    mock_lights(hass)
    hass.states.async_set("light.bed", "off", {"supported_color_modes": ["brightness"]})
    manager = get_manager(hass)
    bed = flat.entries["bed"].entry_id
    before_inputs = {i: hass.states.get(i).state for i in manager.rooms[bed].inputs}
    session = await start(
        hass, [{"id": "Test", "route": [{"room": bed, "x": 1000, "y": 3000, "seconds": 20}]}], live_lights=True
    )
    await elapsed(flat, 3)
    assert hass.states.get("light.bed").state == "on"
    assert hass.states.get("light.bed").attributes["brightness"] == 102
    assert manager.home.people(bed) == 0
    assert {i: hass.states.get(i).state for i in before_inputs} == before_inputs
    await session.stop()
    await hass.async_block_till_done()
    assert hass.states.get("light.bed").state == "off"
    assert not manager.home.snapshot()["simulation"]["running"]


async def test_master_off_stops_and_restores_live_test(hass, flat, monkeypatch):
    await flat.setup(monkeypatch, lights={"bed": "light.bed"})
    mock_lights(hass)
    hass.states.async_set("light.bed", "off")
    manager = get_manager(hass)
    await start(
        hass,
        [{"id": "Test", "route": [{"room": flat.entries["bed"].entry_id, "x": 1000, "y": 3000, "seconds": 30}]}],
        live_lights=True,
    )
    await elapsed(flat, 3)
    assert hass.states.get("light.bed").state == "on"
    manager.home.set_setting("light_automation", False)
    await hass.async_block_till_done()
    assert manager.simulation is None
    assert hass.states.get("light.bed").state == "off"
    with pytest.raises(HomeAssistantError):
        await start(hass, [{"id": "Test", "route": [{"seconds": 1}]}], live_lights=True)
    assert manager.simulation is None


async def test_auto_stop_and_duplicate_ids(hass, flat, monkeypatch):
    await flat.setup(monkeypatch)
    person = {"id": "Test", "route": [{"room": flat.entries["bed"].entry_id, "x": 1000, "y": 3000, "seconds": 2}]}
    with pytest.raises(HomeAssistantError):
        await start(hass, [person, person])
    session = await start(hass, [person])
    await elapsed(flat, 3)
    assert not session.running
    assert get_manager(hass).simulation is None


async def test_interpolation_keeps_final_position_and_dropout():
    path = [(4, ("floor", [0, 1000], "room")), (8, ("floor", [2000, 1000], "room")), (10, None)]
    assert SimulationSession.position(path, 6)[1] == [1000, 1000]
    assert SimulationSession.position(path, 9) is None
    assert SimulationSession.position(path, 11) is None


async def test_user_light_change_survives_stop(hass, flat, monkeypatch):
    await flat.setup(monkeypatch, lights={"bed": "light.bed"})
    mock_lights(hass)
    hass.states.async_set("light.bed", "off")
    session = await start(
        hass,
        [{"id": "Test", "route": [{"room": flat.entries["bed"].entry_id, "x": 1000, "y": 3000, "seconds": 30}]}],
        live_lights=True,
    )
    await elapsed(flat, 3)
    hass.states.async_set("light.bed", "on", {"brightness": 77}, context=Context(user_id="user"))
    await hass.async_block_till_done()
    await session.stop()
    assert hass.states.get("light.bed").state == "on"
    assert hass.states.get("light.bed").attributes["brightness"] == 77


async def test_live_two_people_last_exit_switches_off(hass, flat, monkeypatch):
    await flat.setup(monkeypatch, lights={"bed": "light.bed"})
    mock_lights(hass)
    hass.states.async_set("light.bed", "off", {"supported_color_modes": ["brightness"]})
    bed, hall = (flat.entries[k].entry_id for k in ("bed", "hall"))
    session = await start(
        hass,
        [
            {
                "id": "First",
                "route": [
                    {"room": bed, "x": 1000, "y": 3000, "seconds": 6},
                    {"room": bed, "x": 3500, "y": 1000, "seconds": 4},
                    {"room": hall, "x": 5500, "y": 1000, "seconds": 4},
                    {"room": hall, "x": 5500, "y": 1000, "seconds": 50},
                ],
            },
            {
                "id": "Second",
                "route": [
                    {"room": bed, "x": 2900, "y": 3000, "seconds": 20},
                    {"room": bed, "x": 3500, "y": 1000, "seconds": 4},
                    {"room": hall, "x": 6500, "y": 1000, "seconds": 4},
                    {"room": hall, "x": 6500, "y": 1000, "seconds": 40},
                ],
            },
        ],
        live_lights=True,
    )
    await elapsed(flat, 16)
    assert session.sandbox.home.people(bed) == 1
    assert hass.states.get("light.bed").state == "on"
    await elapsed(flat, 30)
    assert session.sandbox.home.people(bed) == 0
    assert hass.states.get("light.bed").state == "off"
    await session.stop()


async def test_live_applies_brightness_to_already_on_light_then_restores(hass, flat, monkeypatch):
    await flat.setup(monkeypatch, lights={"bed": "light.bed"})
    mock_lights(hass)
    hass.states.async_set("light.bed", "on", {"brightness": 200, "supported_color_modes": ["brightness"]})
    session = await start(
        hass,
        [{"id": "Test", "route": [{"room": flat.entries["bed"].entry_id, "x": 1000, "y": 3000, "seconds": 20}]}],
        live_lights=True,
    )
    await elapsed(flat, 3)
    assert hass.states.get("light.bed").attributes["brightness"] == 102
    await session.stop()
    await hass.async_block_till_done()
    assert hass.states.get("light.bed").state == "on"
    assert hass.states.get("light.bed").attributes["brightness"] == 200
