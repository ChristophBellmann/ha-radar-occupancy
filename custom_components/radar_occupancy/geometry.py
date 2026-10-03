"""Geometry in millimetres, free of Home Assistant imports.

Coordinates are robot map millimetres per floor; radar coordinates are the
sensor's own millimetres (X across, Y away from the sensor).
"""

from __future__ import annotations

import math
from collections import deque


def own_samples(samples):
    """Samples that belong to the room plane; sub-area samples are kept as reference only."""
    return [s for s in samples if s.get("area") in (None, "room")]


def solve(matrix, values):
    rows = [list(row) + [value] for row, value in zip(matrix, values)]
    for i in range(3):
        pivot = max(range(i, 3), key=lambda j: abs(rows[j][i]))
        rows[i], rows[pivot] = rows[pivot], rows[i]
        if abs(rows[i][i]) < 1e-8:
            raise ValueError("Die Messpunkte liegen zu dicht oder auf einer Linie.")
        scale = rows[i][i]
        rows[i] = [v / scale for v in rows[i]]
        for j in range(3):
            if i != j:
                factor = rows[j][i]
                rows[j] = [a - factor * b for a, b in zip(rows[j], rows[i])]
    return [row[3] for row in rows]


def fit(samples):
    samples = own_samples(samples)
    if len(samples) < 3:
        raise ValueError("Mindestens drei räumlich verteilte Messpunkte nötig.")
    rows = [[s["radar"][0] / 1000, s["radar"][1] / 1000, 1] for s in samples]
    normal = [[sum(r[i] * r[j] for r in rows) for j in range(3)] for i in range(3)]
    coefficients = [
        solve(normal, [sum(r[i] * s["map"][axis] for r, s in zip(rows, samples)) for i in range(3)])
        for axis in range(2)
    ]
    error = math.sqrt(sum(math.dist(project(coefficients, *s["radar"]), s["map"]) ** 2 for s in samples) / len(samples))
    # Extrapolation einer fast kollinearen Probe verhindern.
    spread = max(
        abs(
            (a["radar"][0] - c["radar"][0]) * (b["radar"][1] - c["radar"][1])
            - (a["radar"][1] - c["radar"][1]) * (b["radar"][0] - c["radar"][0])
        )
        for a in samples
        for b in samples
        for c in samples
    )
    if spread < 250000:
        raise ValueError(
            "Die Messpunkte bilden ein zu kleines oder zu flaches Dreieck. Gehe seitlich aus der Linie der bisherigen Punkte heraus, möglichst 1 m weit. Der neue Punkt wurde nicht gespeichert."
        )
    if error > 400:
        raise ValueError("Messabweichung über 40 cm; Punkte bitte erneut messen.")
    return coefficients, round(error)


def project(coefficients, x, y):
    return [c[0] * x / 1000 + c[1] * y / 1000 + c[2] for c in coefficients]


def inside(point, polygon):
    x, y = point
    result = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            result = not result
    return result


def distance(point, polygon):
    if inside(point, polygon):
        return 0
    distances = []
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        t = max(0, min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (dx * dx + dy * dy))) if dx or dy else 0
        distances.append(math.dist(point, [a[0] + t * dx, a[1] + t * dy]))
    return min(distances)


def valid_polygon(points):
    if len(points) < 3 or len(points) > 30:
        raise ValueError("Raumgrenze braucht 3 bis 30 Eckpunkte.")
    if abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1]))) < 500000:
        raise ValueError("Raumgrenze ist zu klein.")

    # Sich kreuzende Kanten ergeben keine eindeutige Raumgrenze.
    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    edges = list(zip(points, points[1:] + points[:1]))
    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges):
            if j <= i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            if cross(a, b, c) * cross(a, b, d) < 0 and cross(c, d, a) * cross(c, d, b) < 0:
                raise ValueError("Die Raumgrenze darf sich nicht kreuzen.")
    return points


def segment_outlines(pixels, dimensions, room_id):
    """Eigene Kontur aus Raumzellen; keine umschließende Rechteck-Näherung."""
    if pixels is None or dimensions is None:
        return []
    cells = {
        (x, y)
        for x in range(dimensions.width)
        for y in range(dimensions.height)
        if int(pixels[x, y]) in (room_id, room_id + 100)
    }
    if not cells:
        return []
    # Nur Außenkanten behalten, gegen den Uhrzeigersinn um jede Zelle.
    edges = set()
    for x, y in cells:
        for a, b, neighbor in [
            ((x, y), (x + 1, y), (x, y - 1)),
            ((x + 1, y), (x + 1, y + 1), (x + 1, y)),
            ((x + 1, y + 1), (x, y + 1), (x, y + 1)),
            ((x, y + 1), (x, y), (x - 1, y)),
        ]:
            if neighbor not in cells:
                edges.add((a, b))
    outgoing = {}
    for a, b in edges:
        outgoing.setdefault(a, set()).add(b)
    loops = []
    while edges:
        start, current = min(edges)
        previous = start
        loop = [start]
        edges.remove((start, current))
        outgoing[start].remove(current)
        while current != start:
            loop.append(current)
            candidates = outgoing.get(current, set())
            if not candidates:
                return []
            # An diagonal berührenden Zellen die linke Abzweigung nehmen.
            dx, dy = current[0] - previous[0], current[1] - previous[1]
            nxt = max(candidates, key=lambda p: dx * (p[1] - current[1]) - dy * (p[0] - current[0]))
            edges.remove((current, nxt))
            candidates.remove(nxt)
            previous, current = current, nxt
        loops.append(loop)
    area = lambda ps: sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ps, ps[1:] + ps[:1]))
    result = []
    for outer in loops:
        if area(outer) <= 0:
            continue
        # Gerade Teilstücke zusammenfassen; Innenaussparungen (Möbel) bleiben Raum.
        reduced = [
            b
            for a, b, c in zip(outer[-1:] + outer[:-1], outer, outer[1:] + outer[:1])
            if (b[0] - a[0]) * (c[1] - b[1]) != (b[1] - a[1]) * (c[0] - b[0])
        ]
        result.append(
            [
                [dimensions.left + x * dimensions.grid_size, dimensions.top + y * dimensions.grid_size]
                for x, y in reduced
            ]
        )
    return result


def segment_outline(pixels, dimensions, room_id):
    contours = segment_outlines(pixels, dimensions, room_id)
    area = lambda ps: sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ps, ps[1:] + ps[:1]))
    return max(contours, key=area) if contours else []


def doorway_approaches(pixels, dimensions, room_id, room_ids, allowed_neighbors=None):
    """Nur über verbundene Boden-Raumzellen erreichbar, maximal 1,5 m Weg."""
    if pixels is None or dimensions is None:
        return []

    def label(x, y):
        value = int(pixels[x, y])
        return value - 100 if 100 < value < 163 else value

    allowed = room_ids - {room_id} if allowed_neighbors is None else set(allowed_neighbors)
    floors = {
        (x, y): label(x, y)
        for x in range(dimensions.width)
        for y in range(dimensions.height)
        if label(x, y) in room_ids
    }
    neighbors = lambda p: ((p[0] - 1, p[1]), (p[0] + 1, p[1]), (p[0], p[1] - 1), (p[0], p[1] + 1))
    doors = {
        p for p, value in floors.items() if value in allowed and any(floors.get(n) == room_id for n in neighbors(p))
    }
    if not doors:
        return []
    steps = int(1500 / dimensions.grid_size)
    visited = {p: 0 for p in doors}
    pending = deque(doors)
    while pending:
        point = pending.popleft()
        if visited[point] >= steps:
            continue
        for nxt in neighbors(point):
            if nxt not in visited and nxt in floors and floors[nxt] in allowed:
                visited[nxt] = visited[point] + 1
                pending.append(nxt)

    class Mask:
        def __getitem__(self, point):
            return 1 if point in visited else 0

    return segment_outlines(Mask(), dimensions, 1)


def rigid(location, heading, mirrored=False):
    """Maßstabstreue Umrechnung aus Montageort und Blickrichtung.

    `heading` ist die Blickrichtung (Radar-Y) in Grad im Kartensystem,
    gegen den Uhrzeigersinn ab +X. Radar-X zeigt ungespiegelt nach rechts.
    """
    h = math.radians(heading)
    m = -1 if mirrored else 1
    return [
        [1000 * m * math.sin(h), 1000 * math.cos(h), float(location[0])],
        [-1000 * m * math.cos(h), 1000 * math.sin(h), float(location[1])],
    ]


def orientation(coefficients):
    """Blickrichtung und Spiegelung, die eine affine Umrechnung nahelegt."""
    (a, b, _), (c, d, _) = coefficients
    return round(math.degrees(math.atan2(d, b)) % 360, 1), a * d - b * c < 0


def scales(coefficients):
    """Größte und kleinste Streckung (Karte je Radar-Millimeter)."""
    (a, b, _), (c, d, _) = coefficients
    a, b, c, d = a / 1000, b / 1000, c / 1000, d / 1000
    p, q = (a * a + c * c + b * b + d * d) / 2, abs(a * d - b * c)
    root = math.sqrt(max(0, p * p - q * q))
    return math.sqrt(p + root), math.sqrt(max(0, p - root))


def plausible(coefficients):
    """Radar und Karte messen beide Millimeter; starke Verzerrung ist ein Messfehler."""
    big, small = scales(coefficients)
    return small >= 0.5 and big <= 2.2


def rms_error(coefficients, samples):
    samples = own_samples(samples)
    if not samples:
        return None
    return round(
        math.sqrt(sum(math.dist(project(coefficients, *s["radar"]), s["map"]) ** 2 for s in samples) / len(samples))
    )


def doorways(pixels, dimensions, room_ids):
    """Durchgänge zwischen Räumen der Roboterkarte: zusammenhängende Stellen,
    an denen Bodenzellen zweier Räume aneinanderstoßen. Ergebnis je
    Durchgang: (raum_a, raum_b, Mittelpunkt in mm, Breite in mm)."""
    if pixels is None or dimensions is None:
        return []

    def label(x, y):
        value = int(pixels[x, y])
        return value - 100 if 100 < value < 163 else value

    floors = {
        (x, y): label(x, y)
        for x in range(dimensions.width)
        for y in range(dimensions.height)
        if label(x, y) in room_ids
    }
    contacts = {}
    for (x, y), a in floors.items():
        for n in ((x + 1, y), (x, y + 1)):
            b = floors.get(n)
            if b is not None and b != a:
                key = (min(a, b), max(a, b))
                contacts.setdefault(key, set()).update({(x, y), n})
    result = []
    for (a, b), cells in contacts.items():
        pending = set(cells)
        while pending:
            seed = pending.pop()
            group, queue = [seed], deque([seed])
            while queue:
                cx, cy = queue.popleft()
                for n in ((cx + dx, cy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                    if n in pending:
                        pending.remove(n)
                        group.append(n)
                        queue.append(n)
            xs = [dimensions.left + (x + 0.5) * dimensions.grid_size for x, _ in group]
            ys = [dimensions.top + (y + 0.5) * dimensions.grid_size for _, y in group]
            width = max(max(xs) - min(xs), max(ys) - min(ys)) + dimensions.grid_size
            result.append((a, b, [sum(xs) / len(xs), sum(ys) / len(ys)], round(width)))
    return result
