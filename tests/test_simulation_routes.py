"""Automatic routes honor doors, concave geometry and independent walkers."""

import math
from itertools import pairwise

import pytest

from custom_components.radar_occupancy import get_manager
from custom_components.radar_occupancy.simulation_routes import RoomPaths, automatic_routes, segment_inside
from tests.test_map_mode import Flat


@pytest.fixture
def flat(hass, freezer):
    return Flat(hass, freezer)


def test_concave_path_stays_inside():
    polygon = [[0, 0], [4000, 0], [4000, 1000], [1000, 1000], [1000, 4000], [0, 4000]]
    paths = RoomPaths(polygon)
    a, b = [500, 3500], [3500, 500]
    assert not segment_inside(a, b, polygon)
    path = paths.path(a, b)
    assert len(path) > 2
    assert all(segment_inside(a, b, polygon) for a, b in pairwise(path))


async def test_automatic_walks_independent_and_use_doors(hass, flat, monkeypatch):
    await flat.setup(monkeypatch)
    manager = get_manager(hass)
    result = automatic_routes(manager, 3, 180, seed=27)
    assert len(result["persons"]) == 3
    routes = [p["route"] for p in result["persons"]]
    assert routes[0] != routes[1] != routes[2]
    rooms = set(manager.rooms)
    for route in routes:
        assert sum(p["seconds"] for p in route) == pytest.approx(180, abs=0.01)
        assert {p["room"] for p in route} == rooms
        for a, b in pairwise(route):
            assert math.dist([a["x"], a["y"]], [b["x"], b["y"]]) / b["seconds"] < 2500
            if a["room"] != b["room"]:
                assert any({d.a, d.b} == {a["room"], b["room"]} for d in manager.home.tracking.doors)
    assert automatic_routes(manager, 3, 180, seed=27)["persons"] == result["persons"]


async def test_service_starts_without_manual_waypoints(hass, flat, monkeypatch):
    await flat.setup(monkeypatch)
    await hass.services.async_call(
        "radar_occupancy", "start_simulation", {"automatic": True, "count": 3, "duration": 60, "seed": 3}, blocking=True
    )
    manager = get_manager(hass)
    session = manager.simulation
    assert len(session.paths) == 3
    assert len(session.snapshot()["routes"]) == 3
    for _ in range(16):
        await flat.tick(0.5)
    assert len(session.targets) == 3
    assert len({tuple(p["map"]) for p in session.targets}) == 3
    await session.stop()
