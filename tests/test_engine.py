"""Engine tests, modelled on observed situations from a real installation."""

from custom_components.radar_occupancy.engine import (
    HANDED_OVER,
    HELD,
    IN_AREA,
    LEFT_THROUGH_DOOR,
    LIVE,
    PRESENT,
    SAFETY_TIMEOUT,
    UNAVAILABLE,
    Area,
    Room,
    RoomConfig,
    handover,
)


def enter(room: Room, now: float, distance: float, x: float = 0, y: float | None = None) -> None:
    room.set_presence(True, now)
    room.set_distance(distance)
    room.set_position(x, distance if y is None else y)
    room.update(now)


def lose(room: Room, now: float) -> None:
    room.set_presence(False, now)
    room.set_distance(None)
    room.update(now)


def test_still_person_is_held_until_safety_timeout():
    # Desk at 0.2–1.3 m, door at 5.4 m: losing someone at the desk keeps the room.
    room = Room(RoomConfig(door_from=4000, safety_timeout=1800))
    enter(room, 0, 900)
    lose(room, 10)
    assert room.occupied and room.reason == HELD
    room.update(10 + 1799)
    assert room.occupied
    room.update(10 + 1800)
    assert not room.occupied and room.reason == SAFETY_TIMEOUT


def test_disappearing_at_the_door_releases_immediately():
    room = Room(RoomConfig(door_from=4000))
    enter(room, 0, 2000)
    room.set_distance(5600)
    lose(room, 5)
    assert not room.occupied and room.reason == LEFT_THROUGH_DOOR


def test_door_range_upper_bound():
    room = Room(RoomConfig(door_from=3000, door_to=4000, safety_timeout=0))
    enter(room, 0, 5000)  # beyond the door, e.g. seen through a window
    lose(room, 1)
    assert room.occupied and room.reason == HELD
    room.update(10**6)  # no safety timeout configured
    assert room.occupied


def test_default_range_releases_on_every_loss():
    room = Room()
    enter(room, 0, 1000)
    lose(room, 1)
    assert not room.occupied


def test_empty_room_stays_empty_without_presence():
    room = Room(RoomConfig(door_from=4000))
    room.set_presence(False, 0)
    room.update(0)
    assert not room.occupied


def test_unavailable_sensor_keeps_last_decision():
    room = Room(RoomConfig(door_from=4000))
    enter(room, 0, 1000)
    room.set_presence(None, 5)
    room.update(5)
    assert room.occupied and room.reason == UNAVAILABLE
    room.set_presence(True, 6)
    room.update(6)
    assert room.reason == PRESENT


def test_sub_area_disappearance_is_not_leaving():
    # Balcony stairs end at 3.4 m, the door at 3.1 m; they differ in X.
    balcony = Area(x_min=-3000, x_max=-600, y_min=2000, y_max=8000)
    room = Room(RoomConfig(door_from=2750), areas=[balcony])
    enter(room, 0, 3400, x=-1100, y=3200)
    lose(room, 1)
    assert room.occupied and room.reason == IN_AREA
    assert room.area_occupied(balcony)
    # Back in the room, then out through the door.
    enter(room, 20, 1200, x=400, y=1100)
    assert not room.area_occupied(balcony)
    room.set_distance(3100)
    room.set_position(700, 3000)
    lose(room, 30)
    assert not room.occupied and room.reason == LEFT_THROUGH_DOOR


def test_hold_off_follows_presence():
    room = Room(RoomConfig(door_from=4000))
    room.hold = False
    enter(room, 0, 1000)
    lose(room, 1)
    assert not room.occupied and room.reason == LIVE


def test_release_refused_while_present():
    room = Room(RoomConfig(door_from=4000))
    enter(room, 0, 1000)
    assert not room.release()
    lose(room, 1)
    assert room.release()
    assert not room.occupied


def test_learn_door_from_last_exit():
    room = Room()
    enter(room, 0, 3120)
    lose(room, 1)
    assert room.learn_door() == 2620


def test_zero_position_is_ignored():
    room = Room()
    enter(room, 0, 1500, x=300, y=1400)
    room.set_position(0, 0)
    assert (room.last_x, room.last_y) == (300, 1400)


def _pair(**office):
    lab = Room(RoomConfig(door_from=2750, handover=True, handover_anywhere=True))
    desk = Room(RoomConfig(door_from=4000, handover=True, **office))
    return lab, desk


def test_handover_after_delay():
    lab, office = _pair()
    enter(lab, 0, 1300)
    lose(lab, 10)
    enter(office, 12, 1000)
    assert handover([lab, office], 25) == []  # only 15 s since the loss
    assert handover([lab, office], 30) == [lab]
    assert not lab.occupied and lab.reason == HANDED_OVER
    assert office.occupied


def test_handover_ignores_echo_close_to_other_sensor():
    # An open door leaf shows up as a fixed target at ~0.36 m.
    lab, office = _pair(takeover_min=500)
    enter(lab, 0, 1300)
    lose(lab, 10)
    enter(office, 12, 360)
    assert handover([lab, office], 40) == []
    office.set_distance(1000)
    assert handover([lab, office], 41) == [lab]


def test_handover_requires_door_unless_anywhere():
    office, lab = _pair()  # office here: handover only at the door
    office.config.handover_anywhere = False
    enter(office, 0, 900)
    lose(office, 1)
    enter(lab, 2, 1500)
    assert handover([office, lab], 60) == []


def test_handover_disabled_room_is_ignored():
    lab, office = _pair()
    office.config.handover = False
    enter(lab, 0, 1300)
    lose(lab, 1)
    enter(office, 2, 1000)
    assert handover([lab, office], 60) == []
