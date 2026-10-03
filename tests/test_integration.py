"""Integration tests against a real Home Assistant test instance."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.radar_occupancy.const import (
    CONF_DISTANCE,
    CONF_DOOR_FROM,
    CONF_HANDOVER,
    CONF_HANDOVER_ANYWHERE,
    CONF_KIND,
    CONF_LIGHT,
    CONF_PARENT,
    CONF_PRESENCE,
    CONF_RUN_ON,
    CONF_SAFETY_TIMEOUT,
    CONF_X,
    CONF_X_MAX,
    CONF_X_MIN,
    CONF_Y,
    CONF_Y_MAX,
    CONF_Y_MIN,
    DEFAULTS,
    DOMAIN,
    KIND_AREA,
    KIND_ROOM,
)


def room_entry(name: str, prefix: str, **options) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title=name,
        data={CONF_KIND: KIND_ROOM},
        options={
            **DEFAULTS,
            CONF_PRESENCE: f"binary_sensor.{prefix}_presence",
            CONF_DISTANCE: f"sensor.{prefix}_distance",
            CONF_X: f"sensor.{prefix}_x",
            CONF_Y: f"sensor.{prefix}_y",
            **options,
        },
    )


async def setup(hass: HomeAssistant, *entries: MockConfigEntry) -> None:
    for entry in entries:
        entry.add_to_hass(hass)
    for entry in entries:
        if entry.state is ConfigEntryState.NOT_LOADED:
            await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def see(hass: HomeAssistant, prefix: str, distance: float, x: float = 0, y: float | None = None) -> None:
    hass.states.async_set(f"sensor.{prefix}_distance", str(distance))
    hass.states.async_set(f"sensor.{prefix}_x", str(x))
    hass.states.async_set(f"sensor.{prefix}_y", str(distance if y is None else y))
    hass.states.async_set(f"binary_sensor.{prefix}_presence", "on")


def lose(hass: HomeAssistant, prefix: str) -> None:
    hass.states.async_set(f"binary_sensor.{prefix}_presence", "off")
    for axis in ("distance", "x", "y"):
        hass.states.async_set(f"sensor.{prefix}_{axis}", "unknown")


def mock_lights(hass: HomeAssistant, reachable: bool = True) -> tuple[list, list]:
    """light.turn_on/off that change the state, like a real light would."""
    on, off = [], []

    async def turn_on(call):
        on.append(call)
        hass.states.async_set(call.data["entity_id"], "on")

    async def turn_off(call):
        off.append(call)
        if reachable:
            hass.states.async_set(call.data["entity_id"], "off")

    hass.services.async_register("light", "turn_on", turn_on)
    hass.services.async_register("light", "turn_off", turn_off)
    return on, off


def occupancy(hass: HomeAssistant, name: str) -> str:
    return hass.states.get(f"binary_sensor.{name}").state


async def advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float) -> None:
    await hass.async_block_till_done()  # process pending state changes at the current time
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_config_flow_creates_room_and_area(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["room", "home", "plan"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "room"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"name": "name_required"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Office"})
    assert result["step_id"] == "room_inputs"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PRESENCE: "binary_sensor.office_presence", CONF_DISTANCE: "sensor.office_distance"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    room = result["result"]
    assert room.title == "Office"
    assert room.options[CONF_DOOR_FROM] == 0
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["menu_options"] == ["room", "area", "home", "plan"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "area"})
    box = {CONF_X_MIN: 0, CONF_X_MAX: -1, CONF_Y_MIN: 0, CONF_Y_MAX: 1}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Balcony", CONF_PARENT: room.entry_id, **box}
    )
    assert result["errors"] == {"base": "invalid_box"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Balcony", CONF_PARENT: room.entry_id, **box, CONF_X_MAX: 1}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_updates_door_range(hass: HomeAssistant) -> None:
    entry = room_entry("Office", "office")
    await setup(hass, entry)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**entry.options, CONF_DOOR_FROM: 4000}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_DOOR_FROM] == 4000
    assert entry.state is ConfigEntryState.LOADED


async def test_still_person_held_door_releases(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    await setup(hass, room_entry("Office", "office", **{CONF_DOOR_FROM: 4000}))
    see(hass, "office", 900)
    await hass.async_block_till_done()
    assert occupancy(hass, "office") == "on"

    lose(hass, "office")
    await advance(hass, freezer, 600)
    state = hass.states.get("binary_sensor.office")
    assert state.state == "on"
    assert state.attributes["reason"] == "held"
    assert hass.states.get("sensor.office_last_seen_distance").state == "900.0"

    see(hass, "office", 2500)
    await hass.async_block_till_done()
    see(hass, "office", 5600)
    lose(hass, "office")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.office")
    assert state.state == "off"
    assert state.attributes["reason"] == "left_through_door"


async def test_safety_timeout(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    await setup(hass, room_entry("Office", "office", **{CONF_DOOR_FROM: 4000, CONF_SAFETY_TIMEOUT: 30}))
    see(hass, "office", 900)
    lose(hass, "office")
    await advance(hass, freezer, 29 * 60)
    assert occupancy(hass, "office") == "on"
    await advance(hass, freezer, 61)
    assert occupancy(hass, "office") == "off"


async def test_light_on_enter_off_after_run_on(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    turn_on, turn_off = mock_lights(hass)
    hass.states.async_set("sun.sun", "below_horizon")
    hass.states.async_set("light.office", "off")
    await setup(hass, room_entry("Office", "office", **{CONF_LIGHT: "light.office", CONF_RUN_ON: 30}))

    see(hass, "office", 1000)
    await hass.async_block_till_done()
    assert len(turn_on) == 1
    assert turn_on[0].data == {"entity_id": "light.office", "brightness_pct": 100}

    lose(hass, "office")  # default door range: every loss is leaving
    await advance(hass, freezer, 10)
    assert not turn_off
    await advance(hass, freezer, 25)
    assert len(turn_off) == 1


async def test_daylight_keeps_light_off_but_owns_it(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    turn_on, turn_off = mock_lights(hass)
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set("light.office", "on")  # switched on by hand before
    await setup(hass, room_entry("Office", "office", **{CONF_LIGHT: "light.office", CONF_RUN_ON: 0}))
    see(hass, "office", 1000)
    await hass.async_block_till_done()
    assert not turn_on
    lose(hass, "office")
    await advance(hass, freezer, 2)
    assert len(turn_off) == 1


async def test_light_kept_while_other_room_with_same_light_occupied(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    _, turn_off = mock_lights(hass)
    hass.states.async_set("sun.sun", "below_horizon")
    hass.states.async_set("light.hall", "off")
    a = room_entry("Hall A", "a", **{CONF_LIGHT: "light.hall", CONF_RUN_ON: 0})
    b = room_entry("Hall B", "b", **{CONF_LIGHT: "light.hall", CONF_RUN_ON: 0})
    await setup(hass, a, b)
    see(hass, "a", 1000)
    see(hass, "b", 1000)
    await hass.async_block_till_done()
    hass.states.async_set("light.hall", "on")
    lose(hass, "a")
    await advance(hass, freezer, 5)
    assert not turn_off
    lose(hass, "b")
    await advance(hass, freezer, 5)
    assert turn_off


async def test_unreachable_light_is_retried(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    _, turn_off = mock_lights(hass, reachable=False)
    hass.states.async_set("sun.sun", "below_horizon")
    hass.states.async_set("light.office", "off")
    await setup(hass, room_entry("Office", "office", **{CONF_LIGHT: "light.office", CONF_RUN_ON: 0}))
    see(hass, "office", 1000)
    await hass.async_block_till_done()
    hass.states.async_set("light.office", "on")
    lose(hass, "office")
    await advance(hass, freezer, 2)
    assert len(turn_off) == 3  # command dropped, light stays on
    await advance(hass, freezer, 60)
    assert len(turn_off) == 3
    await advance(hass, freezer, 300)
    assert len(turn_off) == 6
    assert hass.states.get("binary_sensor.office").attributes["light_owned"]


async def test_handover(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    lab = room_entry("Lab", "lab", **{CONF_DOOR_FROM: 2750, CONF_HANDOVER: True, CONF_HANDOVER_ANYWHERE: True})
    office = room_entry("Office", "office", **{CONF_DOOR_FROM: 4000, CONF_HANDOVER: True})
    await setup(hass, lab, office)
    see(hass, "lab", 1300)
    await hass.async_block_till_done()
    lose(hass, "lab")
    see(hass, "office", 1000)
    await advance(hass, freezer, 10)
    assert occupancy(hass, "lab") == "on"
    await advance(hass, freezer, 15)
    state = hass.states.get("binary_sensor.lab")
    assert state.state == "off"
    assert state.attributes["reason"] == "handed_over"


async def test_handover_switch_off_with_guests(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    from custom_components.radar_occupancy.const import HOME_DEFAULTS, KIND_HOME

    home = MockConfigEntry(
        domain=DOMAIN, title="Flat", data={CONF_KIND: KIND_HOME}, options=dict(HOME_DEFAULTS), unique_id="home"
    )
    lab = room_entry("Lab", "lab", **{CONF_DOOR_FROM: 2750, CONF_HANDOVER: True, CONF_HANDOVER_ANYWHERE: True})
    office = room_entry("Office", "office", **{CONF_DOOR_FROM: 4000, CONF_HANDOVER: True})
    await setup(hass, home, lab, office)
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.flat_handover_between_rooms"}, blocking=True
    )
    see(hass, "lab", 1300)
    await hass.async_block_till_done()
    lose(hass, "lab")
    see(hass, "office", 1000)
    await advance(hass, freezer, 60)
    assert occupancy(hass, "lab") == "on"
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.flat_handover_between_rooms"}, blocking=True
    )
    await advance(hass, freezer, 2)
    assert hass.states.get("binary_sensor.lab").attributes["reason"] == "handed_over"


async def test_area_and_release_and_learn(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    lab = room_entry("Lab", "lab", **{CONF_DOOR_FROM: 2750})
    await setup(hass, lab)
    area = MockConfigEntry(
        domain=DOMAIN,
        title="Balcony",
        data={CONF_KIND: KIND_AREA},
        options={
            **DEFAULTS,
            CONF_PARENT: lab.entry_id,
            CONF_X_MIN: -3000,
            CONF_X_MAX: -600,
            CONF_Y_MIN: 2000,
            CONF_Y_MAX: 8000,
        },
    )
    await setup(hass, area)
    see(hass, "lab", 3400, x=-1100, y=3200)
    await hass.async_block_till_done()
    lose(hass, "lab")
    await advance(hass, freezer, 5)
    assert occupancy(hass, "lab") == "on"
    assert occupancy(hass, "balcony") == "on"

    await hass.services.async_call("button", "press", {"entity_id": "button.lab_release"}, blocking=True)
    await hass.async_block_till_done()
    assert occupancy(hass, "lab") == "off"
    assert occupancy(hass, "balcony") == "off"

    await hass.services.async_call(
        "button", "press", {"entity_id": "button.lab_learn_door_from_last_exit"}, blocking=True
    )
    await hass.async_block_till_done()
    assert lab.options[CONF_DOOR_FROM] == 2900


async def test_state_survives_restart(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    entry = room_entry("Office", "office", **{CONF_DOOR_FROM: 4000})
    await setup(hass, entry)
    see(hass, "office", 900)
    lose(hass, "office")
    await advance(hass, freezer, 5)
    assert occupancy(hass, "office") == "on"
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert occupancy(hass, "office") == "on"
    assert hass.states.get("binary_sensor.office").attributes["reason"] == "held"


async def test_entities_have_unique_ids(hass: HomeAssistant) -> None:
    entry = room_entry("Office", "office", **{CONF_LIGHT: "light.office"})
    await setup(hass, entry)
    registry = er.async_get(hass)
    ids = {e.unique_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)}
    assert ids == {
        f"{entry.entry_id}_{key}"
        for key in ("occupancy", "last_distance", "release", "learn_door", "auto_light", "only_dark", "hold")
    }


async def test_distance_in_metres_is_converted(hass: HomeAssistant) -> None:
    await setup(hass, room_entry("Office", "office", **{CONF_DOOR_FROM: 4000}))
    hass.states.async_set("sensor.office_distance", "5.6", {"unit_of_measurement": "m"})
    hass.states.async_set("binary_sensor.office_presence", "on")
    await hass.async_block_till_done()
    lose(hass, "office")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.office")
    assert state.attributes["last_distance"] == 5600
    assert state.attributes["reason"] == "left_through_door"


async def test_last_seen_distance_published_on_loss(hass: HomeAssistant) -> None:
    await setup(hass, room_entry("Office", "office", **{CONF_DOOR_FROM: 4000}))
    see(hass, "office", 900)
    await hass.async_block_till_done()
    see(hass, "office", 1200)
    await hass.async_block_till_done()
    lose(hass, "office")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.office_last_seen_distance").state == "1200.0"


async def test_room_from_radar_device(hass: HomeAssistant) -> None:
    """Choosing the radar device suggests its sensors and the room name from its area."""
    from homeassistant.helpers import area_registry as ar
    from homeassistant.helpers import device_registry as dr

    source = MockConfigEntry(domain="esphome")
    source.add_to_hass(hass)
    area = ar.async_get(hass).async_create("Living room")
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=source.entry_id, identifiers={("esphome", "radar1")}, name="Radar 1"
    )
    dr.async_get(hass).async_update_device(device.id, area_id=area.id)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "binary_sensor",
        "esphome",
        "p",
        device_id=device.id,
        suggested_object_id="radar_1_presence",
        original_name="Presence",
        original_device_class="occupancy",
        config_entry=source,
    )
    for n in (1, 2, 3):
        for axis in ("x", "y", "distance"):
            registry.async_get_or_create(
                "sensor",
                "esphome",
                f"t{n}{axis}",
                device_id=device.id,
                suggested_object_id=f"radar_1_target_{n}_{axis}",
                original_name=f"Target {n} {axis}",
                config_entry=source,
            )
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "room"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"device": device.id})
    assert result["step_id"] == "room_inputs"
    assert result["description_placeholders"] == {"room": "Living room", "found": "8"}
    defaults = {str(key): key.default() for key in result["data_schema"].schema if callable(key.default)}
    suggested = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }
    assert defaults[CONF_PRESENCE] == "binary_sensor.radar_1_presence"
    assert suggested[CONF_DISTANCE] == "sensor.radar_1_target_1_distance"
    assert suggested["y3_entity"] == "sensor.radar_1_target_3_y"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**defaults, **suggested})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room"
    assert result["result"].options["x2_entity"] == "sensor.radar_1_target_2_x"
