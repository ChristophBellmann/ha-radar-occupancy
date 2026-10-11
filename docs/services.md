# Services

All services are in the `radar_occupancy` domain. `room` accepts a room
entry ID or the room's occupancy entity.

## Calibration and map

| Service | |
| --- | --- |
| `sample` | add a calibration point: you stand at map `x`/`y` (mm) and the room's sensor sees you |
| `undo_sample` | remove the last calibration point |
| `sample_area` | assign a calibration point (1–12) to the `room` or a `sub_area` |
| `set_location` | sensor mounting point in map mm |
| `set_orientation` | `heading` (°), `mirrored`, `mount` (`wall`/`ceiling`), `height` (mm), `clear` |
| `set_boundary` | room outline (`kind: room`) or door approach area (`kind: approach`) as a list of `points` |
| `reset_calibration` | clear the sensor's calibration |
| `set_calibration` | import a calibration object (backup/restore) |
| `set_exit` | exit (stairs, front door) at `x`/`y`, or `clear` |
| `set_door` | door `to` another room (or `outside`) at `x`/`y`, or `clear` |
| `set_floor` | display `name` and `flip` of a floor `camera` |
| `refresh_maps` | reload all maps |
| `release` | clear a held occupancy of `room` |

The position card calls these; you rarely need them by hand.

## Simulation

| Service | Response | |
| --- | --- | --- |
| `simulate` | yes | one route at once on a virtual clock: `timeline`, `commands`, `unavailable_lights` |
| `start_simulation` | no | animated people on the card, optionally with real lights |
| `measure_simulation` | yes | the same walks at once; `latency` per entering |
| `stop_simulation` | no | stop and restore light states |

Fields of `start_simulation` and `measure_simulation`:

| Field | |
| --- | --- |
| `persons` | list of `{id, route}`; waypoints `{room, x, y, seconds}`, no room = dropout |
| `automatic`, `count`, `duration`, `room`, `seed` | generated walks: 1–8 people, 30–900 s |
| `live_lights` | `start_simulation` only: control the real lamps |
| `ignore_restrictions` | ignore darkness and time windows |
| `sensor_interval` | seconds between radar reports (default 1, 0 = ideal) |
| `field_of_view` | sensors see only their field of view and room (default on) |
| `see_through_doors` | sight through open doorways (default on) |

Examples: [simulate a walk](simulation.md), [measure the light delay](measuring-latency.md).
