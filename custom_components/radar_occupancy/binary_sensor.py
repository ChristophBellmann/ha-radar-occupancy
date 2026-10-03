"""Occupancy binary sensor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import RadarOccupancyEntity
from .manager import RoomTarget


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    add([OccupancySensor(entry.runtime_data, "occupancy")])


class OccupancySensor(RadarOccupancyEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_name = None  # the device name is the room name

    @property
    def is_on(self) -> bool:
        return self.target.occupied

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        target = self.target
        attrs: dict[str, Any] = {"light_owned": target.owned, "mode": "map" if target.on_map else "distance"}
        if target.on_map:
            source, destination = self.manager.home.reason_rooms(target.entry_id)
            attrs.update(people=target.people, reason=target.reason, reason_from=source, reason_to=destination)
        if isinstance(target, RoomTarget):
            room = target.room
            attrs.update(
                reason=target.reason,
                last_distance=room.last_distance,
                last_x=room.last_x,
                last_y=room.last_y,
            )
        if target.light:
            attrs["light_mode"] = self.manager.lights.mode(target.light)
        return attrs
