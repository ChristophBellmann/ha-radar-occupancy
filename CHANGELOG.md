# Changelog

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
