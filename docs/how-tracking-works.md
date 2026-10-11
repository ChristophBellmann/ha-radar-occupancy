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
2. **Merging.** Targets of different sensors closer than **80 cm** are the
   same person. The merged observation remembers which sensors saw it.
3. **Tracks.** Each observation is matched to the nearest track that could
   have moved there (at most **1.5 m** between two measurements). A track
   without measurement for **2 s** ends.
4. **Rooms.** A track belongs to the room whose outline contains it, with
   **40 cm** tolerance at outlines. A track changes rooms only within
   **1.3 m** of a door. Uncertain positions within 0.8 m of the measuring
   sensor's room outline keep that sensor's room.

## Counting

- The first target in an empty room counts after **1 s** (in practice the
  second report of an LD2450), each further simultaneous target after
  **3 s**, and only if it is at least **1 m** away from the others.
- Somebody appearing "at the door" (within **1.1 m**) of a room where
  nobody was seen leaving is `appeared_at_door`; arrivals must have moved at
  least 15 cm away from the door when confirmed.
- A nearby reappearance within **15 s** after a dropout is the same person,
  not a new entrant.

## Leaving

A track vanishing within **80 cm** of a door (stricter than appearing,
because it switches lights off) and the passage is **measured**:

- the track crossed the outline at the doorway (within 45 cm of the actual
  door), or
- a target appeared on the other side within **8 s** (paired), or
- the sensor of the room being left sees the person clearly beyond the
  doorway in the next room.

Doors into an area no sensor sees (stairs, an unsensed room) need the
measured crossing; the person is handed to the other side after **2 s**
unseen. Without evidence, the room stays held.

A person who vanished within the last **60 s** is the one who moved on when
somebody appears next door.

## Looking ahead

- **Approach.** A target within **1.5 m** of a door that came at least
  **30 cm** closer pre-lights the room behind it.
- **Seen by the next room.** If the radar of that room is among the sensors
  that see the target and it is within 1.1 m of the door, the room behind is
  expected: full light.
- **Expected arrival.** A counted track lost near a door it walked towards,
  whose other side no sensor covers, makes the room ahead expected: full light
  at once. Occupancy does not change without proof; if nobody turns up, the
  light fades out after 20 s.

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
