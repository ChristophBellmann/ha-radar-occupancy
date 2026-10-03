"""Independent automatic walks through known doorways and room polygons."""

from __future__ import annotations

import heapq
import math
import random
from copy import deepcopy
from itertools import pairwise
from types import SimpleNamespace

from homeassistant.exceptions import HomeAssistantError

from .geometry import distance, inside


def nearest(point, polygon):
    candidates = []
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        t = max(0, min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (dx * dx + dy * dy))) if dx or dy else 0
        candidates.append([a[0] + t * dx, a[1] + t * dy])
    return min(candidates, key=lambda p: math.dist(p, point))


def segment_inside(a, b, polygon):
    """Test each interval cut by polygon edges, including narrow concavities."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    cuts = [0.0, 1.0]
    for c, d in zip(polygon, polygon[1:] + polygon[:1]):
        ex, ey = d[0] - c[0], d[1] - c[1]
        det = dx * ey - dy * ex
        if abs(det) < 1e-8:
            continue
        t = ((c[0] - a[0]) * ey - (c[1] - a[1]) * ex) / det
        u = ((c[0] - a[0]) * dy - (c[1] - a[1]) * dx) / det
        if 0 < t < 1 and 0 <= u <= 1:
            cuts.append(t)
    cuts.sort()
    return all(
        distance([a[0] + dx * (lo + hi) / 2, a[1] + dy * (lo + hi) / 2], polygon) <= 0.1 for lo, hi in pairwise(cuts)
    )


class RoomPaths:
    def __init__(self, polygon):
        self.polygon = polygon
        xs, ys = zip(*polygon)
        self.anchors = [
            [min(xs) + (max(xs) - min(xs)) * x / 12, min(ys) + (max(ys) - min(ys)) * y / 12]
            for x in range(1, 12)
            for y in range(1, 12)
        ]
        self.anchors = [p for p in self.anchors if inside(p, polygon)]
        if not self.anchors:
            raise HomeAssistantError("Room outline has no usable interior for an automatic walk.")

        # Prefer positions away from walls; a narrow room still gets an anchor.
        def clearance(p):
            return math.dist(p, nearest(p, polygon))

        self.anchors.sort(key=clearance, reverse=True)
        self.anchors = self.anchors[: max(3, len(self.anchors) // 3)]
        self.vertices = polygon
        self.edges = [[] for _ in polygon]
        for i, a in enumerate(polygon):
            for j in range(i + 1, len(polygon)):
                if segment_inside(a, polygon[j], polygon):
                    weight = math.dist(a, polygon[j])
                    self.edges[i].append((j, weight))
                    self.edges[j].append((i, weight))

    def path(self, start, end):
        if segment_inside(start, end, self.polygon):
            return [start, end]
        nodes = [*self.vertices, start, end]
        edges = [list(e) for e in self.edges] + [[], []]
        for index in (len(nodes) - 2, len(nodes) - 1):
            for j, p in enumerate(nodes[:index]):
                if segment_inside(nodes[index], p, self.polygon):
                    weight = math.dist(nodes[index], p)
                    edges[index].append((j, weight))
                    edges[j].append((index, weight))
        first, last = len(nodes) - 2, len(nodes) - 1
        queue = [(0, first)]
        costs = {first: 0}
        previous = {}
        while queue:
            cost, node = heapq.heappop(queue)
            if node == last:
                result = [nodes[node]]
                while node != first:
                    node = previous[node]
                    result.append(nodes[node])
                return result[::-1]
            if cost != costs[node]:
                continue
            for other, weight in edges[node]:
                candidate = cost + weight
                if candidate < costs.get(other, math.inf):
                    costs[other] = candidate
                    previous[other] = node
                    heapq.heappush(queue, (candidate, other))
        raise HomeAssistantError("No walkable path inside this room outline. Check the outline.")


def planning_snapshot(manager, start_room=None):
    """Capture configuration on the event loop before geometry runs in a worker."""
    if not manager.home:
        raise HomeAssistantError("Automatic walks require a loaded home map.")
    try:
        preferred = manager.resolve(start_room) if start_room else None
    except KeyError as err:
        raise HomeAssistantError("Unknown starting room for the automatic walk.") from err
    tracking = SimpleNamespace(rooms=deepcopy(manager.home.tracking.rooms), doors=deepcopy(manager.home.tracking.doors))
    return SimpleNamespace(
        home=SimpleNamespace(tracking=tracking), rooms=dict.fromkeys(manager.rooms), resolve=lambda value: value
    ), preferred


def automatic_routes(manager, count=2, duration=180, *, seed=None, start_room=None):
    if not manager.home or not manager.home.tracking.rooms:
        raise HomeAssistantError("Automatic walks require loaded, calibrated room maps.")
    source = manager.home.tracking.rooms
    rooms = {rid: info for rid, info in source.items() if info.get("polygon") and rid in manager.rooms}
    if not rooms:
        raise HomeAssistantError("No calibrated rooms for an automatic walk.")
    paths = {rid: RoomPaths(info["polygon"]) for rid, info in rooms.items()}
    graph = {rid: [] for rid in rooms}
    warnings = []
    for door in manager.home.tracking.doors:
        if door.a not in rooms or door.b not in rooms or not door.point:
            continue
        if rooms[door.a]["floor"] != rooms[door.b]["floor"]:
            continue
        endpoints = {rid: nearest(door.point, rooms[rid]["polygon"]) for rid in (door.a, door.b)}
        if any(math.dist(p, door.point) > 1000 for p in endpoints.values()):
            warnings.append("Door is too far from a room outline; correct its position.")
            continue
        graph[door.a].append((door.b, door.point, endpoints))
        graph[door.b].append((door.a, door.point, endpoints))
    components = []
    remaining = set(rooms)
    while remaining:
        todo = [min(remaining)]
        component = []
        while todo:
            rid = todo.pop()
            if rid not in remaining:
                continue
            remaining.remove(rid)
            component.append(rid)
            todo.extend(v[0] for v in graph[rid])
        components.append(sorted(component))
    components.sort(key=lambda c: (str(rooms[c[0]]["floor"]), c[0]))
    preferred = manager.resolve(start_room) if start_room else None
    if preferred in rooms:
        components.sort(key=lambda c: preferred not in c)
    base = random.SystemRandom().randrange(2**31) if seed is None else seed
    persons = []
    for index in range(count):
        rng = random.Random(base + index * 104729)
        component = components[index % len(components)]
        current = (
            preferred
            if index == 0 and preferred in component
            else component[(index // len(components) + rng.randrange(len(component))) % len(component)]
        )
        position = list(rng.choice(paths[current].anchors))
        total = 0.0
        route = []
        visits = {current: 1}
        previous = None

        def append(room, point, seconds, route=route):
            nonlocal total, position
            requested = seconds
            seconds = min(seconds, duration - total)
            if seconds <= 0:
                return False
            # Truncate a final travel segment without teleporting to its endpoint.
            if seconds + 1e-8 < requested:
                fraction = seconds / requested
                point = [position[i] + (point[i] - position[i]) * fraction for i in range(2)]
            route.append({"room": room, "x": round(point[0], 2), "y": round(point[1], 2), "seconds": round(seconds, 3)})
            total += seconds
            position = list(point)
            return total < duration - 0.001

        append(current, position, rng.uniform(3, 8) + index * 0.7)
        while total < duration - 0.001 and len(route) < 300:
            neighbors = graph[current]
            if neighbors:
                choices = sorted(neighbors, key=lambda e: (visits.get(e[0], 0), e[0] == previous, rng.random()))
                destination, door, endpoints = choices[0]
                segments = [(current, p) for p in paths[current].path(position, endpoints[current])[1:]]
                segments.append((current, list(door)))
                segments.append((destination, endpoints[destination]))
                goal = list(rng.choice(paths[destination].anchors))
                segments.extend((destination, p) for p in paths[destination].path(endpoints[destination], goal)[1:])
            else:
                destination = current
                goal = list(rng.choice(paths[current].anchors))
                segments = [(current, p) for p in paths[current].path(position, goal)[1:]]
                if len(components) > 1:
                    warnings.append("Some rooms have no connected doorway; people stay within their map component.")
            speed = rng.uniform(650, 1050)
            for room, point in segments:
                if math.dist(position, point) < 1:
                    continue
                if not append(room, point, max(0.5, math.dist(position, point) / speed)):
                    break
            if total >= duration - 0.001:
                break
            previous, current = current, destination
            visits[current] = visits.get(current, 0) + 1
            append(current, position, rng.uniform(4, 17))
        persons.append({"id": f"Person {index + 1}", "route": route})
    return {"persons": persons, "seed": base, "warnings": sorted(set(warnings))}
