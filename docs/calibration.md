# Position card and calibration

```yaml
type: custom:radar-occupancy-card
```

The card is registered automatically. It shows every floor with its rooms,
doors and exits, live radar targets, people per room, held occupancy and the
selected sensor's field of view. Texts follow your Home Assistant language
(English or German).

Select a sensor to calibrate it or to see its field of view. Pressing a room
tile for a second releases a held occupancy.

## Calibrate a sensor

For every sensor:

1. **Place sensor** at its mounting point on the map.
2. **Orient sensor**: turn the field of view until your dot appears where you
   stand. Use **Swap left/right** if the dot moves the wrong way.
3. Ceiling sensors instead take three or more **calibration points**: stand
   somewhere, tap where you are on the map, repeat in different corners.
   **Remove last calibration point** undoes one.

Distorted calibrations (points that cannot belong to one rigid sensor pose)
are detected; such rooms keep their distance rule until fixed.

## Outlines, doors and exits

Robot maps bring outlines and doors; correct them if needed. On floor plans:

- **Draw room outline**: tap the corners of the room.
- **Mark door**: choose the room behind it, then tap the door.
- **Mark exit**: stairs or the front door, leading `outside`.
- **Door approach area**: the area in front of a door where walking towards it
  counts for the pre-light. It is derived from the map; **Correct door
  approach area** draws it by hand.

## Check it

Walk through the home with the card open:

- your dot stays inside the room you are in, also in the doorway;
- the count of the room you leave drops when you pass the door;
- the selected sensor's field of view matches what it really sees.

Then let the [simulation](simulation.md) walk your routes.

## Backup and import

`set_calibration` imports a calibration (for example from the diagnostics of
another installation); `reset_calibration` clears a sensor. The diagnostics
download contains the calibration of every room.

The corresponding services are listed under [services](services.md).
