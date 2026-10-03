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
        attrs: dict[str, Any] = {"light_owned": self.target.owned}
        if isinstance(self.target, RoomTarget):
            room = self.target.room
            attrs.update(
                reason=room.reason,
                last_distance=room.last_distance,
                last_x=room.last_x,
                last_y=room.last_y,
            )
        return attrs
