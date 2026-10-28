"""People per room from the radar targets of all sensors (map mode).

Free of Home Assistant imports. Coordinates are map millimetres per floor;
rooms are identified by key (the config entry id), `labels` gives their
display names.

Principle: a room only becomes empty when someone evidently walked out
through a door. A target that vanishes in the middle of a room is someone
sitting still. Several people are counted through door passages; someone
being seen in another room says nothing about this room.

Reasons are stable codes (see REASONS) plus the rooms involved, so the
frontend can translate them and automations can rely on them.
"""

from __future__ import annotations

import math
from itertools import count as counter
from itertools import pairwise

from .geometry import distance, inside

OUTSIDE = "outside"  # everything without a radar: stairs, front door, unsensed map rooms
MERGE = 800  # mm: targets of different sensors that are the same person
GATE = 1500  # mm: largest jump of a track between two measurements
TRACK_TTL = 2.0  # s without a measurement: the track ends
EDGE = 400  # mm: tolerance at room outlines
DOOR_CROSS = 450  # mm: measured boundary crossing must pass the actual doorway
DOOR_PASS = 1300  # mm: a track changes rooms only this close to a door
DOOR_NEAR = 1100  # mm: appearing "at the door"
ARRIVE_NEAR = 1500  # mm: first report of somebody coming in (radars see doorways late)
DOOR_LEAVE = 800  # mm: vanishing "at the door" (stricter: it switches lights off)
DOOR_APPROACH = 300  # mm: a target must have come this much closer to the door
STANDSTILL = 150  # mm: a target that moved less has stopped
PRE_STOP = 6.0  # s: the walk to the door before stopping there (slowing down to open it)
ECHO_HOLD = 6.0  # s: a radar holds the last coordinates of somebody gone (5 s live window)
ECHO_MOVE = 700  # mm: an echo that walks this far is a person after all
BEYOND_FAR_DOOR = 100  # mm: outside the room, behind a door to another floor map
FAR_DOOR_REACH = 2500  # mm: how far a radar sees through such a door
APPROACH_ZONE = 1500  # mm: pre-light when a target walks this close towards a door
APPROACH_REARM = 1000  # mm: beyond the zone by this much, the door may pre-light again
APPROACH_HEADING = 35  # degrees: walking at the door, not along the wall past it
SUB_SHADOW = 3000  # mm: somebody this close to a door of the parent room, seen next door, explains sub-area targets
SPOT_RADIUS = 1000  # mm: approaches starting here again (a desk chair) are no walk to the door
SPOT_MEMORY = 14400.0  # s: how long such a starting point is remembered without a passage (a passage clears it)
PAIR_WINDOW = 8.0  # s: vanishing at a door and appearing on the other side
REACQUIRE_WINDOW = 15.0  # s: a nearby reappearance after radar dropout is not a new entrant
UNSEEN_PASS = 2.0  # s: door into an area no sensor sees
CONFIRM_ONE = 1.0  # s: first target in an empty room
CONFIRM_MORE = 3.0  # s: each further target visible at the same time
SEPARATION = 1000  # mm: two simultaneous targets must be this far apart
ARRIVAL_STEP = 150  # mm: an arrival has moved this far away from the door when confirmed
VANISH_WINDOW = 60.0  # s: a person who vanished this recently is the one who moved on

# Reason codes
SEEN = "seen_in_room"  # someone visible in the room
MOVED = "moved"  # walked from one room to another (from, to)
CAME_IN = "came_in"  # came from outside the home
APPEARED_AT_DOOR = "appeared_at_door"  # at the door to `from`, nobody seen leaving there
WENT_OUT = "went_out"  # left the home
RELEASED = "released"  # released by hand
HOLD_OFF = "hold_off"  # no target and hold switched off
HOUSEHOLD = "household_limit"  # more people counted than live in the home: a held place was stale
REASONS = (SEEN, MOVED, CAME_IN, APPEARED_AT_DOOR, WENT_OUT, RELEASED, HOLD_OFF, HOUSEHOLD)


def _segment_distance(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    t = max(0, min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length)) if length else 0
    return math.dist(point, [a[0] + t * dx, a[1] + t * dy])


class Door:
    def __init__(self, a, b, floor, point, covered=True, far=None):
        self.a, self.b, self.floor, self.point, self.covered = a, b, floor, point, covered
        # The same doorway on another floor's map (floor, point): a staircase
        # or a hall that one robot map shows and the other one continues.
        self.far = far

    def at(self, floor):
        """The door point on this floor's map, or None."""
        if floor == self.floor:
            return self.point
        if self.far and floor == self.far[0]:
            return self.far[1]
        return None

    def covered_into(self, room):
        """Does a sensor see who walks through this door into `room`?"""
        return self.covered.get(room, True) if isinstance(self.covered, dict) else self.covered

    def other(self, room):
        return self.b if room == self.a else self.a if room == self.b else None

    def distance(self, floor, point):
        here = self.at(floor)
        return None if here is None else math.dist(point, here)

    def __repr__(self):
        return f"Door({self.a}<->{self.b})"


class Track:
    ids = counter(1)

    def __init__(self, floor, point, room, now):
        self.id = next(Track.ids)
        self.floor, self.point, self.room = floor, point, room
        self.born = self.seen = now
        self.history = [(now, point)]
        self.counted = False
        self.pending = None
        self.pending_since = None
        self.birth_point = point
        self.room_since = now
        self.sensors = frozenset()  # rooms whose radar reported the last position
        self.approached = {}  # door -> "active" while walking towards it, "used" after; walking away re-arms
        self.echo = None  # (time, point): somebody just left the room while this track stood here
        self.shadow_of = None  # id of the track of another floor map that sees the same person

    def age(self, now):
        return now - self.born


class Presence:
    def __init__(self, rooms=None, doors=None, counts=None, labels=None):
        self.rooms = rooms or {}  # key -> {'floor':..., 'polygon':[...]}
        self.labels = dict(labels or {})  # key -> display name
        self.doors = doors or []
        self.counts = dict(counts or {})
        self.tracks = []
        self.deaths = []  # open departures at doors whose other side a sensor sees
        self.lost = []  # counted tracks that vanished without evidence of leaving
        self.events = []
        self.reasons = {}  # room -> {"code": ..., "from": room key, "to": room key}
        self.approaching = {}  # room -> time of the last approach to its door
        self.false_starts = {}  # door -> [(point, time)] approaches not (yet) followed by a passage
        self.arrived_unpaired = []  # people who appeared at a door before anybody vanished on the other side
        self.expected = {}  # room -> time someone vanished at its unseen door, walking towards it
        self.arrivals = {}  # room -> time someone last came in through a door
        self.arrived_from = {}  # room -> where that person came from (OUTSIDE: into the home)
        self.vanished = {}  # room -> time a counted person last vanished without leaving
        self.observed_at = {}  # room -> time someone was last visible there
        self.max_people = None  # people living in the home (incl. regular guests)
        self.last_step = None

    def name(self, room):
        return OUTSIDE if room == OUTSIDE else self.labels.get(room, room)

    def reason(self, room):
        """Reason of a room with display names, or None."""
        reason = self.reasons.get(room)
        if reason is None:
            return None
        return {k: self.name(v) if k in ("from", "to") and v is not None else v for k, v in reason.items()}

    # -- Setup ---------------------------------------------------------------
    def configure(self, rooms, doors, labels=None):
        self.rooms, self.doors = rooms, doors
        if labels is not None:
            self.labels = dict(labels)
        # Counts of rooms that are (temporarily) not on the map are kept, e.g.
        # while the maps load after a restart.
        self.tracks = [t for t in self.tracks if t.room is None or t.room in rooms]

    def doors_of(self, room):
        return [d for d in self.doors if room in (d.a, d.b)]

    def door_between(self, a, b):
        return [d for d in self.doors if {d.a, d.b} == {a, b}]

    def room_at(self, floor, point):
        best, best_distance = None, None
        for name, room in self.rooms.items():
            if room["floor"] != floor or not room.get("polygon"):
                continue
            if inside(point, room["polygon"]):
                return name
            d = distance(point, room["polygon"])
            if d <= EDGE and (best_distance is None or d < best_distance):
                best, best_distance = name, d
        return best

    # -- Counts ----------------------------------------------------------------
    def count(self, room):
        return self.counts.get(room, 0)

    def occupied(self, room):
        return self.count(room) > 0

    def _change(self, room, delta, code, now, source=None, target=None):
        if room is None or room == OUTSIDE or room not in self.rooms:
            return
        self.counts[room] = max(0, self.count(room) + delta)
        self.reasons[room] = {"code": code, "from": source, "to": target}
        if delta < 0 and code in (MOVED, WENT_OUT):
            # The radar left behind holds the last coordinates of whoever just
            # went for a few seconds; that echo is nobody new in the room.
            for track in self.tracks:
                if track.room == room:
                    track.echo = (now, track.point)
        self.events.append((now, room, delta, code, source, target))
        del self.events[:-40]

    def transfer(self, source, target, now):
        for door in self.door_between(source, target):
            self.false_starts.pop(id(door), None)
        self._change(source, -1, MOVED, now, source, target)
        self._change(target, +1, MOVED, now, source, target)
        self._arrive(target, now, source)

    def _arrive(self, room, now, source=None):
        if room in self.rooms:
            self.arrivals[room] = now
            self.arrived_from[room] = source

    def reset(self, room, now, code=RELEASED):
        self.counts[room] = 0
        self.reasons[room] = {"code": code, "from": None, "to": None}
        for track in self.tracks:
            if track.room == room:
                track.counted = False
        self.deaths = [d for d in self.deaths if d["room"] != room]
        self.lost = [d for d in self.lost if d["room"] != room]

    def _behind_far_door(self, track):
        """Seen through a door into a room on another floor map: this map
        shows nothing of that room, its own radar counts who is there. The
        sighting still lights this room early for somebody walking in.
        Returns that door, or None."""
        polygon = self.rooms.get(track.room, {}).get("polygon")
        if not polygon or inside(track.point, polygon) or distance(track.point, polygon) <= BEYOND_FAR_DOOR:
            return None
        return next(
            (
                d
                for d in self.doors_of(track.room)
                if d.far and (here := d.at(track.floor)) is not None and math.dist(track.point, here) <= FAR_DOOR_REACH
            ),
            None,
        )

    def _shadowed(self, track, now):
        """Seen at a door to another floor map while the radar on the other
        side still follows a counted person at or through that door: the
        same person, seen twice. Counted here once that radar lets go of
        them, or once they walk on into this room."""
        if track.shadow_of is not None:
            source = next((t for t in self.tracks if t.id == track.shadow_of), None)
            if source and source.counted and now - source.seen <= TRACK_TTL and self._near_far_door(track):
                return True
            track.shadow_of = None
            return False
        for door in self.doors_of(track.room):
            here = door.at(track.floor) if door.far else None
            if here is None or math.dist(track.point, here) > FAR_DOOR_REACH:
                continue
            other = door.other(track.room)
            source = next(
                (
                    t
                    for t in self.tracks
                    if t.room == other
                    and t.counted
                    and now - t.seen <= TRACK_TTL
                    and (
                        self._behind_far_door(t)
                        or (
                            door.distance(t.floor, t.point) is not None and door.distance(t.floor, t.point) <= DOOR_NEAR
                        )
                    )
                ),
                None,
            )
            if source is not None:
                track.shadow_of = source.id
                return True
        return False

    def _near_far_door(self, track):
        return any(
            d.far and (here := d.at(track.floor)) is not None and math.dist(track.point, here) <= FAR_DOOR_REACH
            for d in self.doors_of(track.room)
        )

    @staticmethod
    def _echo(track, now):
        if track.echo is None:
            return False
        when, point = track.echo
        if now - when > ECHO_HOLD or math.dist(track.point, point) > ECHO_MOVE:
            track.echo = None
            return False
        return True

    def visible(self, room, now):
        """How many people are certainly visible at the same time?"""
        tracks = [
            t
            for t in self.tracks
            if t.room == room
            and t.seen == now
            and not self._echo(t, now)
            and not self._behind_far_door(t)
            and not self._shadowed(t, now)
        ]
        first = [t for t in tracks if t.age(now) >= CONFIRM_ONE]
        if not first:
            return 0
        steady = [t for t in tracks if t.age(now) >= CONFIRM_MORE]
        chosen = []
        for track in sorted(steady, key=lambda t: t.born):
            if all(math.dist(track.point, other.point) >= SEPARATION for other in chosen):
                chosen.append(track)
        return max(1, len(chosen))

    def observed(self, room, now):
        """A confirmed target in the latest measurement, evaluated slightly later."""
        return (
            self.last_step is not None
            and 0 <= now - self.last_step <= TRACK_TTL
            and self.visible(room, self.last_step) > 0
        )

    # -- Measurement step --------------------------------------------------------
    def step(self, now, observations, hold=None):
        """observations: list of (floor, point[, room]); room forces the
        assignment (sub-areas). hold: rooms whose occupancy is not held."""
        self.last_step = now
        merged = self._merge(observations)
        # Held occupants remain candidates even after a long radar dropout.
        self.lost = [d for d in self.lost if self.count(d["room"]) > 0]
        alive = [t for t in self.tracks if now - t.seen <= TRACK_TTL]
        pairs = sorted(
            (
                (math.dist(t.point, o[1]), i, j)
                for i, t in enumerate(alive)
                for j, o in enumerate(merged)
                if t.floor == o[0]
            ),
            key=lambda p: p[0],
        )
        used_tracks, used_obs = set(), set()
        for gap, i, j in pairs:
            if gap > GATE or i in used_tracks or j in used_obs:
                continue
            if not self._can_match(alive[i], merged[j], now):
                continue
            used_tracks.add(i)
            used_obs.add(j)
            self._move(alive[i], merged[j], now)
        self._expect(now, alive, used_tracks)
        for j, obs in enumerate(merged):
            if j not in used_obs:
                room = obs[2] if len(obs) > 2 and obs[2] else self.room_at(obs[0], obs[1])
                track = Track(obs[0], obs[1], room, now)
                track.sensors = obs[3] if len(obs) > 3 else frozenset()
                self._reacquire(track)
                self.tracks.append(track)
        for track in list(self.tracks):
            if now - track.seen > TRACK_TTL:
                self.tracks.remove(track)
                self._died(track, now)
            elif not track.counted and track.room and track.age(now) >= CONFIRM_ONE and track.seen == now:
                self._born(track, now)
        self._settle_deaths(now)
        self._arriving(now)
        seen_now = {}
        for room in self.rooms:
            seen = seen_now[room] = self.visible(room, now)
            if seen:
                self.observed_at[room] = now
            if seen > self.count(room):
                self.counts[room] = seen
                self.reasons[room] = {"code": SEEN, "from": None, "to": None}
            if hold and room in hold and seen == 0 and self.count(room):
                self.counts[room] = 0
                self.reasons[room] = {"code": HOLD_OFF, "from": None, "to": None}
        self._limit(now, seen_now)
        self._approach(now)

    def _expect(self, now, alive, matched):
        """Somebody just lost at a door into a room no sensor sees behind it.

        Nothing will confirm the passage before the track ends, and a dropout
        at the door does not release the room either. The room ahead may still
        light up at once: its count does not change, so a person who in fact
        stayed loses nothing."""
        for i, track in enumerate(alive):
            if i in matched or not track.counted or track.room is None:
                continue
            door = self._door_near(track, track.seen, True)
            if door is None:
                continue
            other = door.other(track.room)
            if other in self.rooms and not door.covered_into(other):
                self.expected[other] = now

    def _limit(self, now, seen):
        """Never count more people than live in the home.

        Every departure the sensors miss leaves a held place behind; without a
        limit the counts only grow. A held place nobody is visible in goes
        first: the room someone just vanished from (the same person walked
        on), otherwise the one confirmed longest ago. People who are visible
        are never removed, so a second person sitting still elsewhere stays
        as long as the limit allows it."""
        if not self.max_people:
            return
        while sum(self.count(r) for r in self.rooms) > self.max_people:
            candidates = [r for r in self.rooms if self.count(r) > seen.get(r, 0)]
            if not candidates:
                return
            recent = [r for r in candidates if now - self.vanished.get(r, -1e9) <= VANISH_WINDOW]
            if recent:
                room = max(recent, key=lambda r: self.vanished[r])
            else:
                room = min(candidates, key=lambda r: (self.observed_at.get(r, -1e9), -self.count(r)))
            self._change(room, -1, HOUSEHOLD, now)
            self.vanished.pop(room, None)
            if self.count(room) == 0:
                self.lost = [d for d in self.lost if d["room"] != room]
                self.deaths = [d for d in self.deaths if d["room"] != room]

    def _merge(self, observations):
        """One person seen by several radars is one observation.

        Each radar keeps its own room for targets near its outline, so the
        same person in the hall used to arrive as a hall, a living room and a
        bathroom observation, each counted on its own. Targets of all sensors
        within MERGE are fused. The room of the fused target comes from the
        sensor that sees it deepest inside its own room; without such a
        sensor, from a room all members agree on, otherwise the map decides.
        Sub-areas (no outline) are only fused with their own targets."""
        groups = []
        observations = self._without_shadows(observations)
        for obs in observations:
            floor, point = obs[0], list(obs[1])
            forced = obs[2] if len(obs) > 2 else None
            sensor = obs[3] if len(obs) > 3 else None
            sub = forced is not None and forced in self.rooms and not self.rooms[forced].get("polygon")
            for group in groups:
                if group["floor"] != floor or math.dist(group["point"], point) >= MERGE:
                    continue
                if (sub or group["sub"]) and group["forced"] != {forced}:
                    continue
                n = group["n"]
                group["point"] = [(group["point"][k] * n + point[k]) / (n + 1) for k in range(2)]
                group["n"] += 1
                break
            else:
                group = {
                    "floor": floor,
                    "point": point,
                    "n": 1,
                    "sub": sub,
                    "forced": set(),
                    "sensors": set(),
                    "own": [],
                }
                groups.append(group)
            group["forced"].add(forced)
            if sensor is not None:
                group["sensors"].add(sensor)
            depth = self._depth(sensor, forced, point)
            if depth is not None:
                group["own"].append((depth, forced))
        merged = []
        for g in groups:
            if g["own"]:
                room = max(g["own"], key=lambda o: o[0])[1]
            elif len(g["forced"]) == 1:
                room = next(iter(g["forced"]))
            else:
                room = None
            merged.append((g["floor"], g["point"], room, frozenset(g["sensors"])))
        return merged

    def _without_shadows(self, observations):
        """Drop sub-area targets while the person is next door.

        A ceiling radar cannot tell front from back: somebody in the next
        room near its door shows up mirrored, in the balcony zone of the lab.
        While the radar of that neighbour sees somebody inside its own room
        near the shared door, a sub-area target is that person."""
        near = []
        for obs in observations:
            sensor = obs[3] if len(obs) > 3 else None
            if self._depth(sensor, obs[2] if len(obs) > 2 else None, obs[1]) is not None:
                near.append((obs[0], sensor, obs[1]))
        if not near:
            return observations
        kept = []
        for obs in observations:
            forced = obs[2] if len(obs) > 2 else None
            parent = self._parent(forced)
            if parent is not None and any(
                floor == obs[0]
                and other != parent
                and any(
                    d.at(floor) is not None and math.dist(point, d.at(floor)) <= SUB_SHADOW
                    for d in self.door_between(parent, other)
                )
                for floor, other, point in near
            ):
                continue
            kept.append(obs)
        return kept

    def _parent(self, room):
        """The room a sub-area belongs to (linked by a door without position)."""
        if room is None or room not in self.rooms or self.rooms[room].get("polygon"):
            return None
        return next((d.other(room) for d in self.doors_of(room) if d.point is None), None)

    def _depth(self, sensor, forced, point):
        """How far a sensor's target lies inside the sensor's own room (mm), or None."""
        if sensor is None or forced != sensor:
            return None
        polygon = self.rooms.get(sensor, {}).get("polygon")
        if not polygon or not inside(point, polygon):
            return None
        return min(_segment_distance(point, a, b) for a, b in zip(polygon, polygon[1:] + polygon[:1]))

    def _can_match(self, track, obs, now):
        """A trusted sighting in another room must not refresh a stuck track.

        Missing the doorway does not prove who moved, but the receiving
        radar still proves presence in its own room. Start a separate track
        there instead of reporting the old room as visibly occupied forever.
        Unassigned wall echoes continue to use the strict crossing checks.
        """
        _, point, forced = obs[:3]
        if not forced or forced == track.room or track.room is None:
            return True
        source = self.rooms.get(track.room, {}).get("polygon")
        target = self.rooms.get(forced, {}).get("polygon")
        if not source or not target or not inside(point, target) or distance(point, source) < 200:
            return True
        return any(self._crossed_door(track, door, now, point) for door in self.door_between(track.room, forced))

    def _crossed_door(self, track, door, now, next_point=None):
        """An inside-to-outside segment crosses the outline at this doorway."""
        polygon = self.rooms.get(track.room, {}).get("polygon")
        here = door.at(track.floor)
        if not polygon or here is None:
            return False
        since = min(now, self._stopped(track)) if next_point is None else now
        recent = [(t, p) for t, p in track.history if since - t <= 4 and t <= now and t >= track.room_since]
        if next_point is not None:
            recent.append((now, next_point))
        for (_, a), (_, b) in pairwise(recent):
            if not inside(a, polygon) or inside(b, polygon):
                continue
            dx, dy = b[0] - a[0], b[1] - a[1]
            for c, d in zip(polygon, polygon[1:] + polygon[:1]):
                ex, ey = d[0] - c[0], d[1] - c[1]
                det = dx * ey - dy * ex
                if abs(det) < 1e-9:
                    continue
                cx, cy = c[0] - a[0], c[1] - a[1]
                along = (cx * ey - cy * ex) / det
                edge = (cx * dy - cy * dx) / det
                if 0 <= along <= 1 and 0 <= edge <= 1:
                    crossing = [a[0] + along * dx, a[1] + along * dy]
                    if math.dist(crossing, here) <= DOOR_CROSS:
                        return True
        return False

    def _move(self, track, obs, now):
        floor, point, forced = obs[:3]
        track.sensors = obs[3] if len(obs) > 3 else frozenset()
        previous = track.point
        track.point, track.seen = point, now
        # A held coordinate repeats each step; keep its first time only, or a
        # few seconds of standing still push the walk out of the history.
        if point != track.history[-1][1]:
            track.history.append((now, point))
            del track.history[:-40]
        room = forced or self.room_at(floor, point)
        if forced and forced == track.room:
            # The radar of the room being left keeps its own room at uncertain
            # edges, but it often still sees a few decimetres through the
            # doorway. Clearly beyond, the passage checks below decide; waiting
            # for the track to end cost seconds of darkness on the other side.
            beyond = self.room_at(floor, point)
            if beyond and beyond != forced and self.door_between(forced, beyond):
                room = beyond
        if room is None or room == track.room:
            track.pending = None
            return
        if track.room is None:
            track.room, track.room_since = room, now
            return
        # Rooms change only through a door; otherwise a sensor sees through a wall.
        doors = self.door_between(track.room, room)
        source_polygon = self.rooms.get(track.room, {}).get("polygon")
        target_polygon = self.rooms.get(room, {}).get("polygon")
        if source_polygon and target_polygon:
            valid_passage = (
                inside(point, target_polygon)
                and distance(point, source_polygon) >= 200
                and any(self._crossed_door(track, d, now) for d in doors)
            )
        else:
            # Explicit sub-areas have radar-coordinate assignments, no outline.
            valid_passage = any(
                d.point is None or min(d.distance(floor, previous) or 1e9, d.distance(floor, point) or 1e9) <= DOOR_PASS
                for d in doors
            )
        if not valid_passage:
            track.pending = None
            return
        if track.pending != room:
            track.pending, track.pending_since = room, now
            # Through the door: light the room now, the count follows once the
            # passage is confirmed.
            self.expected[room] = now
            return
        if now - track.pending_since >= 0.5:
            source = track.room
            track.room, track.pending, track.room_since = room, None, now
            if track.counted:
                self.transfer(source, room, now)
            else:
                track.counted = True
                self._change(room, +1, MOVED, now, source, room)
                self._arrive(room, now, source)
            self.deaths = [d for d in self.deaths if not (d["room"] == source and d["to"] == room)]

    def _door_near(self, track, now, require_approach, limit=None, point=None):
        best = None
        limit = limit or (DOOR_LEAVE if require_approach else DOOR_NEAR)
        stop = self._stopped(track)
        for door in self.doors_of(track.room):
            d = door.distance(track.floor, point or track.point)
            if d is None or d > limit:
                continue
            if require_approach:
                window = PRE_STOP if track.seen - stop >= 1 else 4
                earlier = [door.distance(track.floor, p) for t, p in track.history if stop - t <= window]
                if not earlier or max(earlier) - d < DOOR_APPROACH:
                    continue
            if best is None or d < best[1]:
                best = (door, d)
        return best[0] if best else None

    @staticmethod
    def _stopped(track):
        """Since when the track stands at its last spot.

        Walked to the door, stopped (opening it) and vanished: the walk before
        the stop counts. The radar holds the last spot meanwhile."""
        stop = track.seen
        for t, p in reversed(track.history):
            if math.dist(p, track.point) > STANDSTILL:
                break
            stop = t
        return stop

    def _reacquire(self, track, confirmed=False):
        # An unpaired departure is still held. Reappearing on the same side
        # cancels it instead of becoming another arrival.
        departure = next(
            (
                d
                for d in self.deaths
                if d["room"] == track.room
                and d["door"].distance(track.floor, track.birth_point) is not None
                and d["door"].distance(track.floor, track.birth_point) <= DOOR_NEAR
            ),
            None,
        )
        if departure:
            self.deaths.remove(departure)
            track.counted = True
            return True
        lost = next(
            (
                item
                for item in self.lost
                if item["room"] == track.room
                and item["floor"] == track.floor
                and (
                    math.dist(item["point"], track.birth_point) <= MERGE
                    or self._door_near(track, track.born, False) is None
                )
                and self.count(track.room) > 0
            ),
            None,
        )
        if lost:
            self.lost.remove(lost)
            if track.born - lost["time"] > REACQUIRE_WINDOW and self._door_near(track, track.born, False):
                # Gone at a door long ago and back at a door: somebody came in
                # (home again after hours), not a radar dropout.
                return False
            track.counted = True
            return True
        # A sub-area shares the radar of its room: whoever vanished at the
        # edge between them and reappears right there on the other side is the
        # same person, not a second one. Keeping both held hid the departure.
        # Only once confirmed: a single echo must not move the occupancy.
        if not confirmed:
            return False
        lost = next(
            (
                item
                for item in self.lost
                if item["room"] != track.room
                and item["floor"] == track.floor
                and self.count(item["room"]) > 0
                and any(d.point is None for d in self.door_between(item["room"], track.room))
                and math.dist(item["point"], track.birth_point) <= MERGE
            ),
            None,
        )
        if lost:
            self.lost.remove(lost)
            track.counted = True
            self.transfer(lost["room"], track.room, track.born)
            return True
        return False

    def _born(self, track, now):
        if self._behind_far_door(track):
            return
        track.counted = True
        if self._reacquire(track, True):
            return
        door = self._door_near(track, now, False) or self._door_near(track, now, False, ARRIVE_NEAR, track.birth_point)
        if door is None:
            # Appeared in the middle of the room: someone who was there, sitting still.
            return
        other = door.other(track.room)
        if self._moving_in(track, door):
            self._arrive(track.room, now, other)
        paired = next(
            (d for d in self.deaths if d["door"] is door and d["room"] == other and now - d["time"] <= PAIR_WINDOW),
            None,
        )
        via = next(
            (
                d
                for d in self.deaths
                if d["to"] == other
                and d["room"] != track.room
                and d["door"] is not door
                and now - d["time"] <= PAIR_WINDOW
                and not self.visible(other, now)
            ),
            None,
        )
        if paired:
            self.deaths.remove(paired)
            self.transfer(other, track.room, now)
        elif via:
            # Out of one room into the hall and straight into the next one,
            # in a corner the hall radar does not see: the path is the
            # evidence, both doors open into the same hall.
            self.deaths.remove(via)
            self.transfer(via["room"], track.room, now)
        elif self.count(other) > self.visible(other, now) and not door.covered_into(other):
            # A sensor cannot see departure from the other side (e.g. the
            # long corridor). Arrival here completes that unseen passage;
            # move its held person instead of adding another on every trip.
            self.transfer(other, track.room, now)
        else:
            # Appearance alone is not proof of another person. Radar targets
            # have no stable identity; repeated dropouts used to inflate counts.
            # Simultaneous, separated targets establish the lower bound in step().
            if other != OUTSIDE:
                self.arrived_unpaired.append({"time": now, "room": track.room, "from": other})
                del self.arrived_unpaired[:-10]
            self.reasons[track.room] = {
                "code": CAME_IN if other == OUTSIDE else APPEARED_AT_DOOR,
                "from": other,
                "to": track.room,
            }

    def _moving_in(self, track, door):
        """Walking away from the door into the room. Someone who reappears at
        the door after a radar dropout, or is on the way out, is no arrival."""
        if door.point is None:
            return True
        first = door.distance(track.floor, track.history[0][1])
        last = door.distance(track.floor, track.point)
        return first is not None and last is not None and last - first >= ARRIVAL_STEP

    def _died(self, track, now):
        if not track.counted or track.room is None:
            return
        door = self._door_near(track, now, True) or self._door_beyond(track) or self._behind_far_door(track)
        if door is None:
            # Lingering at the door, not walking at it: somebody who already
            # appeared behind it is the evidence of the passage.
            near = self._door_near(track, now, False, DOOR_LEAVE)
            if near is not None and self._appeared_behind(track, near, now):
                return
            self.lost.append({"room": track.room, "floor": track.floor, "point": track.point, "time": track.seen})
            self.vanished[track.room] = track.seen
            return
        other = door.other(track.room)
        crossed = self._crossed_door(track, door, track.seen)
        if self._appeared_behind(track, door, now):
            return
        if other == OUTSIDE and crossed:
            self._change(track.room, -1, WENT_OUT, now, track.room, OUTSIDE)
        elif other != OUTSIDE:
            self.deaths.append({"time": now, "door": door, "room": track.room, "to": other, "crossed": crossed})
        else:
            self.lost.append({"room": track.room, "floor": track.floor, "point": track.point, "time": track.seen})
            self.vanished[track.room] = track.seen

    def _appeared_behind(self, track, door, now):
        """The radar ahead saw them come in before this one let go of them (it
        holds the last coordinates for a few seconds). They are already
        counted there; this room is left."""
        other = door.other(track.room)
        if other == OUTSIDE or track.room not in self.rooms:
            return False
        early = next(
            (
                a
                for a in self.arrived_unpaired
                if 0 <= now - a["time"] <= PAIR_WINDOW
                and a["room"] != track.room
                and (a["room"] == other or a["from"] == other)
            ),
            None,
        )
        if early is not None:
            self.arrived_unpaired.remove(early)
            self._change(track.room, -1, MOVED, now, track.room, early["room"])
            return True
        # Or someone came in right behind the door who was taken for the
        # person held there (a reacquired place): counted already.
        behind = door.at(self.rooms.get(other, {}).get("floor"))
        if behind is None or not any(
            t.room == other
            and t.counted
            and 0 <= now - t.born <= PAIR_WINDOW
            and math.dist(t.birth_point, behind) <= ARRIVE_NEAR
            for t in self.tracks
        ):
            return False
        self._change(track.room, -1, MOVED, now, track.room, other)
        return True

    def _door_beyond(self, track):
        """Lost outside its room, inside a neighbour it has a door to (within
        1.3 m of that door):
        the radar of the room left followed the person through the door
        (crossing the outline a little beside the marked door point)."""
        polygon = self.rooms.get(track.room, {}).get("polygon")
        if not polygon or inside(track.point, polygon):
            return None
        beyond = next(
            (
                r
                for r, info in self.rooms.items()
                if r != track.room
                and info["floor"] == track.floor
                and info.get("polygon")
                and inside(track.point, info["polygon"])
            ),
            None,
        )
        if beyond is None:
            return None
        doors = [
            d
            for d in self.door_between(track.room, beyond)
            if (gap := d.distance(track.floor, track.point)) is not None and gap <= DOOR_PASS
        ]
        return min(doors, key=lambda d: d.distance(track.floor, track.point)) if doors else None

    def _settle_deaths(self, now):
        for death in list(self.deaths):
            door = death["door"]
            if death.get("crossed") and not door.covered_into(death["to"]) and now - death["time"] >= UNSEEN_PASS:
                # No sensor sees the other side: the passage itself is the evidence.
                self.deaths.remove(death)
                self.transfer(death["room"], death["to"], now)
            elif now - death["time"] > PAIR_WINDOW:
                # The other side should have seen them: keep a reacquisition
                # candidate for the person still held on this side.
                self.deaths.remove(death)
                self.lost.append(
                    {
                        "room": death["room"],
                        "floor": self.rooms.get(death["room"], {}).get("floor", door.floor),
                        "point": door.at(self.rooms.get(death["room"], {}).get("floor", door.floor)) or door.point,
                        "time": death["time"],
                    }
                )
                self.vanished[death["room"]] = death["time"]

    def _arriving(self, now):
        """A new target right behind the door of an empty room is somebody
        coming in. Confirming it costs a second report (about a second);
        light the room at once. The count still waits for the confirmation;
        a stray echo only pre-lights the room."""
        for track in self.tracks:
            if (
                track.seen == now
                and not track.counted
                and track.room in self.rooms
                and self.rooms[track.room].get("polygon")
                and not self.count(track.room)
                and self._door_near(track, now, False) is not None
            ):
                self.expected[track.room] = now

    def _heading_at(self, track, door, now):
        """The last two seconds of the track point at the door."""
        recent = [p for t, p in track.history if now - t <= 2 and t >= track.room_since]
        here = door.at(track.floor)
        if len(recent) < 2 or here is None:
            return False
        mx, my = recent[-1][0] - recent[0][0], recent[-1][1] - recent[0][1]
        dx, dy = here[0] - recent[0][0], here[1] - recent[0][1]
        if not (mx or my) or not (dx or dy):
            return False
        angle = abs(math.degrees(math.atan2(mx * dy - my * dx, mx * dx + my * dy)))
        return angle <= APPROACH_HEADING

    def _approach(self, now):
        for track in self.tracks:
            if track.seen != now or track.room is None:
                continue
            for door in self.doors_of(track.room):
                d = door.distance(track.floor, track.point)
                if d is not None and d > APPROACH_ZONE + APPROACH_REARM:
                    track.approached.pop(id(door), None)
                if d is None or d > APPROACH_ZONE:
                    if track.approached.get(id(door)) == "active":
                        track.approached[id(door)] = "used"
                    continue
                # Only since entering this room: whoever just came through the
                # door is walking away from it, not towards it.
                earlier = [
                    door.distance(track.floor, p) for t, p in track.history if now - t <= 2 and t >= track.room_since
                ]
                towards = bool(earlier) and max(earlier) - d >= DOOR_APPROACH and self._heading_at(track, door, now)
                if not towards:
                    if track.approached.get(id(door)) == "active":
                        track.approached[id(door)] = "used"
                    continue
                other = door.other(track.room)
                if other in self.rooms:
                    # One approach per walk towards the door, and none again
                    # from where the last one ended without passing: shifting
                    # on a chair near it pre-lit the next room every 25 s.
                    state = track.approached.get(id(door))
                    if state is None:
                        start = next(p for t, p in track.history if now - t <= 2 and t >= track.room_since)
                        spots = [x for x in self.false_starts.get(id(door), []) if now - x[1] <= SPOT_MEMORY]
                        repeat = any(math.dist(point, start) <= SPOT_RADIUS for point, _ in spots)
                        self.false_starts[id(door)] = [*spots, (start, now)][-10:]
                        state = track.approached[id(door)] = "used" if repeat else "active"
                    if state == "active":
                        self.approaching[other] = now
                    if other in track.sensors and d <= DOOR_NEAR:
                        # The radar of the room ahead already sees them
                        # coming through its door: light it fully.
                        self.expected[other] = now

    def snapshot(self, now):
        return {
            "counts": dict(self.counts),
            "reasons": {room: self.reason(room) for room in self.reasons},
            "tracks": [
                {
                    "id": t.id,
                    "floor": t.floor,
                    "point": [round(v) for v in t.point],
                    "room": t.room,
                    "age": round(t.age(now), 1),
                }
                for t in self.tracks
                if now - t.seen <= TRACK_TTL
            ],
            "doors": [
                {
                    "a": d.a,
                    "b": d.b,
                    "floor": d.floor,
                    "point": d.point and [round(v) for v in d.point],
                    "covered": d.covered,
                    **({"far": {"floor": d.far[0], "point": [round(v) for v in d.far[1]]}} if d.far else {}),
                }
                for d in self.doors
            ],
            "events": [
                {
                    "time": round(t, 1),
                    "room": self.name(r),
                    "delta": delta,
                    "code": code,
                    "from": self.name(a) if a is not None else None,
                    "to": self.name(b) if b is not None else None,
                }
                for t, r, delta, code, a, b in self.events[-10:]
            ],
        }
