# How tracking decides

This page describes map mode from the inside, for people who want to know
why a room was or was not freed. The numbers are the constants in
`tracking.py`.

## From radar targets to people

1. **Observations.** Every sensor reports up to three targets in its own
   coordinates. The calibration transforms them into map millimetres. Targets
   closer than 30 cm to the sensor (or than *Take over only from this
   distance*) are echoes and ignored; coordinates older than 5 s are not a
   live target.
2. **Merging.** Targets of all sensors closer than **80 cm** are the same
   person, whichever room each sensor would claim. The room of the merged
   target comes from the sensor that sees it deepest inside its *own* room;
   otherwise from a room all of them agree on; otherwise the map decides. The
   merged observation remembers which sensors saw it. Sub-areas are only
   merged with their own targets.
3. **Ghosts.** A target that a radar reports inside *another* room is
   dropped when that room's own radar is online, has the spot in view and
   sees nobody within 1.2 m of it (walls, reflections). In corners the room's
   radar cannot see, sightings through doors still count. A sub-area target
   is dropped while the radar of a neighbouring room sees somebody inside its
   room within **3 m** of the shared door: a ceiling radar shows people next
   door mirrored.
4. **Tracks.** Each observation is matched to the nearest track that could
   have moved there (at most **1.5 m** between two measurements). A track
   without measurement for **2 s** ends.
5. **Rooms.** A track belongs to the room whose outline contains it, with
   **40 cm** tolerance at outlines. A track changes rooms only within
   **1.3 m** of a door. Uncertain positions within 0.8 m of the measuring
   sensor's room outline keep that sensor's room.

## Counting

- The first target in an empty room counts after **1 s** (in practice the
  second report of an LD2450), each further simultaneous target after
  **3 s**, and only if it is at least **1 m** away from the others.
- A new target within **1.1 m** of a door of an empty room lights that room
  at once (expected); it is counted only once confirmed.
- Somebody appearing "at the door" (first report within **1.5 m**: radars
  see doorways late) of a room where nobody was seen leaving is
  `appeared_at_door`; arrivals must have moved at least 15 cm away from the
  door when confirmed.
- A nearby reappearance within **15 s** after a dropout is the same person,
  not a new entrant.

## Leaving

A track vanishing within **80 cm** of a door (stricter than appearing,
because it switches lights off) and the passage is **measured**:

- the track crossed the outline at the doorway (within 45 cm of the actual
  door), or
- a target appeared on the other side within **8 s** (paired), or
- the sensor of the room being left sees the person clearly beyond the
  doorway in the next room, or loses them just outside its outline inside a
  neighbour, within 1.3 m of their door (calibrations are a few decimetres
  off at doors), and somebody turns up on the other side, or
- the radar ahead saw them arrive up to **8 s before** the radar behind let
  go of them (sensors hold the last coordinates for a few seconds), or
- they left into a hall and came in through another door of the same hall
  within 8 s while nobody was visible in the hall (dead corners in front of
  the hall doors).

A track that walked to a door, **stopped** there (opening it) and then
vanished counts the walk before the stop (up to **6 s**): radars hold the
last spot while somebody stands still, so the walk would otherwise have aged
out. This is how leaving through the front door is seen.

Standing within **80 cm** of a door without walking at it and vanishing, while
somebody was just seen arriving right behind that door, is that person
moving there.

After somebody left a room, a target its radar keeps reporting at the same
spot for up to **6 s** is their echo, not a new person (unless it walks
**70 cm** away).

Doors into an area no sensor sees (stairs, an unsensed room) need the
measured crossing; the person is handed to the other side after **2 s**
unseen. Without evidence, the room stays held.

A person who vanished within the last **60 s** is the one who moved on when
somebody appears next door.

## Looking ahead

- **Approach.** A target within **1.5 m** of a door that came at least
  **30 cm** closer, walking at the door (within **35°**), pre-lights the room
  behind it, once per walk. Further approaches from the spot where one ended
  without passing (a desk chair) pre-light nothing for **4 h**; passing the
  door clears that. Walking more than 2.5 m away re-arms the door.
- **Through the door.** The first measurement of a valid door passage lights
  the room ahead; the count follows after confirmation (0.5 s).
- **Seen by the next room.** If the radar of that room is among the sensors
  that see the target and it is within 1.1 m of the door, the room behind is
  expected: full light.
- **Expected arrival.** A counted track lost near a door it walked towards,
  whose other side no sensor covers, makes the room ahead expected: full light
  at once. Occupancy does not change without proof; if nobody turns up, the
  light fades out 20 s after the last such sighting.

## Doors between two floor maps

Two robot maps often both show part of the same place: the upstairs robot
sees down the stairs into the lower hall, the downstairs robot sees that
hall up to the first step. A door marked with `set_door` from a room on one
map to a room on the other, with `x`/`y` on this map and `to_x`/`to_y` on the
other one, links them; it replaces the robot's passage at that doorway
(within 1 m), which otherwise led "outside".

- Leaving through it pairs with an arrival at its point on the other map,
  as at any door.
- A radar seeing through it (more than 10 cm outside its room, within 2.5 m
  of the door) does not count anybody there: that room has its own radar.
  The sighting still lights its own room early for somebody walking in, and
  losing a counted person there is leaving through that door.
- While one radar still follows a counted person at or through the door,
  the other radar's target at its side of the door is the same person; it
  counts once the first radar lets go of them or they walk on more than
  2.5 m.

## Household limit

Counts above *People in the home at most* drop the held place nobody is
visible in: first the room somebody just vanished from, otherwise the one
confirmed longest ago (`household_limit`). This place does **not** count as
"evidently left" for the [switched-off-by-hand](manual-off.md) rule.

## What it cannot do

- Radar targets carry no identity; two people crossing can swap tracks.
- People standing closer than about 1 m look like one target.
- A sensor sees only its field of view (about 7 m, ±60°); corners in front of
  doors the hall sensor cannot see are blind, which is why the expected
  arrival exists.
- A door opening is invisible; only people are seen.
