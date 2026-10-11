# Measure the light delay

`radar_occupancy.measure_simulation` runs the same walks as the animated
simulation **at once** on a virtual clock, with virtual lights only, and
returns when each light was decided.

```yaml
action: radar_occupancy.measure_simulation
data:
  automatic: true
  count: 2
  duration: 600
  seed: 7
  ignore_restrictions: true
  sensor_interval: 1
  field_of_view: true
  see_through_doors: true
response_variable: result
```

`result.latency` holds one entry per time a person **really entered** a room
with a light:

| Field | |
| --- | --- |
| `person` | id of the simulated person |
| `room` | room name |
| `time` | seconds from the start of the walk |
| `prelit` | seconds after entering when the dim pre-light was decided |
| `lit` | seconds after entering when full light was decided (negative: before) |
| `already_on` | the light was already on for somebody else |

`null` means no such decision within 15 s of this entering (and
before the next entering of a room with the same light). Device
latency and the fade come on top.

## Reading the results

- Compare runs with the same `seed`: a change of settings or calibration then
  shows directly.
- Run once with `see_through_doors: false` for the cautious bound (closed or
  angled doors).
- Entries with `lit: null` are rooms entered in darkness — look at the door
  between the two rooms: is it marked, does a sensor see it?
- Many decisions without entering show up as switch-ons in the timeline; that
  is the price of the pre-light.

## Example: a two-floor flat with seven LD2450

Eight random walks with two people over ten minutes each, 582 room
enterings, radars at 1 s (first number with sight through doors, second
without):

| | 0.3.12 | 0.3.14 |
| --- | --- | --- |
| light after entering, median | 1.75 / 1.25 s | 1.00 / 0.75 s |
| mean | 1.66 / 1.93 s | 1.00 / 0.88 s |
| worst case | 14 / 7 s | 3.75 s |
| enterings without light | 11 / 39 | 1 / 1 |

With 0.3.17 (full light before entering where the next room's radar sees the
person) the mean dropped to 0.53 s; the bathroom, whose sensor looks into the
hall, lights 0.75 s before entering. On the real installation the same walk
measured −0.5 s.
