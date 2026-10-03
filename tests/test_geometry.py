"""Geometry: calibration fit, map outlines, doorways, orientation."""

import unittest
from types import SimpleNamespace

from custom_components.radar_occupancy.geometry import (
    distance,
    doorway_approaches,
    doorways,
    fit,
    inside,
    orientation,
    plausible,
    project,
    rigid,
    segment_outline,
    valid_polygon,
)


class GeometryTests(unittest.TestCase):
    def test_affine_ceiling_rotation_and_reflection(self):
        samples = [
            {"radar": [0, 0], "map": [1000, 2000]},
            {"radar": [2000, 0], "map": [1000, 0]},
            {"radar": [0, 2000], "map": [-1000, 2000]},
            {"radar": [2000, 2000], "map": [-1000, 0]},
        ]
        coefficients, error = fit(samples)
        self.assertEqual(error, 0)
        self.assertEqual(project(coefficients, 1000, 1000), [0, 1000])

    def test_collinear_rejected(self):
        with self.assertRaises(ValueError):
            fit([{"radar": [v, v], "map": [v, v]} for v in [0, 1000, 2000]])

    def test_noisy_fourth_sample_rejected(self):
        with self.assertRaises(ValueError):
            fit(
                [
                    {"radar": [0, 0], "map": [0, 0]},
                    {"radar": [2000, 0], "map": [2000, 0]},
                    {"radar": [0, 2000], "map": [0, 2000]},
                    {"radar": [2000, 2000], "map": [6000, 6000]},
                ]
            )

    def test_segment_outline_keeps_concave_room_and_excludes_other_rooms(self):
        class Pixels:
            def __getitem__(self, point):
                return 2 if point in {(0, 0), (1, 0), (0, 1)} else 3

        dimensions = SimpleNamespace(width=2, height=2, left=100, top=200, grid_size=1000)
        poly = segment_outline(Pixels(), dimensions, 2)
        self.assertEqual(len(poly), 6)
        self.assertTrue(inside([600, 1700], poly))
        self.assertFalse(inside([1600, 1700], poly))
        self.assertEqual(segment_outline(Pixels(), dimensions, 4), [])

    def test_segment_outline_ignores_furniture_hole_and_tiny_island(self):
        class Pixels:
            def __getitem__(self, point):
                x, y = point
                return 2 if (x < 3 and y < 3 and point != (1, 1)) or point == (4, 4) else 0

        poly = segment_outline(Pixels(), SimpleNamespace(width=5, height=5, left=0, top=0, grid_size=1000), 2)
        self.assertEqual(len(poly), 4)
        self.assertTrue(inside([1500, 1500], poly))
        self.assertFalse(inside([4500, 4500], poly))

    def test_doorway_approach_follows_connected_floor_not_walls(self):
        class Pixels:
            def __getitem__(self, point):
                x, y = point
                if x < 2:
                    return 2
                if x == 2 and y != 2:
                    return 255
                return 1

        d = SimpleNamespace(width=8, height=5, left=0, top=0, grid_size=500)
        polygons = doorway_approaches(Pixels(), d, 2, {1, 2})
        self.assertTrue(any(inside([1750, 1250], p) for p in polygons))
        self.assertFalse(any(inside([1250, 250], p) for p in polygons))
        self.assertFalse(any(inside([3750, 250], p) for p in polygons))

        class Walls:
            def __getitem__(self, point):
                return 2 if point[0] < 2 else 255

        self.assertEqual(doorway_approaches(Walls(), d, 2, {1, 2}), [])

    def test_doorway_proposal_does_not_cross_from_corridor_into_kitchen(self):
        class Pixels:
            def __getitem__(self, point):
                return [5, 1, 3][point[0]]

        dimensions = SimpleNamespace(width=3, height=2, left=0, top=0, grid_size=500)
        polygons = doorway_approaches(Pixels(), dimensions, 3, {1, 3, 5}, {1})
        self.assertTrue(any(inside([750, 250], p) for p in polygons))
        self.assertFalse(any(inside([250, 250], p) for p in polygons))
        self.assertEqual(doorway_approaches(Pixels(), dimensions, 1, {1, 3, 5}, set()), [])

    def test_concave_room(self):
        poly = [[0, 0], [4000, 0], [4000, 1000], [1000, 1000], [1000, 4000], [0, 4000]]
        self.assertTrue(inside([500, 3000], poly))
        self.assertFalse(inside([3000, 3000], poly))
        self.assertEqual(distance([2000, 2000], poly), 1000)

    def test_rigid_orientation_roundtrip_and_mirror(self):
        t = rigid([1000, 2000], 90)
        self.assertEqual([round(v) for v in project(t, 0, 1000)], [1000, 3000])
        self.assertEqual([round(v) for v in project(t, 1000, 0)], [2000, 2000])
        self.assertEqual(orientation(t), (90.0, False))
        m = rigid([0, 0], 0, True)
        self.assertEqual([round(v) for v in project(m, 1000, 0)], [0, 1000])
        self.assertEqual(orientation(m), (0.0, True))

    def test_distorted_calibration_is_not_plausible(self):
        self.assertTrue(plausible(rigid([0, 0], 33)))
        self.assertFalse(plausible([[-5749, -2993, 0], [4154, 744, 0]]))
        self.assertFalse(plausible([[-43, 48, 0], [161, -1418, 0]]))

    def test_crossed_boundary_rejected(self):
        with self.assertRaises(ValueError):
            valid_polygon([[0, 0], [5000, 4000], [0, 4000], [4000, 0]])

    def test_sub_area_samples_are_kept_but_not_fitted(self):
        samples = [
            {"radar": [0, 0], "map": [0, 0]},
            {"radar": [2000, 0], "map": [2000, 0]},
            {"radar": [0, 2000], "map": [0, 2000]},
            {"radar": [900, 900], "map": [9000, 9000], "area": "balcony"},
        ]
        _, error = fit(samples)
        self.assertEqual(error, 0)

    def test_doorways_between_two_rooms(self):
        class Pixels:
            def __getitem__(self, point):
                return 1 if point[0] < 2 else 2

        d = SimpleNamespace(width=4, height=2, left=0, top=0, grid_size=500)
        result = doorways(Pixels(), d, {1, 2})
        self.assertEqual(len(result), 1)
        a, b, point, _width = result[0]
        self.assertEqual({a, b}, {1, 2})
        self.assertEqual(point, [1000.0, 500.0])
