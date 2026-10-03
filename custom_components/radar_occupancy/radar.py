"""Suggest the inputs of a room from the entities of a radar device.

Free of Home Assistant imports. Radar firmwares name their entities freely,
e.g. ESPHome's ld2450 component "Target 1 X" or a German configuration
"LD2450 Ziel 1 X"; only the pattern target/ziel + number + axis is relied on.
Every suggestion can be changed in the form that follows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .const import CONF_DISTANCE, CONF_PRESENCE, CONF_X, CONF_X2, CONF_X3, CONF_Y, CONF_Y2, CONF_Y3

TARGET = re.compile(
    r"(?:target|ziel|cible|doel|objetivo|bersaglio)[\s_-]*(\d)[\s_-]*(x|y|distance|entfernung|abstand|dist)\b"
)
PRESENCE_WORDS = ("presence", "anwesenheit", "occupancy", "belegung", "has_target", "target", "ziel")
PRESENCE_CLASSES = ("occupancy", "presence", "motion")
KEYS = {
    (1, "x"): CONF_X,
    (1, "y"): CONF_Y,
    (2, "x"): CONF_X2,
    (2, "y"): CONF_Y2,
    (3, "x"): CONF_X3,
    (3, "y"): CONF_Y3,
}


@dataclass
class Candidate:
    entity_id: str
    name: str  # original or user name, lower case
    device_class: str | None = None
    disabled: bool = False

    @property
    def domain(self) -> str:
        return self.entity_id.split(".", 1)[0]

    @property
    def text(self) -> str:
        return f"{self.entity_id.split('.', 1)[-1]} {self.name}".lower().replace("-", " ")


def suggest(candidates: list[Candidate]) -> dict[str, str]:
    result: dict[str, str] = {}
    enabled = [c for c in candidates if not c.disabled]
    presence = [c for c in enabled if c.domain == "binary_sensor" and c.device_class in PRESENCE_CLASSES]
    if presence:

        def rank(c: Candidate) -> tuple:
            words = [w for w in PRESENCE_WORDS if w in c.text]
            # Zone sensors ("zone 1 presence") cover only part of the field.
            return ("zone" in c.text, -len(words), PRESENCE_CLASSES.index(c.device_class), c.entity_id)

        result[CONF_PRESENCE] = min(presence, key=rank).entity_id
    for c in enabled:
        if c.domain != "sensor":
            continue
        match = TARGET.search(c.text.replace("_", " "))
        if not match:
            continue
        number, axis = int(match.group(1)), match.group(2)
        key = KEYS.get((number, axis)) if axis in ("x", "y") else CONF_DISTANCE if number == 1 else None
        if key and key not in result:
            result[key] = c.entity_id
    return result
