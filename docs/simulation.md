# Simulate a walk

The simulation walks virtual people over your calibrated map and runs them
through the same tracking and light logic as real radar targets. Real
sensors, lights and stored occupancy stay unchanged unless you ask for a live
light test.

Requirements: a *Home* entry, calibrated rooms and loaded maps.

## On the position card

- **Simulate walk** starts automatic walks with the current settings; the
  selected room is the first person's preferred start.
- **Simulation** opens the path editor. **Generate paths automatically** is
  enabled by default: choose **People** (1–8) and **Duration**, then start.
  Each person gets different starting positions, destinations, speeds and
  pauses. Paths follow known doors and calibrated outlines, including concave
  rooms; disconnected floors get separate walkers, no stair connection is
  invented.
- For manual paths disable automatic generation, select a person, **Draw path
  on map** and tap waypoints along the rooms and doors. **Wait 10 s** repeats
  the last position; **Lose target · 60 s** creates a radar dropout.
- **Control real lights** lets the simulated people switch your real lamps,
  with brightness, fades and run-on. Normal radar light control pauses during
  the test; the light automation master switch must be on, and switching it
  off stops the test.

**Stop**, the end of the longest path, unloading the integration or a regular
shutdown end the session and **restore** the previous light states and
brightnesses. Light changes you make by hand during the test are kept.

The card's buttons ignore darkness and time windows, but respect rooms whose
automatic light is off.

## Realistic radars

Simulated radars behave like the real ones:

| Parameter | Default | |
| --- | --- | --- |
| `sensor_interval` | 1 s | seconds between two reports; in between the last coordinates stay (ESPHome LD2450 rate). 0 = every step |
| `field_of_view` | on | a sensor sees only its field of view (7 m, ±60°), its own room and the threshold of its doors |
| `see_through_doors` | on | also along a line of sight through an open doorway; off is the cautious bound for closed or angled doors |

Corners no sensor sees, such as the area in front of a bathroom door, stay
blind in the simulation as well. `sensor_interval: 0` with
`field_of_view: false` is the ideal sensor of versions before 0.3.13.

## Actions

### Animated, in real time

```yaml
action: radar_occupancy.start_simulation
data:
  automatic: true
  count: 3
  duration: 180
  live_lights: true
  ignore_restrictions: true
```

Own routes:

```yaml
action: radar_occupancy.start_simulation
data:
  live_lights: true
  ignore_restrictions: true
  persons:
    - id: Person 1
      route:
        - room: binary_sensor.example_room_occupancy
          x: 2000
          y: 3000
          seconds: 5
        - room: binary_sensor.example_hall_occupancy
          x: 5000
          y: 1000
          seconds: 8
        - seconds: 60          # no room: radar dropout
    - id: Person 2
      route:
        - room: binary_sensor.example_room_occupancy
          x: 3500
          y: 3000
          seconds: 60
```

Stop with `radar_occupancy.stop_simulation`.

- Coordinates are **map millimetres** (before display rotation), not radar
  millimetres or screen pixels. Room entry IDs or occupancy entity IDs are
  accepted.
- `seconds` is the time to reach a waypoint from the previous one; the first
  waypoint is a stationary start. A repeated position is a pause.
- At most eight people, 30 waypoints each, 0.5–120 s per waypoint; automatic
  walks 30–900 s. `seed` repeats automatic walks with the same maps; `room`
  sets the first person's start.
- Paths do not avoid walls by themselves; place waypoints along the actual
  doors and corridors. Observations closer than the tracker's resolution may
  merge, like real targets.

### Instant dry run

`radar_occupancy.simulate` runs one route at once on a virtual clock and
returns `timeline`, `commands` and `unavailable_lights`:

```yaml
action: radar_occupancy.simulate
data:
  ignore_restrictions: true
  held: false          # true: one virtual held person in every mapped room
  route:
    - room: binary_sensor.example_room_occupancy
      x: 2000
      y: 3000
      seconds: 4
    - seconds: 5       # radar loses someone sitting still
    - room: binary_sensor.example_room_occupancy
      x: 3000
      y: 2000
      seconds: 2
response_variable: walk_report
```

It tests decisions and reports fade intentions, not radio coverage, lamp
acknowledgement, real fade timing or network delays.

To measure how fast lights come on, see
[measure the light delay](measuring-latency.md).
