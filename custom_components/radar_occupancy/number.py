"""Fade times of the home and the number of people living in it."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_RUN_ON, DEFAULTS
from .entity import RadarOccupancyEntity
from .home import Home


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    home = entry.runtime_data
    if not isinstance(home, Home):
        if home.light:
            add([RunOnNumber(home, CONF_RUN_ON)])
        return
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


class RunOnNumber(FadeNumber):
    """Persistent per-room light run-on, in seconds."""

    _attr_native_min_value = 0
    _attr_native_max_value = 3600
    _attr_native_step = 15
    _attr_mode = NumberMode.BOX

    @property
    def native_value(self) -> float:
        return float(self.target.entry.options.get(CONF_RUN_ON, DEFAULTS[CONF_RUN_ON]))

    async def async_set_native_value(self, value: float) -> None:
        self.hass.config_entries.async_update_entry(
            self.target.entry,
            options={**self.target.entry.options, CONF_RUN_ON: float(value)},
        )
