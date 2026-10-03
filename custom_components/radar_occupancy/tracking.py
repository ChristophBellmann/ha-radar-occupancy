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

from .geometry import distance, inside

OUTSIDE = "outside"  # everything without a radar: stairs, front door, unsensed map rooms
MERGE = 800  # mm: targets of different sensors that are the same person
GATE = 1500  # mm: largest jump of a track between two measurements
TRACK_TTL = 2.0  # s without a measurement: the track ends
EDGE = 400  # mm: tolerance at room outlines
DOOR_PASS = 1300  # mm: a track changes rooms only this close to a door
DOOR_NEAR = 1100  # mm: appearing "at the door"
DOOR_LEAVE = 800  # mm: vanishing "at the door" (stricter: it switches lights off)
DOOR_APPROACH = 300  # mm: a target must have come this much closer to the door
APPROACH_ZONE = 1500  # mm: pre-light when a target walks this close towards a door
PAIR_WINDOW = 8.0  # s: vanishing at a door and appearing on the other side
UNSEEN_PASS = 2.0  # s: door into an area no sensor sees
CONFIRM_ONE = 1.0  # s: first target in an empty room
CONFIRM_MORE = 3.0  # s: each further target visible at the same time
SEPARATION = 1000  # mm: two simultaneous targets must be this far apart

# Reason codes
SEEN = "seen_in_room"  # someone visible in the room
MOVED = "moved"  # walked from one room to another (from, to)
CAME_IN = "came_in"  # came from outside the home
APPEARED_AT_DOOR = "appeared_at_door"  # at the door to `from`, nobody seen leaving there
WENT_OUT = "went_out"  # left the home
RELEASED = "released"  # released by hand
HOLD_OFF = "hold_off"  # no target and hold switched off
REASONS = (SEEN, MOVED, CAME_IN, APPEARED_AT_DOOR, WENT_OUT, RELEASED, HOLD_OFF)


class Door:
    def __init__(self, a, b, floor, point, covered=True):
        self.a, self.b, self.floor, self.point, self.covered = a, b, floor, point, covered

    def covered_into(self, room):
        """Does a sensor see who walks through this door into `room`?"""
        return self.covered.get(room, True) if isinstance(self.covered, dict) else self.covered

    def other(self, room):
        return self.b if room == self.a else self.a if room == self.b else None

    def distance(self, floor, point):
        if self.point is None or floor != self.floor:
            return None
        return math.dist(point, self.point)

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
        self.events = []
        self.reasons = {}  # room -> {"code": ..., "from": room key, "to": room key}
        self.approaching = {}  # room -> time of the last approach to its door

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
        self.events.append((now, room, delta, code, source, target))
        del self.events[:-40]

    def transfer(self, source, target, now):
        self._change(source, -1, MOVED, now, source, target)
        self._change(target, +1, MOVED, now, source, target)

    def reset(self, room, now, code=RELEASED):
        self.counts[room] = 0
        self.reasons[room] = {"code": code, "from": None, "to": None}
        for track in self.tracks:
            if track.room == room:
                track.counted = False
        self.deaths = [d for d in self.deaths if d["room"] != room]

    def visible(self, room, now):
        """How many people are certainly visible at the same time?"""
        tracks = [t for t in self.tracks if t.room == room and t.seen == now]
        first = [t for t in tracks if t.age(now) >= CONFIRM_ONE]
        if not first:
            return 0
        steady = [t for t in tracks if t.age(now) >= CONFIRM_MORE]
        chosen = []
        for track in sorted(steady, key=lambda t: t.born):
            if all(math.dist(track.point, other.point) >= SEPARATION for other in chosen):
                chosen.append(track)
        return max(1, len(chosen))

    # -- Measurement step --------------------------------------------------------
    def step(self, now, observations, hold=None):
        """observations: list of (floor, point[, room]); room forces the
        assignment (sub-areas). hold: rooms whose occupancy is not held."""
        merged = self._merge(observations)
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
            used_tracks.add(i)
            used_obs.add(j)
            self._move(alive[i], merged[j], now)
        for j, obs in enumerate(merged):
            if j not in used_obs:
                room = obs[2] if len(obs) > 2 and obs[2] else self.room_at(obs[0], obs[1])
                self.tracks.append(Track(obs[0], obs[1], room, now))
        for track in list(self.tracks):
            if now - track.seen > TRACK_TTL:
                self.tracks.remove(track)
                self._died(track, now)
            elif not track.counted and track.room and track.age(now) >= CONFIRM_ONE and track.seen == now:
                self._born(track, now)
        self._settle_deaths(now)
        for room in self.rooms:
            seen = self.visible(room, now)
            if seen > self.count(room):
                self.counts[room] = seen
                self.reasons[room] = {"code": SEEN, "from": None, "to": None}
            if hold and room in hold and seen == 0 and self.count(room):
                self.counts[room] = 0
                self.reasons[room] = {"code": HOLD_OFF, "from": None, "to": None}
        self._approach(now)

    def _merge(self, observations):
        merged = []
        for obs in observations:
            floor, point = obs[0], list(obs[1])
            forced = obs[2] if len(obs) > 2 else None
            for group in merged:
                if group["floor"] == floor and group["room"] == forced and math.dist(group["point"], point) < MERGE:
                    n = group["n"]
                    group["point"] = [(group["point"][k] * n + point[k]) / (n + 1) for k in range(2)]
                    group["n"] += 1
                    break
            else:
                merged.append({"floor": floor, "point": point, "room": forced, "n": 1})
        return [(g["floor"], g["point"], g["room"]) for g in merged]

    def _move(self, track, obs, now):
        floor, point, forced = obs
        previous = track.point
        track.point, track.seen = point, now
        track.history.append((now, point))
        del track.history[:-40]
        room = forced or self.room_at(floor, point)
        if room is None or room == track.room:
            track.pending = None
            return
        if track.room is None:
            track.room, track.room_since = room, now
            return
        # Rooms change only through a door; otherwise a sensor sees through a wall.
        doors = self.door_between(track.room, room)
        if not any(
            d.point is None or min(d.distance(floor, previous) or 1e9, d.distance(floor, point) or 1e9) <= DOOR_PASS
            for d in doors
        ):
            track.pending = None
            return
        if track.pending != room:
            track.pending, track.pending_since = room, now
            return
        if now - track.pending_since >= 0.5:
            source = track.room
            track.room, track.pending, track.room_since = room, None, now
            if track.counted:
                self.transfer(source, room, now)
            else:
                track.counted = True
                self._change(room, +1, MOVED, now, source, room)
            self.deaths = [d for d in self.deaths if not (d["room"] == source and d["to"] == room)]

    def _door_near(self, track, now, require_approach):
        best = None
        limit = DOOR_LEAVE if require_approach else DOOR_NEAR
        for door in self.doors_of(track.room):
            d = door.distance(track.floor, track.point)
            if d is None or d > limit:
                continue
            if require_approach:
                earlier = [door.distance(track.floor, p) for t, p in track.history if track.seen - t <= 4]
                if not earlier or max(earlier) - d < DOOR_APPROACH:
                    continue
            if best is None or d < best[1]:
                best = (door, d)
        return best[0] if best else None

    def _born(self, track, now):
        track.counted = True
        door = self._door_near(track, now, False)
        if door is None:
            # Appeared in the middle of the room: someone who was there, sitting still.
            return
        other = door.other(track.room)
        paired = next(
            (d for d in self.deaths if d["door"] is door and d["room"] == other and now - d["time"] <= PAIR_WINDOW),
            None,
        )
        if paired:
            self.deaths.remove(paired)
            self.transfer(other, track.room, now)
        elif other == OUTSIDE:
            self._change(track.room, +1, CAME_IN, now, OUTSIDE, track.room)
        else:
            # Nobody was seen leaving on the other side: count here, take nothing off there.
            self._change(track.room, +1, APPEARED_AT_DOOR, now, other, track.room)

    def _died(self, track, now):
        if not track.counted or track.room is None:
            return
        door = self._door_near(track, now, True)
        if door is None:
            return
        other = door.other(track.room)
        if other == OUTSIDE:
            self._change(track.room, -1, WENT_OUT, now, track.room, OUTSIDE)
        else:
            self.deaths.append({"time": now, "door": door, "room": track.room, "to": other})

    def _settle_deaths(self, now):
        for death in list(self.deaths):
            door = death["door"]
            if not door.covered_into(death["to"]) and now - death["time"] >= UNSEEN_PASS:
                # No sensor sees the other side: the passage itself is the evidence.
                self.deaths.remove(death)
                self.transfer(death["room"], death["to"], now)
            elif now - death["time"] > PAIR_WINDOW:
                # The other side should have seen them: probably still in the room.
                self.deaths.remove(death)

    def _approach(self, now):
        for track in self.tracks:
            if track.seen != now or track.room is None:
                continue
            for door in self.doors_of(track.room):
                d = door.distance(track.floor, track.point)
                if d is None or d > APPROACH_ZONE:
                    continue
                # Only since entering this room: whoever just came through the
                # door is walking away from it, not towards it.
                earlier = [
                    door.distance(track.floor, p) for t, p in track.history if now - t <= 2 and t >= track.room_since
                ]
                if earlier and max(earlier) - d >= DOOR_APPROACH:
                    other = door.other(track.room)
                    if other in self.rooms:
                        self.approaching[other] = now

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
