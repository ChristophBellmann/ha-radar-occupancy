# Changelog

## 0.3.0

- **Floor plans**: a PNG or JPEG of a floor (below `www`) plus its real width
  is a map for map mode. No robot vacuum needed. Room outlines are drawn and
  doors marked on the position card.
- New service `set_door` and card tool *Mark door*: a door to another room or
  outside, at a map point.
- Position card in English and German, following the Home Assistant language.
- Calibration errors are translated (English, German).
- Diagnostics download for every entry.
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
