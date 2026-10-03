"""Diagnostics download: what a bug report needs, without images."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_KIND, DOMAIN, KIND_HOME, KIND_PLAN
from .manager import RoomTarget


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    manager = hass.data.get(DOMAIN)
    result: dict[str, Any] = {"kind": entry.data.get(CONF_KIND), "options": dict(entry.options)}
    if manager is None:
        return result
    kind = entry.data.get(CONF_KIND)
    if kind == KIND_HOME and manager.home is not None:
        home = manager.home
        snapshot = home.snapshot()
        result["home"] = {
            "map_mode": snapshot["map_mode"],
            "light_automation": snapshot["light_automation"],
            "floors": snapshot["floors"],
            "map_errors": dict(home.errors),
            "people": snapshot["people"],
            "doors": snapshot["doors"],
            "events": snapshot["events"],
            "lights": snapshot["lights"],
            "calibrations": home.calibrations,
            "exits": home.data.get("exits", {}),
            "marked_doors": home.data.get("doors", {}),
        }
    elif kind == KIND_PLAN and manager.home is not None:
        floor = manager.home.floors.get(f"plan.{entry.entry_id}")
        result["floor"] = {k: v for k, v in (floor or {}).items() if k != "image"}
    else:
        target = manager.target(entry.entry_id)
        if target is not None:
            result["state"] = target.persist()
            result["on_map"] = target.on_map
            if isinstance(target, RoomTarget) and manager.home is not None:
                result["map"] = {k: v for k, v in manager.home.rooms.get(entry.entry_id, {}).items() if k != "targets"}
    return result
