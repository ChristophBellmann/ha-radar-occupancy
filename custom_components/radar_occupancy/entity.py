"""Base entity: one device per room or sub-area."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_UPDATE
from .manager import Target


class RadarOccupancyEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, target: Target, key: str) -> None:
        self.target = target
        self._attr_translation_key = key
        self._attr_unique_id = f"{target.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, target.entry_id)},
            name=target.entry.title,
            manufacturer="Radar Occupancy",
            model="Area" if target.entry.data.get("kind") == "area" else "Room",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATE.format(self.target.entry_id), self.async_write_ha_state)
        )

    @property
    def manager(self):
        return self.hass.data[DOMAIN]
