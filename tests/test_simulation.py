"""Public dry-run service must exercise decisions without touching the home."""

from copy import deepcopy

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.radar_occupancy import get_manager
from custom_components.radar_occupancy.simulation import room_route, simulate
from tests.test_map_mode import Flat


@pytest.fixture
def flat(hass, freezer):
    return Flat(hass, freezer)


@pytest.mark.parametrize("held", [False, True])
async def test_simulation_isolated(hass, flat, monkeypatch, held):
    await flat.setup(monkeypatch, lights={"bath": "light.bath"})
    hass.states.async_set("light.bath", "off", {"supported_color_modes": ["brightness"]})
    manager = get_manager(hass)
    before_states = {s.entity_id: s.as_dict() for s in hass.states.async_all()}
    before_saved = deepcopy(manager.saved)
    counts = dict(manager.home.tracking.counts)
    room = flat.entries["bath"].entry_id
    result = simulate(manager, room_route(manager, room), held=held, ignore_restrictions=True)
    # An empty room is entered: light on. In a held room, moving around inside
    # is no entry (somebody turning over in bed must not get light).
    assert any(c["service"] == "turn_on" for c in result["commands"]) is not held
    assert not any(c["service"] == "turn_off" for c in result["commands"]), "Sitting still is not an exit"
    assert result["timeline"][-1]["people"][room] >= 1
    assert manager.saved == before_saved
    assert manager.home.tracking.counts == counts
    assert {s.entity_id: s.as_dict() for s in hass.states.async_all()} == before_states


async def test_simulation_service_validation(hass, flat, monkeypatch):
    await flat.setup(monkeypatch, lights={"bath": "light.bath"})
    hass.states.async_set("light.bath", "off", {"supported_color_modes": ["brightness"]})
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("radar_occupancy", "simulate", {}, blocking=True, return_response=True)
    with pytest.raises(HomeAssistantError):
        simulate(get_manager(hass), [{"room": flat.entries["bath"].entry_id}])
    report = await hass.services.async_call(
        "radar_occupancy",
        "simulate",
        {"room": flat.entries["bath"].entry_id, "ignore_restrictions": True},
        blocking=True,
        return_response=True,
    )
    assert report["dry_run"]
    assert report["commands"]


async def test_walk_through_rooms_and_exit(hass, flat, monkeypatch):
    await flat.setup(monkeypatch, lights={"bed": "light.bed", "bath": "light.bath"})
    for entity in ("light.bed", "light.bath"):
        hass.states.async_set(entity, "off", {"supported_color_modes": ["brightness"]})
    manager = get_manager(hass)
    bed, hall, bath = (flat.entries[k].entry_id for k in ("bed", "hall", "bath"))
    route = [{"room": bed, "x": 1000, "y": 3000, "seconds": 4}]
    from tests.test_map_mode import line

    route += [
        {"room": bed, "x": x, "y": y, "seconds": 0.5}
        for x, y in (line([1000, 3000], [3500, 1000], 5) + line([3500, 1000], [5500, 1000], 5))
    ]
    route += [{"room": hall, "x": x, "y": y, "seconds": 0.5} for x, y in line([5500, 1000], [9500, 1500], 8)]
    route += [{"room": bath, "x": 9500, "y": 1500, "seconds": 20}]
    report = simulate(manager, route, ignore_restrictions=True)
    assert report["timeline"][-1]["people"][bed] == 0
    assert report["timeline"][-1]["people"][bath] == 1
    assert any(c["service"] == "turn_off" and c["entity_id"] == "light.bed" for c in report["commands"])
    assert any(c["service"] == "turn_on" and c["entity_id"] == "light.bath" for c in report["commands"])


async def test_darkness_and_unavailable_report(hass, flat, monkeypatch):
    await flat.setup(monkeypatch, lights={"bath": "light.bath"})
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set("light.bath", "off")
    manager = get_manager(hass)
    room = flat.entries["bath"].entry_id
    report = simulate(manager, room_route(manager, room))
    assert not report["commands"]
    hass.states.async_set("light.bath", "unavailable")
    report = simulate(manager, room_route(manager, room), ignore_restrictions=True)
    assert "light.bath" in report["unavailable_lights"]
