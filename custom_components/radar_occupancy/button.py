"""Buttons: release a held room, learn the door range from the last exit."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DOOR_FROM, CONF_DOOR_TO, DOMAIN, DOOR_LEARN_MARGIN
from .entity import RadarOccupancyEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    target = entry.runtime_data
    add([ReleaseButton(target, "release"), LearnDoorButton(target, "learn_door")])


class ReleaseButton(RadarOccupancyEntity, ButtonEntity):
    async def async_press(self) -> None:
        if not self.target.room.release():
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="target_present")
        if self.manager.home:
            self.manager.home.release(self.target.entry_id)
        self.manager.notify(self.target)
        self.manager.evaluate()


class LearnDoorButton(RadarOccupancyEntity, ButtonEntity):
    """Walk out through the door, then press: the door range starts just
    before the point where the radar lost you."""

    _attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        room = self.target.room
        if room.presence:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="leave_first")
        door_from = room.learn_door(DOOR_LEARN_MARGIN)
        if door_from is None:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="no_distance")
        entry = self.target.entry
        self.hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_DOOR_FROM: door_from, CONF_DOOR_TO: 0}
        )
