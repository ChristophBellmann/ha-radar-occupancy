# Background and measurements

The logic comes from a home with seven LD2450 sensors on two floors and was
tuned against recorded history.

## The door range

In an office with the desk 0.2 to 1.3 m from the sensor and the door at
5.4 m, real exits disappeared at 4.7 to 7.6 m, losses at the desk at 0.15 to
2.3 m. A plain "presence off for 15 s" rule switched off 33 times in that
period, nine of them on somebody sitting at the desk. The door range rule,
replayed against the same history, switched off 24 times, none of them at the
desk, and missed no exit.

## Why lights came late, and what changed

Measured in the history: radar presence → room occupied after about 1.2 s,
in single cases 4–6 s, then a 3 s fade-in. Causes:

1. ESPHome publishes LD2450 coordinates about once per second (median
   1.07 s between two values).
2. A new target must be confirmed for 1 s, in practice until the second
   value.
3. Blind corners in front of doors: the hall sensor at one end of a long
   corridor does not see in front of the bathroom, kitchen and living room
   doors. People coming out were handed to the hall only after the track
   ended (2 s) plus 2 s for unseen passages; kitchen → hall measured 5.8 s.
4. The radar of the room being left often sees 20–80 cm through the door and
   kept those points in its own room.

Fixes, measured in the realistic simulation (0.3.13): room changes
recognised as soon as the old room's radar sees the person beyond the door
(0.3.14), expected arrival behind blind doors (0.3.14), full light where the
next room's radar sees the person coming (0.3.17). Results are on
[measure the light delay](measuring-latency.md).

Rejected: confirming the first target at a door without waiting. It only
helped in its risky form — a ceiling radar that sees into the neighbouring
room's entrance would count echoes there as people.

## Versions

Every change with its reasoning is in the
[changelog](https://github.com/ChristophBellmann/ha-radar-occupancy/blob/main/CHANGELOG.md);
releases are on
[GitHub](https://github.com/ChristophBellmann/ha-radar-occupancy/releases).

## Roadmap

- Map sources of other robot vacuum integrations.
- More card languages (texts live in one table in the card).
