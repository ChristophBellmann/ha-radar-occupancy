# Installation

## Requirements

- Home Assistant 2025.4 or newer (tested with 2026.2, 2026.9 and 2026.10).
- One radar per room that provides a **presence binary sensor**. For the
  door range also the **distance of target 1** in millimetres; for map mode
  **X and Y of every target**. ESPHome's `ld2450` component provides all of
  them, see [radar hardware](hardware.md).
- Optional: lights as `light.*` entities, `sun.sun` for *Only when dark*,
  a robot vacuum map ([dreame_vacuum](https://github.com/Tasshack/dreame-vacuum))
  or a floor plan image for map mode.

## HACS

1. HACS → ⋮ → *Custom repositories*.
2. Repository `https://github.com/ChristophBellmann/ha-radar-occupancy`,
   category *Integration*.
3. Install *Radar Occupancy*, choose the newest release.
4. Restart Home Assistant.

## Manually

Copy `custom_components/radar_occupancy` from a
[release](https://github.com/ChristophBellmann/ha-radar-occupancy/releases)
into `config/custom_components/` and restart Home Assistant.

## What to add

*Settings → Devices & services → Add integration → Radar Occupancy* offers
four kinds of entries:

| Entry | How many | Purpose |
| --- | --- | --- |
| **Room** | one per radar | occupancy, door range, light — see [rooms](rooms.md) |
| **Sub-area** | any | part of a room seen by the same sensor, e.g. a balcony — see [sub-areas](sub-areas-and-handover.md) |
| **Home** | one | master switch, map mode, fades, people limit, overview for the card — see [map mode](map-mode.md) |
| **Floor plan** | one per floor | an image as map for homes without a robot vacuum map — see [maps](maps.md) |

Start with rooms. *Home* is needed for fades, the "switched off by hand"
reset, the position card and map mode.

## Where your configuration lives

The repository only contains the reusable integration and its card. Your
installation keeps its own data:

- Home Assistant config entries: rooms, radars, lights, map assignments,
  options.
- `config/.storage/radar_occupancy`: calibration, doors, outlines, runtime
  state.
- Floor plan images below `config/www/`.

Updates replace only `config/custom_components/radar_occupancy`; everything
above stays. Back it up together with the rest of your configuration.

## After an update

Restart Home Assistant, wait until it has fully started, then check:

- the room occupancy sensors (`reason`, `mode`),
- the position card (targets in the right rooms),
- that each light is still switched by exactly one controller.

When migrating from another radar automation, move light control room by room
so that one controller owns each light.

## The position card

The card `custom:radar-occupancy-card` is registered automatically; no
resource needs to be added. Put it on any dashboard:

```yaml
type: custom:radar-occupancy-card
```

See [position card and calibration](calibration.md).
