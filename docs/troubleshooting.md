# Troubleshooting

## The room stays occupied after everybody left

- Look at `reason`. `held` with the distance rule: the target vanished
  outside the door range. Walk out once and press **Learn door from last
  exit**, or widen the range by hand.
- Map mode: the passage was not measured. Is the door marked where people
  really walk through? Does a sensor see the doorway? Check the dot on the
  card while you walk out.
- Clear it now: press the room tile on the card for a second, or
  `button.<room>_release`.

## The light goes off while I sit still

- `left_through_door`: the door range starts too close to the sensor; learn it
  again or raise *Door range from*.
- `safety_timeout`: raise the timeout or set it to 0.
- `handed_over`: handover is on and somebody else was seen elsewhere; switch
  handover off with guests, or use map mode.

## The light comes on although I switched it off

Version 0.3.16 or newer keeps it off. Check `light_mode`: `manual_off` is
right. If it is `auto`, the off command did not reach Home Assistant as a
`light.turn_off` call (some wall switches only change the lamp); switching
off again in the app or by voice sets it.

## The light comes late

- Fade-in time (`number.<home>_fade_in`) is part of the felt delay; try 1 s.
- Measure with [`measure_simulation`](measuring-latency.md); rooms with
  `lit: null` need a better marked door or a sensor that sees it.
- Rooms in `mode: distance` light only when their own radar confirms someone.

## Map not available

Robot maps need a saved map in the vacuum app; floor plans a PNG/JPEG below
`www`. Press *Reload maps* on the card. A map that failed to load is retried
every 15 s.

## A room shows `mode: distance` in map mode

Its calibration is missing or distorted. Calibrate it again on the card.

## Bug reports

Download the diagnostics of the home and the room entry (*Settings → Devices
& services → Radar Occupancy → ⋮ at the entry → Download diagnostics*) and
attach them to an
[issue](https://github.com/ChristophBellmann/ha-radar-occupancy/issues). They
contain entity IDs, settings and calibration, no images.
