"""Fade times of the home and the number of people living in it."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import RadarOccupancyEntity
from .home import Home


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    home: Home = entry.runtime_data
    add([FadeNumber(home, "fade_in"), FadeNumber(home, "fade_out"), PeopleNumber(home, "max_people")])


class FadeNumber(RadarOccupancyEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_max_value = 10
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.SLIDER

    def __init__(self, home: Home, key: str) -> None:
        super().__init__(home, key)
        self._key = key

    @property
    def native_value(self) -> float:
        return getattr(self.target, self._key)

    async def async_set_native_value(self, value: float) -> None:
        self.target.set_setting(self._key, float(value))


class PeopleNumber(FadeNumber):
    """Upper bound for the people counted in the home (0 = no limit).

    Raise it while visitors are here."""

    _attr_native_min_value = 0
    _attr_native_max_value = 20
    _attr_native_step = 1
    _attr_native_unit_of_measurement = None
    _attr_mode = NumberMode.BOX
