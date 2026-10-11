# Rooms and the door range

## Add a room

*Settings → Devices & services → Add integration → Radar Occupancy → Room
with a radar sensor*.

1. Choose the **radar device** of the room. The room name defaults to the
   device's area. Without a device you pick the sensors yourself.
2. Pick the **light** of the room (optional, can be added later).
3. Check the suggested sensors:

| Input | Needed for |
| --- | --- |
| **Presence** (required) | setting the room occupied |
| **Distance of target 1** (recommended) | the door range |
| **X / Y of target 1** | sub-areas |
| **X / Y of targets 2 and 3** | map mode |

The room's *Configure* dialog holds everything else: door range, safety
timeout, handover, light, brightness, run-on time, time window and the map
settings.

## How the room decides

| Evidence | Clears the room |
| --- | --- |
| **Left through the door** | the target disappeared within the door range |
| **Handed over** | another room took the person over (optional, see [handover](sub-areas-and-handover.md)) |
| **Safety timeout** | nobody was seen for the configured time (default 30 min, 0 = never) |
| **Released** | *Release* pressed, or *Hold occupancy* switched off |

A target that disappears anywhere else keeps the room occupied. That is the
whole trick: radar loses still people, but it loses them where they sit, not
at the door.

## Calibrate the door range

1. Walk into the room and out through the door at normal speed.
2. Press **Learn door from last exit** on the room's device page.

The door range then starts 50 cm before the point where the radar lost you.
`sensor.<room>_last_seen_distance` shows where the radar last saw a target;
you can also set *Door range from / to* by hand (0 as upper limit = no limit).

A door range of 0 to 0 (the default) means every disappearance counts as
leaving: plain presence behaviour, useful to start with.

Check after a day: the `reason` attribute of `binary_sensor.<room>` says why
the room was freed. `left_through_door` while somebody was still sitting
means the range starts too close to the sensor; a room that stays `held` after
everybody left means it starts too far.

## Options of a room

| Option | Default | |
| --- | --- | --- |
| Door range from / to | 0 / 0 mm | where vanishing counts as leaving |
| Release after no presence for | 30 min | safety timeout, 0 = never |
| Take part in handover | off | single-person homes |
| Hand over even when lost away from the door | off | see handover |
| Take over only from this distance | 0 mm | ignore fixed echoes close to the sensor |
| Light | — | see [light control](light-control.md) |
| Brightness | 100 % | |
| Switch off after | 60 s | run-on after the room became free |
| Time window from / to | 00:00 / 00:00 | same value = always |
| Last brightness set by hand | off | fade to the brightness you chose last |
| Map, room on the map, doors | — | see [map mode](map-mode.md) |

## Switches and buttons per room

- `switch.<room>_hold_occupancy`: off makes the room follow live presence
  only (no latch).
- `button.<room>_release`: clears a held occupancy; refused while a target is
  present.
- `button.<room>_learn_door_from_last_exit`: see above.
- With a light: `switch.<room>_automatic_light` and
  `switch.<room>_only_when_dark`.

A sensor that goes offline keeps the last decision (`reason: unavailable`
while it is gone).
