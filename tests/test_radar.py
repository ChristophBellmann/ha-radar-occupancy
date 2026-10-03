"""Entity suggestions from a radar device."""

from custom_components.radar_occupancy.const import (
    CONF_DISTANCE,
    CONF_PRESENCE,
    CONF_X,
    CONF_X2,
    CONF_X3,
    CONF_Y,
    CONF_Y2,
    CONF_Y3,
)
from custom_components.radar_occupancy.radar import Candidate, suggest


def ld2450(prefix: str, target: str, presence: str, distance: str) -> list[Candidate]:
    entities = [
        Candidate(f"binary_sensor.{prefix}_{presence}", presence, "occupancy"),
        Candidate(f"binary_sensor.{prefix}_zone_1_{presence}", f"zone 1 {presence}", "occupancy"),
        Candidate(f"binary_sensor.{prefix}_moving_target", "moving target", "motion"),
    ]
    for n in (1, 2, 3):
        for axis in ("x", "y", "speed", distance):
            entities.append(Candidate(f"sensor.{prefix}_{target}_{n}_{axis}", f"{target} {n} {axis}"))
    return entities


def test_esphome_english_names() -> None:
    result = suggest(ld2450("office", "target", "presence", "distance"))
    assert result == {
        CONF_PRESENCE: "binary_sensor.office_presence",
        CONF_X: "sensor.office_target_1_x",
        CONF_Y: "sensor.office_target_1_y",
        CONF_DISTANCE: "sensor.office_target_1_distance",
        CONF_X2: "sensor.office_target_2_x",
        CONF_Y2: "sensor.office_target_2_y",
        CONF_X3: "sensor.office_target_3_x",
        CONF_Y3: "sensor.office_target_3_y",
    }


def test_german_names() -> None:
    result = suggest(ld2450("c3_ld2450_1_ld2450", "ziel", "anwesenheit", "entfernung"))
    assert result[CONF_PRESENCE] == "binary_sensor.c3_ld2450_1_ld2450_anwesenheit"
    assert result[CONF_DISTANCE] == "sensor.c3_ld2450_1_ld2450_ziel_1_entfernung"
    assert result[CONF_Y3] == "sensor.c3_ld2450_1_ld2450_ziel_3_y"


def test_names_with_dashes_and_disabled_entities() -> None:
    entities = [
        Candidate("binary_sensor.radar_has_target", "Has Target", "presence"),
        Candidate("sensor.radar_target_1_x", "Target-1 X", disabled=True),
        Candidate("sensor.radar_t1x", "Target-1 X"),
        Candidate("sensor.radar_target_1_distance", "Target-1 Distance"),
    ]
    result = suggest(entities)
    assert result == {
        CONF_PRESENCE: "binary_sensor.radar_has_target",
        CONF_X: "sensor.radar_t1x",
        CONF_DISTANCE: "sensor.radar_target_1_distance",
    }


def test_nothing_to_suggest() -> None:
    assert suggest([Candidate("sensor.temperature", "Temperature", "temperature")]) == {}
