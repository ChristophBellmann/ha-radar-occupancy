"""Occupancy logic, free of Home Assistant imports so it can be tested directly.

A room is a latch: radar presence sets it, and only evidence clears it.

Radar sensors routinely lose a person who sits or lies still. Clearing the
room whenever presence drops therefore switches the light off on people. Here
a room is released only when one of these is true:

* the target disappeared inside the configured door range (distance from the
  sensor), i.e. it walked out;
* another room took the person over (handover, single-person households);
* nobody was seen for the safety timeout;
* the user released it by hand, or switched "hold" off.

Disappearing inside a sub-area (for example a balcony the room sensor also
covers) never counts as leaving, even within the door range.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Reasons exposed as attribute; stable values, translated in the frontend.
PRESENT = "present"
HELD = "held"
IN_AREA = "in_area"
LEFT_THROUGH_DOOR = "left_through_door"
SAFETY_TIMEOUT = "safety_timeout"
HANDED_OVER = "handed_over"
RELEASED = "released"
LIVE = "live"
UNAVAILABLE = "unavailable"
EMPTY = "empty"


@dataclass
class RoomConfig:
    """Tunables of one room. Distances in mm, times in seconds."""

    door_from: float = 0
    # door_to <= door_from means "no upper bound".
    door_to: float = 0
    # 0 disables the safety timeout.
    safety_timeout: float = 30 * 60
    handover: bool = False
    handover_anywhere: bool = False
    # Another room's target must be at least this far from its sensor to take
    # a person over. Filters fixed echoes close to a sensor, e.g. a door leaf.
    takeover_min: float = 0


@dataclass
class Area:
    """Rectangle in the radar's own coordinates (mm)."""

    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def contains(self, x: float | None, y: float | None) -> bool:
        if x is None or y is None:
            return False
        return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max


@dataclass
class Room:
    config: RoomConfig = field(default_factory=RoomConfig)
    areas: list[Area] = field(default_factory=list)

    # Live inputs. presence None = sensor unavailable.
    presence: bool | None = None
    presence_changed: float = 0.0
    distance: float | None = None

    # Last position seen while a target was present.
    last_distance: float | None = None
    last_x: float | None = None
    last_y: float | None = None

    hold: bool = True
    occupied: bool = False
    reason: str = EMPTY

    def set_presence(self, value: bool | None, now: float) -> None:
        if value != self.presence:
            self.presence = value
            self.presence_changed = now

    def set_distance(self, value: float | None) -> None:
        """Current distance of the first target; None or 0 means no target."""
        if value is not None and value <= 0:
            value = None
        self.distance = value
        if value is not None:
            self.last_distance = value

    def set_position(self, x: float | None, y: float | None) -> None:
        # Many firmwares report 0/0 for an empty target slot.
        if x is None or y is None or (x == 0 and y == 0):
            return
        self.last_x, self.last_y = x, y

    def in_door_range(self) -> bool:
        low = self.config.door_from
        high = self.config.door_to if self.config.door_to > low else float("inf")
        if self.last_distance is None:
            # Without a distance we cannot tell; only the default range
            # (everything) counts as leaving.
            return low <= 0 and high == float("inf")
        return low <= self.last_distance <= high

    def in_area(self) -> bool:
        return any(area.contains(self.last_x, self.last_y) for area in self.areas)

    def lost_for(self, now: float) -> float:
        return now - self.presence_changed

    def update(self, now: float) -> bool:
        """Re-evaluate. Returns True if `occupied` or `reason` changed."""
        before = (self.occupied, self.reason)
        if self.presence is None:
            # Keep the last decision while the sensor is away.
            if self.occupied:
                self.reason = UNAVAILABLE
        elif self.presence:
            self.occupied, self.reason = True, PRESENT
        elif self.occupied:
            in_area = self.in_area()
            timeout = self.config.safety_timeout
            if not self.hold:
                self.occupied, self.reason = False, LIVE
            elif not in_area and self.in_door_range():
                self.occupied, self.reason = False, LEFT_THROUGH_DOOR
            elif timeout and self.lost_for(now) >= timeout:
                self.occupied, self.reason = False, SAFETY_TIMEOUT
            else:
                self.reason = IN_AREA if in_area else HELD
        return before != (self.occupied, self.reason)

    def release(self, reason: str = RELEASED) -> bool:
        """Clear a held room. Refused while a target is present."""
        if self.presence:
            return False
        changed = self.occupied
        self.occupied, self.reason = False, reason
        return changed

    def learn_door(self, margin: float = 500) -> float | None:
        """Door range from the last exit: everything beyond (last - margin)."""
        if self.last_distance is None:
            return None
        return max(0.0, round(self.last_distance - margin, -1))

    def area_occupied(self, area: Area) -> bool:
        return self.occupied and area.contains(self.last_x, self.last_y)


HANDOVER_DELAY = 20.0


def handover(rooms: list[Room], now: float, delay: float = HANDOVER_DELAY) -> list[Room]:
    """Release rooms whose person has evidently moved to another room.

    Assumes a single-person household: if a room lost its target near the
    door (or anywhere, if configured) at least `delay` seconds ago and another
    room now sees someone, the person went there. Returns the released rooms.
    """
    released = []
    for room in rooms:
        cfg = room.config
        if not (cfg.handover and room.occupied and room.presence is False):
            continue
        if room.lost_for(now) < delay:
            continue
        if not (cfg.handover_anywhere or room.in_door_range()):
            continue
        for other in rooms:
            if other is room or not other.config.handover or not other.presence:
                continue
            minimum = other.config.takeover_min
            if minimum and (other.distance is None or other.distance < minimum):
                continue
            room.release(HANDED_OVER)
            released.append(room)
            break
    return released
