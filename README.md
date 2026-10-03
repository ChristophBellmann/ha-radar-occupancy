# Radar Occupancy

Room occupancy for Home Assistant from mmWave radar sensors (HLK-LD2450 and
similar) that **does not switch the light off on people who sit still**.

[Deutsch weiter unten](#deutsch)

## The problem

Radar presence sensors lose people who sit or lie still. An automation that
clears the room when presence drops therefore turns the light off at the desk,
on the sofa or in bed, and back on at the next movement. Longer timeouts only
move the problem.

## The idea

A room is a latch. Radar presence sets it; only **evidence of leaving** clears
it:

| Evidence | Meaning |
| --- | --- |
| **Left through the door** | The target disappeared within the configured *door range*, the distance from the sensor at which people walk out. |
| **Handed over** | Another room took the person over (optional, single-person households). |
| **Safety timeout** | Nobody was seen for a configurable time (or never, if set to 0). |
| **Released** | Pressed the *Release* button, or switched *Hold occupancy* off. |

If the target disappears anywhere else, for example at the desk 1 m from the
sensor, the room stays occupied.

**Sub-areas** cover parts of a room seen by the same sensor, such as a balcony
behind the room. Disappearing there is never leaving, even inside the door
range, and a sub-area can switch its own light.

## Installation

HACS → ⋮ → *Custom repositories* → `https://github.com/ChristophBellmann/ha-radar-occupancy`,
category *Integration*. Install *Radar Occupancy* and restart Home Assistant.

Manually: copy `custom_components/radar_occupancy` into your `config/custom_components`.

## Setup

*Settings → Devices & services → Add integration → Radar Occupancy → Room*:

- **Presence**: the radar's presence binary sensor.
- **Distance of target 1** (recommended): needed for the door range, e.g. the
  target 1 distance sensor of ESPHome's `ld2450` component.
- **X / Y of target 1** (optional): needed for sub-areas.
- **Light** (optional).

Then open the room's *Configure* dialog for door range, safety timeout,
handover, brightness, run-on time and time window.

### Calibrating the door range

1. Walk into the room and out through the door at normal speed.
2. Press **Learn door from last exit** on the room's device page.

The door range then starts 50 cm before the point where the radar lost you.
*Last seen distance* shows the value; you can also set the range by hand.
A door range of 0 to 0 (default) means every disappearance counts as leaving,
i.e. plain presence behaviour.

### Handover (single-person households)

Rooms that take part in handover release each other: if a room lost its target
near the door at least 20 s ago and another taking-part room sees someone, the
first room is free. *Hand over even when lost away from the door* helps where
two rooms connect at a spot the sensor cannot tell from the inside. *Take over
only from this distance* ignores fixed echoes close to a sensor, such as a door
leaf.

With visitors, a room can be released while someone is still in it. Leave
handover off unless one person lives in the home.

## Light control

With a light configured:

- **Entering** an empty room switches the light on (brightness, *Only when
  dark* via `sun.sun`, time window). *Last brightness set by hand* fades to
  the brightness you chose last instead of the fixed one.
- **Leaving**: after the run-on time the light is switched off — also a light
  that was on before someone entered, because whoever entered owns it.
  A light switched on while nobody entered stays on.
- **Switched off by hand** in an occupied room: the light stays off, also
  after leaving briefly (to the bathroom at night and back). Switching it on
  by hand gives it back to the automation; with a home entry it also ends
  after the room was empty for 30 minutes (configurable). Changes by other
  automations do not count as "by hand".
- Rooms sharing a light keep it on while any of them is occupied.
- With a home entry, lights **fade** in and out in perceptually even steps
  (CIE L*), at most one command per lamp in flight, so slow cloud lamps get
  no backlog; lamps with native transitions get one command. Fading out never
  switches on a lamp of a group that is already off.
- Lamps that are unreachable drop commands silently. The light is switched off
  up to three times and checked again every five minutes, also after a restart,
  until it really reports off.

## Map mode (optional): people counted through doors

Add *Home* once (*Add integration → Radar Occupancy → Home*). It brings

| Entity | |
| --- | --- |
| `switch.<home>_light_automation` | Master switch for all lights |
| `switch.<home>_map_mode` | Off: every room uses its distance rule |
| `number.<home>_fade_in`, `number.<home>_fade_out` | Fade times, 0 = switch |
| `sensor.<home>_overview` | People in the home; attributes feed the position card |

Map mode places every radar target on the saved map of a robot vacuum
([dreame_vacuum](https://github.com/Tasshack/dreame-vacuum) cameras), fuses
the targets of all sensors and counts **people per room**. A room becomes free
only when everybody evidently walked out through a door. Somebody seen in
another room says nothing about this room, so it works with several people.

Per room (*Configure*): *Robot map* (camera), *Room on the map* (segment),
*Doors to these map rooms* (only real doors; empty = every adjacent segment),
and X/Y of targets 2 and 3. Map segments without a radar count as outside.
Exits the map does not show (stairs, front door) are marked on the card.

Then calibrate each sensor on the **position card**
(`type: custom:radar-occupancy-card`, loaded automatically; its texts are
German only for now): place it on the
map and turn its field of view until your dot appears where you stand (wall),
or take three or more samples (ceiling). Distorted calibrations are detected;
such rooms keep their distance rule. Walking towards a door pre-lights the
room behind it.

Services: `sample`, `undo_sample`, `sample_area`, `set_location`,
`set_orientation`, `set_boundary`, `reset_calibration`, `set_calibration`
(backup/import), `set_exit`, `set_floor`, `refresh_maps`, `release`.

## Entities per room

| Entity | |
| --- | --- |
| `binary_sensor.<room>` | Occupancy; attributes `reason`, `mode` (`map`/`distance`), `people` (map mode), `last_distance`, `last_x`, `last_y`, `light_owned`, `light_mode` |
| `sensor.<room>_last_seen_distance` | Where the radar last saw a target |
| `switch.<room>_hold_occupancy` | Off: the room follows live presence only |
| `switch.<room>_automatic_light`, `switch.<room>_only_when_dark` | If a light is configured |
| `button.<room>_release` | Clear a held occupancy (refused while a target is present) |
| `button.<room>_learn_door_from_last_exit` | See calibration |

`reason` is one of `present`, `held`, `in_area`, `left_through_door`,
`handed_over`, `safety_timeout`, `released`, `live`, `unavailable`, `empty`.
A sensor that goes offline keeps the last decision.

## Background

The logic comes from a home with seven LD2450 sensors and was tuned against
recorded history. In an office with the desk 0.2 to 1.3 m from the sensor and
the door at 5.4 m, real exits disappeared at 4.7 to 7.6 m, and losses at the
desk at 0.15 to 2.3 m. A plain "presence off for 15 s" rule switched off 33
times in that period, nine of them on someone sitting at the desk; the door
range rule, replayed against the same history, switched off 24 times, none of
them at the desk, and missed no exit.

## Roadmap

- Floor plans from images, not only robot vacuum maps.
- Several homes / floors without a robot.

## Compatibility

Tested with Home Assistant 2026.2 and 2026.9. Any radar works that provides a presence
binary sensor and, for the door range, a distance sensor in millimetres.

## Development

```bash
pip install -r requirements_test.txt
pytest
```

`engine.py` holds the occupancy logic without Home Assistant imports.

## License

Apache-2.0

---

## Deutsch

Raumbelegung aus mmWave-Radarsensoren (z. B. HLK-LD2450), die **das Licht
nicht ausschaltet, wenn jemand still sitzt**.

Ein Raum wird durch Radar-Anwesenheit belegt und nur durch einen Nachweis
wieder frei: Das Ziel verschwand im **Türbereich**, ein anderer Raum hat die
Person **übernommen** (nur Einpersonenhaushalt), die **Sicherheitsabschaltung**
griff, oder jemand hat **freigegeben**. Verschwindet das Ziel woanders, etwa am
Schreibtisch, bleibt der Raum belegt. **Teilbereiche** (z. B. ein Balkon, den
der Raumsensor mit sieht) zählen nie als Verlassen und können ein eigenes
Licht schalten.

**Türbereich einmessen:** normal durch die Tür hinausgehen, danach
**Türbereich vom letzten Verlassen lernen** drücken. Der Bereich beginnt dann
50 cm vor der Stelle, an der das Radar dich verloren hat.

**Kartenmodus** (optional, Eintrag „Wohnung“): Radarziele auf der
Roboterkarte, Personen je Raum über Türen gezählt, mehrpersonentauglich.
Licht: von Hand ausgeschaltet bleibt aus (auch nach kurzem Verlassen),
weiches Ein- und Ausblenden, Vorblenden bei Annäherung. Eingemessen wird in
der Positionskarte `custom:radar-occupancy-card`.

Einrichtung und Entitäten sind auf Deutsch und Englisch übersetzt; die
Positionskarte gibt es bisher nur auf Deutsch.
