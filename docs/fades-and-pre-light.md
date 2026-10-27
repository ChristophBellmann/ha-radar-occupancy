# Fades and pre-light

Both need the *Home* entry.

## Fades

`number.<home>_fade_in` and `number.<home>_fade_out` set the fade times in
seconds (0 = switch). Fades run in **perceptually even steps** (CIE L*), so
the light does not jump at the dark end.

- At most one command per lamp is in flight. Slow cloud lamps get no backlog;
  unchanged values are skipped.
- Software steps run at up to 20 Hz. Lamps with native transitions get
  interpolated perceptual waypoints at up to 5 Hz, starting dim when the lamp
  was off.
- At most eight light commands run concurrently (cloud integrations have
  small connection pools).
- Fading out never switches on a lamp of a group that is already off.
- Switching off by hand cancels a running fade at once.

A fade-in is part of the felt delay: with 3 s fade the room is fully lit 3 s
after the decision. A short fade (about 1 s) feels much faster. Coming in, a
lamp that was off starts at the pre-light level instead of the darkest step:
the first command, often a slow cloud call, already gives usable light.

## Pre-light

In map mode somebody walking towards a door (within 1.5 m, at least 30 cm
closer, heading at the door, once per walk) pre-lights the room behind it with *Pre-light when approaching the
door* (option of the home, default 30 % of the target brightness).

| Situation | Light |
| --- | --- |
| walking towards a door | pre-light (dim) |
| the next room's own radar sees the person within 1.1 m of its door | full brightness |
| lost at a door no sensor sees behind, after walking towards it | full brightness |
| nobody enters within 20 s | fades out |

Simulated on a two-floor flat: the bathroom light came on 0.75 s **before**
entering instead of 1.1 s after; the mean delay over random walks dropped from
1.0 s to 0.53 s. The price is about 15 % more switch-ons without entering,
for example when somebody walks past an open bathroom door.

The LD2450 cannot see a door opening, only people.
