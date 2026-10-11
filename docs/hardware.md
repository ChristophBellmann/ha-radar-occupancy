# Radar hardware (ESPHome)

Any radar works that gives Home Assistant a presence binary sensor. The
door range needs the distance of target 1 in millimetres, map mode the X/Y
coordinates of every target. The logic was developed with the
**HLK-LD2450** (24 GHz, tracks up to three targets with position) on
ESPHome.

## ESPHome configuration for the LD2450

ESPHome's [`ld2450`](https://esphome.io/components/sensor/ld2450.html)
component provides everything. A minimal configuration (adapt the UART pins
to your board; the LD2450 talks at 256000 baud):

```yaml
uart:
  id: ld2450_uart
  tx_pin: GPIO17
  rx_pin: GPIO16
  baud_rate: 256000
  parity: NONE
  stop_bits: 1

ld2450:
  id: ld2450_radar
  uart_id: ld2450_uart

binary_sensor:
  - platform: ld2450
    ld2450_id: ld2450_radar
    has_target:
      name: "Presence"

sensor:
  - platform: ld2450
    ld2450_id: ld2450_radar
    target_1:
      x:
        name: "Target 1 X"
      y:
        name: "Target 1 Y"
      distance:
        name: "Target 1 Distance"
    target_2:
      x:
        name: "Target 2 X"
      y:
        name: "Target 2 Y"
    target_3:
      x:
        name: "Target 3 X"
      y:
        name: "Target 3 Y"
```

When you add a room, the integration suggests these entities from the chosen
device by their names (English and German names such as *Target 1 X* or
*Ziel 1 Entfernung* are recognised).

## Report rate

ESPHome publishes the LD2450 coordinates about **once per second** (default
of the component). The integration is tuned for that: a new target in an
empty room is confirmed after 1 s, i.e. at the second report. A faster rate
(`throttle` of the component) helps only a little — in the simulation the
mean light delay went from 0.89 s to 0.82 s at 250–500 ms — and causes many
more state changes in Home Assistant.

## Mounting

- **Wall**: about 1.5–2 m high, looking into the room. The LD2450 sees about
  ±60° and up to 6–8 m.
- **Ceiling**: possible; calibrate it with three or more calibration points
  on the position card instead of position and orientation.
- Point the sensor so that the **door is in its field of view**. Leaving is
  recognised where the target disappears; a door the sensor cannot see can
  only be handled by the safety timeout or the map.
- A sensor often sees 20–80 cm through an open door. Map mode handles that;
  for the distance rule set the door range so that it ends behind the door.
- Fixed echoes close to the sensor (a door leaf, a fan) can be ignored with
  *Take over only from this distance*; targets closer than 30 cm are always
  treated as echoes.

## Other radars

Sensors without coordinates (for example presence-only radars) work with the
distance rule if they give a distance, otherwise as plain presence with a
safety timeout. Map mode needs coordinates.
