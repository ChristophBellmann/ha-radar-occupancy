# Changelog

## 0.3.17

- Walking towards a door while the radar of the room ahead already sees you
  through that door lights the room at full brightness instead of the dim
  pre-light. Simulated on a two-floor flat: the bathroom light comes on 0.75 s
  before entering instead of 1.1 s after; mean delay over random walks 0.53
  instead of 1.0 s, with about 15 % more switch-ons for people walking past an
  open door (they fade out after the pre-light time). Observations now carry
  the reporting sensor.

## 0.3.16

- "Light off" by voice, app or automation right after the light came on for
  entering now counts as switched off by hand. In the seconds after its own
  switch-on the integration took the state report for the echo of its command,
  kept the light automatic and switched it on again at the next entering; a
  fade still running could also pull the lamp up again. The `light.turn_off`
  call itself is now the evidence.
- "Switched off by hand" no longer ends because a room was empty for 30
  minutes unless somebody evidently left it (door, out of the home, release,
  hold off). A sleeper unseen for hours and dropped by the household limit
  made the bedroom "empty"; turning over later switched the light on at night.

## 0.3.15

- A map that failed to load is tried again every 15 seconds. After a restart
  the robot's camera entity can exist before it serves its map ("Camera not
  found"); that floor's rooms then stayed on the distance rule until the map
  changed or `refresh_maps` was called.

## 0.3.14

- Leaving a room is recognised as soon as its own radar sees the person
  clearly beyond the doorway (at least 20 cm into the next room, crossing
  measured at the door). Before, that radar kept calling the target its own
  room until the track ended, about four seconds of darkness next door.
- Somebody lost at a door no sensor sees behind, walking towards it, gets the
  room ahead lit at full brightness at once (simulated: hall 0.9–1.3 s after
  leaving bathroom, kitchen or living room instead of never or five seconds).
  Counts do not move without evidence, so a person still standing at the door
  keeps their room; the light fades out after the pre-light time otherwise.
- Measured on a replica of a two-floor flat (8 random two-person walks of
  ten minutes, simulated LD2450 at 1 s): light after entering 0.75–1.0 s
  median instead of 1.25–1.75 s, at worst 3.75 instead of 14 s; entries
  without light 1 instead of 11–39, fewer switch-ons without anybody entering.

## 0.3.13

- Simulated radars report like real ones: only people in their field of view
  (7 m, ±60°), own room and door thresholds, optionally along a line of sight
  through open doorways (`see_through_doors`), once per `sensor_interval`
  (default 1 s, the LD2450 rate in ESPHome), keeping the last coordinates in
  between. Blind corners such as the area in front of a bathroom door stay
  blind. The model follows five days of recorded LD2450 positions.
- New response action `measure_simulation`: the same walks on a virtual clock,
  returning per room entry how many seconds after entering the light was
  pre-lit and switched on. Simulation snapshots carry the same `latency` list.

## 0.3.12

- Simulated positions use the selected radar's room assignment and the home's
  household limit, matching production tracking instead of using geometry
  alone. This makes missed-passage regressions reproducible in simulation.
- Verified independent five-minute walks on an installation's two floor plans:
  every mapped room is observed and receives its expected light commands.

## 0.3.11

- Software fades use 50 ms steps, skipping repeated brightness values and
  retaining at most one command per lamp in flight.
- Transition-capable lamps interpolate 200 ms waypoints along the same
  perceptual brightness curve. Off lamps first receive a dim starting level
  so remembered brightness cannot cause a bright start. The final device
  transition finishes before an off command is sent.
- Tests cover monotonic native fade-in/out, dark startup, exact final levels
  and bounded command rates alongside the existing software-fade tests.

## 0.3.10

- A receiving radar's confirmed room sighting can no longer keep a nearby
  track assigned to a different room indefinitely when the doorway was missed.
  A new track establishes presence in the receiving room; the previous room
  stays held unless a measured departure or the household limit releases it.
- Regression coverage includes missed passages, wrong-wall projections,
  normal doorway transfers and switching on the receiving room's light.

## 0.3.6

- Map-mode transfers require a measured inside-to-outside crossing at the
  actual doorway, followed by confirmation beyond the outline. Mere proximity
  to a door or movement across a nearby wall no longer frees a room.
- A dropout while still inside near an unseen door holds occupancy. A visible
  receiver can complete a paired passage; an unseen receiver requires a measured
  boundary crossing. Outside exits also require crossing the boundary.
- At uncertain map edges the originating radar retains its own room. Unseen
  doorway handovers do not consume a person still visibly present on the other
  side. Existing manual release remains available for an ambiguous held room.
- Regression tests cover wrong-wall movement, doorway jitter, inside dropouts,
  actual crossings and retained lights. Simulation test paths now pass through
  actual doors instead of cutting diagonally through walls.

## 0.3.5

- Fix additive phantom people after repeated or long radar dropouts at doors.
  Reappearance on the same side cancels pending departures; unpaired target
  appearances no longer add another person. Distinct simultaneous targets
  and confirmed door transfers still support multiple people.
- Room tiles distinguish currently detected people from held occupancy. The
  overview sensor reports currently confirmed visible people, not old held
  estimates. Holding a room still keeps its light occupied.
- One-time migration removes inflated legacy headcounts while preserving each
  occupied room as held. Fresh observations establish multiple people again.

## 0.3.4

- Automatic multi-person walks: choose the number of people and duration,
  then start. Each person gets independent destinations, walking speed and
  pauses. Default animation now needs no manually placed waypoints.
- Paths follow calibrated room outlines and known doors. Visibility paths
  keep walks inside concave rooms; disconnected maps get separate starting
  people without inventing connections through walls or between floors.
- Automatic planning runs in a worker from a configuration snapshot. The card
  displays the generated paths and colored moving people on all floor maps.
- `start_simulation` supports `automatic`, `count`, `duration`, optional
  starting `room` and a repeatable `seed`. Manual paths remain available.

## 0.3.3

- Animated map simulation with up to eight simultaneous people, individual
  colors and paths, interpolated positions, waiting and radar dropouts.
- Draw each person's path directly on the zoomable, rotated floor maps.
  Simulated occupancy and real radar occupancy are displayed separately.
- Optional **Control real lights** takes over mapped light control during
  the session, using the production light controller including fades and
  run-on time. Stop, end of route, disabling the master or unloading an entry
  ends the session and restores previous light states. Normal radar tracking
  continues; simulated counts are never written to real occupancy storage.
- Actions `start_simulation` and `stop_simulation` for automation/API use.
  The instant, virtual `simulate` response action remains available.

## 0.3.2

- Public `radar_occupancy.simulate` response action replays local map waypoints
  through the production tracking and light decision logic in an isolated
  sandbox. Reports a timeline, intended light commands, brightness, fade
  duration and unavailable lights; no real sensor or light states are changed.
- Position card adds **Simulate room** / **Raum simulieren** for an entry and
  sitting-still test. Custom multi-room routes and held starting counts are
  supported through the action. Darkness/time restrictions can be bypassed
  for a simulation without changing the installation settings.

## 0.3.1

- A confirmed live target can switch on an automatic light in a room whose
  occupancy was already held or restored. Held counts alone still do not
  switch lights on; manual-off, darkness and time windows remain respected.
- Arrival from a corridor whose doorway a sensor cannot see consumes that
  corridor's held occupant instead of adding another person on each trip.
- A nearby reappearance after a brief radar dropout reuses the held person,
  including when the target resumes walking before its first confirmation.
- Position cards accept `floor_order` to keep floor maps in a chosen order.

## 0.3.0

- **Floor plans**: a PNG or JPEG of a floor (below `www`) plus its real width
  is a map for map mode. No robot vacuum needed. Room outlines are drawn and
  doors marked on the position card.
- New service `set_door` and card tool *Mark door*: a door to another room or
  outside, at a map point.
- Position card in English and German, following the Home Assistant language.
- Calibration errors are translated (English, German).
- Diagnostics download for every entry.
- Room setup from the radar device: presence, distance and X/Y of all
  targets are suggested, the name from the device's area.
- Home switch *Handover between rooms*, to pause handover while guests are
  here.
- **Breaking** for automations that read the `reason` attribute in map mode: it
  is now a stable code (`moved`, `came_in`, `went_out`, `seen_in_room`,
  `appeared_at_door`, `released`, `hold_off`) with the rooms in `reason_from`
  and `reason_to`, instead of a German sentence. The overview's `events` are
  objects with `code`, `from` and `to`.

## 0.2.0

- Map mode on robot vacuum maps: people counted per room through doors.
- Lights: manual-off memory, perceptual fades, pre-lighting at doors.
- Position card for calibration.

## 0.1.0

- Distance rule: a room is left only through the door range, handover,
  safety timeout or release. Sub-areas, light control with retries.
