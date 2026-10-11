# Reason codes

`reason` on `binary_sensor.<room>` is a stable code for automations.

## Distance rule

| Code | State | Meaning |
| --- | --- | --- |
| `present` | on | the radar sees a target |
| `held` | on | no target, but nobody left: the latch holds |
| `in_area` | on | the target was lost inside a sub-area |
| `left_through_door` | off | the target disappeared within the door range |
| `handed_over` | off | another room took the person over |
| `safety_timeout` | off | nobody was seen for the safety timeout |
| `released` | off | *Release* pressed or service `release` |
| `live` | on/off | *Hold occupancy* is off: plain presence |
| `unavailable` | kept | the sensor is offline; the last decision stays |
| `empty` | off | nobody was there since the start |

## Map mode

| Code | Meaning |
| --- | --- |
| `seen_in_room` | somebody visible in the room |
| `moved` | walked from one room to another (`reason_from` → `reason_to`) |
| `came_in` | came from outside the home |
| `appeared_at_door` | appeared at the door to `reason_from`, nobody was seen leaving there |
| `went_out` | left the home |
| `released` | released by hand |
| `hold_off` | no target and *Hold occupancy* off |
| `household_limit` | more people counted than live in the home: a held place was stale |

`outside` in `reason_from` / `reason_to` stands for everything without a
radar: stairs, the front door, unsensed map rooms.
