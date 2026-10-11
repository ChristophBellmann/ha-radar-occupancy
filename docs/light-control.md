# Light control

Pick a light in the room's (or sub-area's) options. The integration then
owns that light's automatic behaviour; do not let a second automation switch
it on presence.

## Entering

The light comes on when somebody **enters**:

- distance rule: the room becomes occupied;
- map mode: the room's count rises, or somebody comes in through a door while
  the room is still held.

Conditions: *Automatic light* on, *Only when dark* (via `sun.sun`, if
enabled), the time window, and the home's master switch
`switch.<home>_light_automation`.

Moving around inside the room switches nothing. If it gets dark (or the time
window opens) while somebody is in the room, the light comes on when they are
next seen.

*Last brightness set by hand* fades to the brightness you chose last instead
of the fixed brightness.

A switch-on the lamp did not confirm is repeated up to three times.

## Leaving

After the run-on time (*Switch off after*, default 60 s) the light is
switched off — also a light that was on before somebody entered, because
whoever entered owns it. A light switched on while nobody entered (by hand,
for a guest the radar does not see) stays on.

Rooms that share a light keep it on while any of them is occupied.

## Unreachable lamps

Lamps that are unreachable drop commands silently. The light is switched off
up to three times (5 s apart) and checked again every five minutes, also
after a restart, until it really reports off.

## Before you enter

In map mode the integration watches people walking towards doors:

- Walking towards a door **pre-lights** the room behind it (30 % of the target
  brightness by default).
- Where that room's own radar already sees the person coming through its
  door (a bathroom sensor looking into the hall), the light comes on at
  **full brightness** before entering.
- Where no sensor sees behind a door, somebody lost at that door while
  walking towards it gets the room ahead lit at full brightness at once.

Nobody turns up? The light fades out after 20 s. Occupancy itself only moves
with evidence. Details: [fades and pre-light](fades-and-pre-light.md).

## Switched off by hand

A light switched off in an occupied room stays off — see
[switched off by hand](manual-off.md).

## Master switch and per-room switches

| Entity | |
| --- | --- |
| `switch.<home>_light_automation` | all lights of the integration |
| `switch.<room>_automatic_light` | this room's light |
| `switch.<room>_only_when_dark` | only when `sun.sun` is below the horizon |

The occupancy sensor's attributes `light_owned` and `light_mode` (`auto` or
`manual_off`) show the current state of the light controller.
