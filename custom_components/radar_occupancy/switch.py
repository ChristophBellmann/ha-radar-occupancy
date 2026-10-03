"""Runtime switches: automatic light, only when dark, hold occupancy."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import RadarOccupancyEntity
from .home import Home
from .manager import RoomTarget, Target


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    target: Target | Home = entry.runtime_data
    if isinstance(target, Home):
        add([HomeSwitch(target, "light_automation"), HomeSwitch(target, "map_mode"), HomeSwitch(target, "handover")])
        return
    entities: list[SwitchEntity] = []
    if target.light:
        entities += [FlagSwitch(target, "auto_light"), FlagSwitch(target, "only_dark")]
    if isinstance(target, RoomTarget):
        entities.append(HoldSwitch(target, "hold"))
    add(entities)


class FlagSwitch(RadarOccupancyEntity, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, target: Target, key: str) -> None:
        super().__init__(target, key)
        self._key = key

    @property
    def is_on(self) -> bool:
        return getattr(self.target, self._key)

    async def _set(self, value: bool) -> None:
        setattr(self.target, self._key, value)
        self.manager.notify(self.target)
        self.manager.evaluate()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)


class HoldSwitch(RadarOccupancyEntity, SwitchEntity):
    """Off: the room follows live radar presence only."""

    _attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool:
        return self.target.room.hold

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.target.room.hold = True
        self.manager.notify(self.target)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.target.room.hold = False
        self.manager.notify(self.target)
        self.manager.evaluate()


class HomeSwitch(RadarOccupancyEntity, SwitchEntity):
    """Light automation of the whole home; map mode (off: distance rule only);
    handover between rooms (off with visitors)."""

    def __init__(self, home: Home, key: str) -> None:
        super().__init__(home, key)
        self._key = key

    @property
    def is_on(self) -> bool:
        return getattr(self.target, self._key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.target.set_setting(self._key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.target.set_setting(self._key, False)
