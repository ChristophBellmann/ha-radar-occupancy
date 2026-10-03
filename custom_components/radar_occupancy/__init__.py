"""Radar Occupancy: room occupancy from radar targets that survives sitting still."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_KIND, DOMAIN, KIND_AREA
from .manager import RadarOccupancyManager

ROOM_PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]
AREA_PLATFORMS = [Platform.BINARY_SENSOR, Platform.SWITCH]


def _platforms(entry: ConfigEntry) -> list[Platform]:
    return AREA_PLATFORMS if entry.data.get(CONF_KIND) == KIND_AREA else ROOM_PLATFORMS


def get_manager(hass: HomeAssistant) -> RadarOccupancyManager:
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = RadarOccupancyManager(hass)
    return hass.data[DOMAIN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    manager = get_manager(hass)
    entry.runtime_data = await manager.async_add(entry)
    await hass.config_entries.async_forward_entry_setups(entry, _platforms(entry))
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    manager.evaluate()
    return True


async def _options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, _platforms(entry))
    if unloaded:
        manager = get_manager(hass)
        manager.save()
        await manager.async_remove(entry.entry_id)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await get_manager(hass).async_forget(entry.entry_id)
