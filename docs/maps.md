# Maps: robot vacuum or floor plan

| Map source | Room outlines | Doors |
| --- | --- | --- |
| Saved map of a robot vacuum ([dreame_vacuum](https://github.com/Tasshack/dreame-vacuum) camera) | from the map | found where map rooms touch |
| **Floor plan image** | drawn on the card | marked on the card |

## Robot vacuum map

The camera entity of a dreame_vacuum map (`camera.<robot>_map`, one per saved
floor) is a map source. In the room options:

- **Map**: the camera of the floor.
- **Room on the map**: the segment that is this room.
- **Doors to these map rooms**: only the segments reachable through a real
  door. Empty = every adjacent segment, which also makes doors out of walls
  that merely touch.

The map needs to be saved in the vacuum app. After a restart the camera can
exist before it serves its map; a map that failed to load is tried again every
15 seconds (or press *Reload maps* on the card / call `refresh_maps`).

`set_floor` gives a floor a display name and can flip it.

## Floor plan image

For homes without a supported robot map.

1. Put a PNG or JPEG of one floor below the `www` folder of your
   configuration, e.g. `config/www/floorplans/ground.png`.
2. *Add integration → Radar Occupancy → Floor plan image*: path below `www`
   (`floorplans/ground.png`) and the **real width of the whole image** in
   metres. Measure one wall shown on the plan and scale it to the full image
   width.
3. Add one entry per floor.
4. On the position card: **Draw room outline** for every room, **Mark door**
   for every door (choose the room behind it, tap the door), **Mark exit** for
   stairs or the front door.

## Several floors

Each floor is its own map; there is no interpolation between maps. Floors are
connected through **exits** (stairs). `floor_order` on the card keeps the
floors in a chosen order:

```yaml
type: custom:radar-occupancy-card
floor_order: [camera.upper_map, camera.lower_map]
```

Use the map-source IDs (`camera.…` or `plan.<entry id>`); other floors follow
afterwards.

Uploaded images stay in your configuration; no map data is part of the
public repository, and diagnostics contain no images.
