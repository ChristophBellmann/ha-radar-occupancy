"""Map-mode people counting, modelled on situations from a real flat with two people."""

import unittest

from custom_components.radar_occupancy.tracking import OUTSIDE, Door, Presence

# Grundriss (mm): Schlafzimmer links, Gang in der Mitte, Bad rechts.
#   Schlafzimmer 0..4000 x 0..4000, Tür bei (4000, 1000)
#   Gang 4000..8000 x 0..2000, Treppe/Wohnungstür bei (6000, 0)
#   Bad 8000..11000 x 0..3000, Tür bei (8000, 1000)
ROOMS = {
    "Schlafzimmer": {"floor": "oben", "polygon": [[0, 0], [4000, 0], [4000, 4000], [0, 4000]]},
    "Gang": {"floor": "oben", "polygon": [[4000, 0], [8000, 0], [8000, 2000], [4000, 2000]]},
    "Bad": {"floor": "oben", "polygon": [[8000, 0], [11000, 0], [11000, 3000], [8000, 3000]]},
}


def doors(gang_covered=True):
    return [
        Door("Schlafzimmer", "Gang", "oben", [4000, 1000], gang_covered),
        Door("Bad", "Gang", "oben", [8000, 1000], gang_covered),
        Door("Gang", OUTSIDE, "oben", [6000, 0], False),
    ]


class PresenceTests(unittest.TestCase):
    def setUp(self):
        self.p = Presence(ROOMS, doors())
        self.t = 0.0

    def run_path(self, points, dt=0.5, extra=()):
        for point in points:
            self.t += dt
            obs = [("oben", point)] if point else []
            self.p.step(self.t, obs + [("oben", e) for e in extra])

    def idle(self, seconds, extra=()):
        for _ in range(int(seconds / 0.5)):
            self.t += 0.5
            self.p.step(self.t, [("oben", e) for e in extra])

    def walk(self, start, end, steps=8):
        return [
            [start[0] + (end[0] - start[0]) * i / steps, start[1] + (end[1] - start[1]) * i / steps]
            for i in range(steps + 1)
        ]

    def test_still_person_stays_counted_for_hours(self):
        self.run_path([[1500, 2500]] * 4)
        self.assertEqual(self.p.count("Schlafzimmer"), 1)
        self.idle(4 * 3600)
        self.assertEqual(self.p.count("Schlafzimmer"), 1)

    def test_walking_through_door_moves_person(self):
        self.run_path([[1500, 1000]] * 3 + self.walk([1500, 1000], [5500, 1000]) + [[5500, 1000]] * 3)
        self.assertEqual(self.p.count("Schlafzimmer"), 0)
        self.assertEqual(self.p.count("Gang"), 1)

    def test_two_people_one_leaves_other_stays_lit(self):
        # Person 1 sitzt still im Schlafzimmer (wird verloren), Person 2 kommt und geht.
        self.run_path([[1000, 3000]] * 4)
        self.idle(60)
        self.run_path(
            [[6000, 300]] * 3
            + self.walk([6000, 300], [4400, 1000], 4)
            + self.walk([3600, 1000], [2000, 1500], 4)
            + [[2000, 1500]] * 3
        )
        self.assertEqual(self.p.count("Schlafzimmer"), 2)
        self.run_path(self.walk([2000, 1500], [5500, 1000]) + [[5500, 1000]] * 3)
        self.assertEqual(self.p.count("Schlafzimmer"), 1, "Die still sitzende Person bleibt.")

    def test_presence_elsewhere_does_not_empty_room(self):
        self.run_path([[1000, 3000]] * 4)
        self.idle(30)
        self.run_path([[10000, 2000]] * 20)
        self.assertEqual(self.p.count("Schlafzimmer"), 1)
        self.assertEqual(self.p.count("Bad"), 1)

    def test_vanishing_at_unseen_door_moves_person_after_short_wait(self):
        self.p.configure(ROOMS, doors(gang_covered=False))
        self.run_path(self.walk([1500, 1000], [4300, 1000], 6))
        self.idle(1)
        self.assertEqual(self.p.count("Schlafzimmer"), 1)
        self.idle(4)
        self.assertEqual(self.p.count("Schlafzimmer"), 0)
        self.assertEqual(self.p.count("Gang"), 1)

    def test_vanishing_at_covered_door_without_sighting_holds(self):
        self.run_path(self.walk([1500, 1000], [3700, 1000], 6))
        self.idle(20)
        self.assertEqual(self.p.count("Schlafzimmer"), 1)
        self.assertEqual(self.p.count("Gang"), 0)

    def test_covered_door_pairs_vanish_and_appearance(self):
        self.run_path(self.walk([1500, 1000], [3700, 1000], 6))
        self.idle(3)
        self.run_path([[4600, 1000]] * 4)
        self.assertEqual(self.p.count("Schlafzimmer"), 0)
        self.assertEqual(self.p.count("Gang"), 1)

    def test_vanishing_a_metre_before_door_holds_even_if_unseen(self):
        self.p.configure(ROOMS, doors(gang_covered=False))
        self.run_path(self.walk([1000, 1000], [3000, 1000], 6))
        self.idle(30)
        self.assertEqual(self.p.count("Schlafzimmer"), 1)

    def test_standing_still_near_door_holds(self):
        self.run_path([[3700, 1000]] * 6)
        self.idle(30)
        self.assertEqual(self.p.count("Schlafzimmer"), 1)

    def test_near_door_dropout_does_not_add_people(self):
        for _ in range(5):
            self.run_path([[3700, 1000]] * 4)
            self.idle(4)
            self.assertEqual(self.p.count("Schlafzimmer"), 1)
        self.run_path(self.walk([3700, 1000], [5500, 1000], 6))
        self.assertEqual(self.p.count("Schlafzimmer"), 0)
        self.assertEqual(self.p.count("Gang"), 1)

    def test_repeated_trip_through_unseen_hall_conserves_people(self):
        self.p.configure(ROOMS, doors(gang_covered=False))
        self.run_path([[2000, 1000]] * 4)
        for _ in range(5):
            self.run_path(self.walk([2000, 1000], [3700, 1000], 6))
            self.idle(5)
            self.run_path([[8500, 1000]] * 4 + self.walk([8500, 1000], [9500, 1000], 4))
            self.assertEqual(self.p.count("Gang"), 0)
            self.assertEqual(self.p.count("Bad"), 1)
            self.run_path(self.walk([9500, 1000], [8300, 1000], 6))
            self.idle(5)
            self.run_path([[3500, 1000]] * 4 + self.walk([3500, 1000], [2000, 1000], 4))
            self.assertEqual(self.p.count("Gang"), 0)
            self.assertEqual(self.p.count("Schlafzimmer"), 1)

    def test_seen_through_wall_does_not_change_room(self):
        # Tür ganz unten; das Ziel springt an der Wand rechnerisch in den Gang.
        self.p.configure(ROOMS, [Door("Schlafzimmer", "Gang", "oben", [4000, 100])])
        self.run_path([[3700, 1900]] * 3 + [[4300, 1900]] * 6 + [[3700, 1900]] * 2)
        self.assertEqual(self.p.count("Schlafzimmer"), 1)
        self.assertEqual(self.p.count("Gang"), 0)

    def test_toilet_trip_and_return(self):
        self.run_path([[1000, 3000]] * 4)
        self.run_path(
            (self.walk([1000, 3000], [3500, 1000], 5) + self.walk([3500, 1000], [5500, 1000], 5))
            + self.walk([5500, 1000], [9500, 1500], 8)
            + [[9500, 1500]] * 3
        )
        self.assertEqual(self.p.count("Schlafzimmer"), 0)
        self.assertEqual(self.p.count("Bad"), 1)
        self.assertEqual(self.p.count("Gang"), 0)

    def test_from_outside_and_back(self):
        self.run_path(self.walk([6000, 100], [6000, 1500], 4) + [[6000, 1500]] * 3)
        self.assertEqual(self.p.count("Gang"), 1)
        self.run_path(self.walk([6000, 1500], [6000, -200], 4))
        self.idle(3)
        self.assertEqual(self.p.count("Gang"), 0)

    def test_two_visible_people_count_two_but_duplicates_one(self):
        self.run_path([[1000, 1000]] * 8, extra=[[3000, 3000]])
        self.assertEqual(self.p.count("Schlafzimmer"), 2)
        p = Presence(ROOMS, doors())
        for i in range(10):
            p.step(i * 0.5, [("oben", [1000, 1000]), ("oben", [1400, 1300])])
        self.assertEqual(p.count("Schlafzimmer"), 1)

    def test_approach_marks_target_room(self):
        self.run_path(self.walk([1500, 1000], [3500, 1000], 4))
        self.assertIn("Gang", self.p.approaching)

    def test_reset_and_hold_off(self):
        self.run_path([[1000, 3000]] * 4)
        self.p.reset("Schlafzimmer", self.t)
        self.assertEqual(self.p.count("Schlafzimmer"), 0)
        self.run_path([[1000, 3000]] * 4)
        self.assertEqual(self.p.count("Schlafzimmer"), 1)
        self.t += 3
        self.p.step(self.t, [], hold={"Schlafzimmer"})
        self.assertEqual(self.p.count("Schlafzimmer"), 0)

    def test_observation_survives_evaluation_clock_offset(self):
        self.run_path([[1500, 2500]] * 4)
        self.assertTrue(self.p.observed("Schlafzimmer", self.t + 0.001))
        self.p.step(self.t + 0.5, [])
        self.assertFalse(self.p.observed("Schlafzimmer", self.t + 0.501))
        self.assertEqual(self.p.count("Schlafzimmer"), 1)

    def test_reasons_use_labels(self):
        self.p.configure(ROOMS, doors(), labels={"Schlafzimmer": "Bedroom", "Gang": "Hall"})
        self.run_path([[1500, 1000]] * 3 + self.walk([1500, 1000], [5500, 1000]) + [[5500, 1000]] * 3)
        assert self.p.reasons["Gang"] == {"code": "moved", "from": "Schlafzimmer", "to": "Gang"}
        assert self.p.reason("Gang") == {"code": "moved", "from": "Bedroom", "to": "Hall"}

    def test_leaving_through_door_is_no_approach_back(self):
        self.run_path(self.walk([1500, 1000], [5000, 1000], 8) + [[5000, 1000]] * 2)
        self.assertEqual(self.p.count("Gang"), 1)
        self.assertNotIn("Schlafzimmer", self.p.approaching)

    def test_long_near_door_dropout_does_not_add_people(self):
        for _ in range(5):
            self.run_path([[3700, 1000]] * 6)
            self.idle(60)
            self.assertEqual(self.p.count("Schlafzimmer"), 1)

    def test_unpaired_departure_reappears_on_same_side(self):
        for _ in range(4):
            self.run_path([[2000, 1000]] * 4 + self.walk([2000, 1000], [3700, 1000], 6))
            self.idle(4)
            self.run_path([[3700, 1000]] * 4)
            self.assertEqual(self.p.count("Schlafzimmer"), 1)
            self.assertEqual(len(self.p.deaths), 0)

    def test_expired_departure_reappears_after_a_minute(self):
        for _ in range(4):
            self.run_path([[2000, 1000]] * 4 + self.walk([2000, 1000], [3700, 1000], 6))
            self.idle(60)
            self.run_path([[3700, 1000]] * 4)
            self.assertEqual(self.p.count("Schlafzimmer"), 1)

    def test_two_simultaneous_people_at_door_are_still_counted(self):
        self.run_path([[3700, 1000]] * 10, extra=[[2500, 2500]])
        self.assertEqual(self.p.count("Schlafzimmer"), 2)

    def test_near_door_wall_crossing_does_not_release_room(self):
        self.run_path([[3700, 1900]] * 4 + self.walk([3700, 1900], [4600, 1900], 6) + [[4600, 1900]] * 5)
        self.assertEqual(self.p.count("Schlafzimmer"), 1)
        self.assertEqual(self.p.count("Gang"), 0)

    def test_drop_inside_near_unseen_door_does_not_release_room(self):
        self.p.configure(ROOMS, doors(gang_covered=False))
        self.run_path(self.walk([1500, 1000], [3700, 1000], 6))
        self.idle(60)
        self.assertEqual(self.p.count("Schlafzimmer"), 1)
        self.assertEqual(self.p.count("Gang"), 0)

    def test_drop_inside_near_unseen_door_expects_the_other_side(self):
        # Lost at the door: the hall may light up at once, the bedroom stays held.
        self.p.configure(ROOMS, doors(gang_covered=False))
        self.run_path(self.walk([1500, 1000], [3700, 1000], 6))
        self.idle(0.5)
        self.assertEqual(self.p.expected.get("Gang"), self.t)
        self.assertNotIn("Bad", self.p.expected)
        self.idle(60)
        self.assertEqual(self.p.count("Schlafzimmer"), 1)
        self.assertEqual(self.p.count("Gang"), 0)

    def test_sitting_still_inside_expects_nothing(self):
        self.p.configure(ROOMS, doors(gang_covered=False))
        self.run_path([[1500, 1000]] * 6)
        self.idle(10)
        self.assertEqual(self.p.expected, {})

    def test_own_radar_seeing_through_doorway_moves_person_promptly(self):
        # The bedroom radar still reports the person 40 cm into the hall and
        # keeps calling it its own room; the measured crossing decides.
        self.p.configure(ROOMS, doors(gang_covered=False))
        path = self.walk([1500, 1000], [4400, 1000], 6)
        for point in path:
            self.t += 0.5
            self.p.step(self.t, [("oben", point, "Schlafzimmer")])
        self.t += 0.5
        self.p.step(self.t, [("oben", path[-1], "Schlafzimmer")])
        self.assertEqual(self.p.count("Gang"), 1)
        self.assertEqual(self.p.count("Schlafzimmer"), 0)

    def test_own_radar_near_wall_outside_door_keeps_room(self):
        # Beyond the outline but nowhere near the door: a wall, not a passage.
        self.p.configure(ROOMS, doors(gang_covered=False))
        for point in self.walk([3000, 3000], [4500, 3000], 6) + [[4500, 3000]] * 4:
            self.t += 0.5
            self.p.step(self.t, [("oben", point, "Schlafzimmer")])
        self.assertEqual(self.p.count("Schlafzimmer"), 1)
        self.assertEqual(self.p.count("Gang"), 0)

    def test_approach_seen_by_radar_ahead_expects_that_room(self):
        # Walking along the hall to the bathroom door; the bathroom radar sees
        # through its door and reports the person: that room lights fully.
        for point in self.walk([5000, 1000], [7400, 1000], 6):
            self.t += 0.5
            self.p.step(self.t, [("oben", point, None, "Bad")])
        self.assertEqual(self.p.expected.get("Bad"), self.t)
        self.assertEqual(self.p.count("Bad"), 0)

    def test_approach_seen_only_by_own_radar_just_pre_lights(self):
        for point in self.walk([5000, 1000], [7400, 1000], 6):
            self.t += 0.5
            self.p.step(self.t, [("oben", point, None, "Gang")])
        self.assertEqual(self.p.approaching.get("Bad"), self.t)
        self.assertNotIn("Bad", self.p.expected)

    def test_jitter_across_door_outline_does_not_release_room(self):
        self.run_path([[3500, 1000]] * 4 + [[4100, 1000], [3900, 1000]] * 8)
        self.assertEqual(self.p.count("Schlafzimmer"), 1)
        self.assertEqual(self.p.count("Gang"), 0)
