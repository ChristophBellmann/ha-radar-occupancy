# Map mode: people counted through doors

The distance rule works per room. With several people at home it cannot
tell "the person left" from "one of two people left". Map mode places every
radar target on a map of the floor, fuses the targets of all sensors and
counts **people per room**.

A room becomes free only when everybody **evidently walked out through a
door**. Somebody seen in another room says nothing about this room, so it
works with several people.

## Setup

1. Add *Home* once (*Add integration → Radar Occupancy → Home*).
2. Provide a map per floor: the saved map of a robot vacuum or a floor plan
   image, see [maps](maps.md).
3. In every room's options choose the *Map*, the *Room on the map* (robot
   maps) and the *Doors to these map rooms*, and add X/Y of targets 2 and 3.
4. Calibrate every sensor on the [position card](calibration.md).

Rooms whose calibration is missing or distorted keep their distance rule
(`mode: distance`); calibrated rooms report `mode: map`.

## Entities of the home

| Entity | |
| --- | --- |
| `switch.<home>_light_automation` | master switch for all lights |
| `switch.<home>_map_mode` | off: every room uses its distance rule |
| `switch.<home>_handover_between_rooms` | off while guests are here: no handover in the distance rule |
| `number.<home>_fade_in`, `number.<home>_fade_out` | fade times in seconds, 0 = switch |
| `number.<home>_people_in_the_home_at_most` | household limit, default 2, 0 = no limit |
| `sensor.<home>_overview` | people in the home; attributes feed the position card |

Options of the home: *Switched off by hand ends after the room was empty for*
(default 30 min) and *Pre-light when approaching the door* (default 30 %).

## Household limit

Every departure the sensors miss leaves a held place behind. *People in the
home at most* bounds the counts: above the limit, the held place nobody is
visible in goes first — the room somebody just vanished from, otherwise the
one confirmed longest ago (`reason: household_limit`). Raise it while visitors
are here.

## Counted and held

Room tiles on the card show **confirmed, simultaneously visible** people.
**Held occupancy** is shown separately: after a radar dropout nobody knows how
many people are still in the room. The overview sensor counts only currently
detected people; lights still respect held occupancy. Repeated appearances
without a confirmed door passage do not add people.

## Exits

Stairs and the front door are **exits** (marked on the card). Somebody
leaving through an exit goes `outside` (`reason: went_out`); somebody
appearing at an exit `came_in`. Map rooms without a radar also count as
outside.

## Leaving needs evidence

A target disappearing near a door is not enough. One of these must hold:

- the measured track crossed the room outline **at the doorway**;
- a matching target appeared on the other side of the door within 8 s;
- the radar of the room being left sees the person clearly beyond the
  doorway (at least 20 cm into the next room, crossing measured at the door).

An unseen room behind a door requires the measured crossing; otherwise
occupancy stays held. Uncertain positions within 0.8 m of the measuring
sensor's room outline keep that room. Calibration and door positions still
decide the accuracy.

How these rules work in detail: [how tracking decides](how-tracking-works.md).
