"""Last seen distance per room; overview of the home for the position card."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import RadarOccupancyEntity
from .home import Home


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    if isinstance(entry.runtime_data, Home):
        add([OverviewSensor(entry.runtime_data, "overview")])
    else:
        add([LastDistanceSensor(entry.runtime_data, "last_distance")])


class LastDistanceSensor(RadarOccupancyEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> float | None:
        return self.target.room.last_distance


class OverviewSensor(RadarOccupancyEntity, SensorEntity):
    """People in the home; the attributes feed the position card.

    Attributes change several times a second and hold the map geometry, so
    none of them is recorded."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "people"
    _unrecorded_attributes = frozenset(
        {
            "simulation",
            "map_mode",
            "light_automation",
            "max_people",
            "fade_in",
            "fade_out",
            "entities",
            "floors",
            "sensors",
            "targets",
            "people",
            "tracks",
            "doors",
            "events",
            "lights",
        }
    )

    @property
    def native_value(self) -> int:
        return self.target.total_people()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.target.snapshot()
