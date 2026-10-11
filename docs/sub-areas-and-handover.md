# Sub-areas and handover

## Sub-areas

A sub-area is a part of a room seen by the **same sensor**, such as a balcony
behind the living room, a reading corner or a bed.

*Add integration → Radar Occupancy → Sub-area of a room*: choose the room and
give a rectangle in the **radar coordinates** of the room sensor (X from/to,
Y from/to in mm). The live `last_x` / `last_y` attributes of the room show
where you stand.

- Disappearing inside a sub-area **never** counts as leaving the room, even
  inside the door range.
- A sub-area has its own occupancy sensor and can switch its own light, with
  the same light options as a room.
- In map mode sub-areas use the room sensor's calibration and the radar
  boundaries.

## Handover (single-person homes)

Rooms that take part in handover release each other: if a room lost its
target near the door at least 20 s ago and another taking-part room sees
someone, the first room is free.

- **Hand over even when lost away from the door** helps where two rooms
  connect at a spot the sensor cannot tell from the inside, for example an
  open kitchen.
- **Take over only from this distance** ignores targets of this room's sensor
  that are closer, such as a fixed echo from a door leaf, so they do not
  steal the person from the room they are in.

Handover assumes one person. With visitors a room can be released while
somebody is still in it. Leave it off unless one person lives in the home, or
switch `switch.<home>_handover_between_rooms` off while guests are here
(needs the *Home* entry).

Map mode does not need handover: it counts people per room and never frees a
room because somebody was seen elsewhere.
