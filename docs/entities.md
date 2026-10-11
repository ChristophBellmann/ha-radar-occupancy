# Entities

Entity IDs follow your entry names; `<room>` and `<home>` stand for them.

## Per room and sub-area

| Entity | |
| --- | --- |
| `binary_sensor.<room>` | occupancy (device class *occupancy*) |
| `sensor.<room>_last_seen_distance` | where the radar last saw a target (rooms) |
| `switch.<room>_hold_occupancy` | off: the room follows live presence only (rooms) |
| `switch.<room>_automatic_light` | light automation of this room (with a light) |
| `switch.<room>_only_when_dark` | only when `sun.sun` is below the horizon (with a light) |
| `button.<room>_release` | clear a held occupancy; refused while a target is present |
| `button.<room>_learn_door_from_last_exit` | set the door range from the last exit |

### Attributes of the occupancy sensor

| Attribute | |
| --- | --- |
| `reason` | why the room is in its state, see [reason codes](reasons.md) |
| `mode` | `map` or `distance` |
| `people` | map mode: people counted in the room |
| `reason_from`, `reason_to` | map mode: rooms of the last move (`outside` = outside the home) |
| `last_distance`, `last_x`, `last_y` | last radar values of target 1 |
| `light_owned` | the integration switched the light on and will switch it off |
| `light_mode` | `auto` or `manual_off` (switched off by hand) |

## Home

| Entity | |
| --- | --- |
| `switch.<home>_light_automation` | master switch for all lights |
| `switch.<home>_map_mode` | off: every room uses its distance rule |
| `switch.<home>_handover_between_rooms` | handover in the distance rule |
| `number.<home>_fade_in` | fade-in time in seconds, 0 = switch |
| `number.<home>_fade_out` | fade-out time in seconds, 0 = switch |
| `number.<home>_people_in_the_home_at_most` | household limit, default 2, 0 = none |
| `sensor.<home>_overview` | people currently detected in the home; attributes feed the card |

## Automations

Use the occupancy sensor and its `reason`, not the radar's presence, for
anything that should survive people sitting still. Example: switch the TV off
when the living room was left through the door, but not after a safety
timeout:

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.living_room
    to: "off"
conditions:
  - condition: template
    value_template: >
      {{ state_attr('binary_sensor.living_room', 'reason')
         in ['left_through_door', 'moved', 'went_out'] }}
actions:
  - action: media_player.turn_off
    target:
      entity_id: media_player.tv
```
