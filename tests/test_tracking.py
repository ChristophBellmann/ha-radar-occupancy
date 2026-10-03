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
        self.run_path(self.walk([1500, 1000], [3700, 1000], 6))
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

    def test_seen_through_wall_does_not_change_room(self):
        # Tür ganz unten; das Ziel springt an der Wand rechnerisch in den Gang.
        self.p.configure(ROOMS, [Door("Schlafzimmer", "Gang", "oben", [4000, 100])])
        self.run_path([[3700, 1900]] * 3 + [[4300, 1900]] * 6 + [[3700, 1900]] * 2)
        self.assertEqual(self.p.count("Schlafzimmer"), 1)
        self.assertEqual(self.p.count("Gang"), 0)

    def test_toilet_trip_and_return(self):
        self.run_path([[1000, 3000]] * 4)
        self.run_path(
            self.walk([1000, 3000], [5500, 1000], 10) + self.walk([5500, 1000], [9500, 1500], 8) + [[9500, 1500]] * 3
        )
        self.assertEqual(self.p.count("Schlafzimmer"), 0)
        self.assertEqual(self.p.count("Bad"), 1)
        self.assertEqual(self.p.count("Gang"), 0)

    def test_from_outside_and_back(self):
        self.run_path(self.walk([6000, 100], [6000, 1500], 4) + [[6000, 1500]] * 3)
        self.assertEqual(self.p.count("Gang"), 1)
        self.run_path(self.walk([6000, 1500], [6000, 200], 4))
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

    def test_reasons_use_labels(self):
        self.p.configure(ROOMS, doors(), labels={"Schlafzimmer": "Bedroom", "Gang": "Hall"})
        self.run_path([[1500, 1000]] * 3 + self.walk([1500, 1000], [5500, 1000]) + [[5500, 1000]] * 3)
        assert self.p.reasons["Gang"] == "Bedroom → Hall"

    def test_leaving_through_door_is_no_approach_back(self):
        self.run_path(self.walk([1500, 1000], [5000, 1000], 8) + [[5000, 1000]] * 2)
        self.assertEqual(self.p.count("Gang"), 1)
        self.assertNotIn("Schlafzimmer", self.p.approaching)
