"""Constants for Radar Occupancy."""

DOMAIN = "radar_occupancy"

CONF_KIND = "kind"
KIND_ROOM = "room"
KIND_AREA = "area"

# Room inputs
CONF_PRESENCE = "presence_entity"
CONF_DISTANCE = "distance_entity"
CONF_X = "x_entity"
CONF_Y = "y_entity"

# Room behaviour
CONF_DOOR_FROM = "door_from"
CONF_DOOR_TO = "door_to"
CONF_SAFETY_TIMEOUT = "safety_timeout"  # minutes, 0 = off
CONF_HANDOVER = "handover"
CONF_HANDOVER_ANYWHERE = "handover_anywhere"
CONF_TAKEOVER_MIN = "takeover_min"

# Sub-area
CONF_PARENT = "parent"
CONF_X_MIN = "x_min"
CONF_X_MAX = "x_max"
CONF_Y_MIN = "y_min"
CONF_Y_MAX = "y_max"

# Light, for rooms and sub-areas
CONF_LIGHT = "light_entity"
CONF_BRIGHTNESS = "brightness"
CONF_RUN_ON = "run_on"  # seconds
CONF_WINDOW_START = "window_start"
CONF_WINDOW_END = "window_end"

DEFAULTS = {
    CONF_DOOR_FROM: 0,
    CONF_DOOR_TO: 0,
    CONF_SAFETY_TIMEOUT: 30,
    CONF_HANDOVER: False,
    CONF_HANDOVER_ANYWHERE: False,
    CONF_TAKEOVER_MIN: 0,
    CONF_BRIGHTNESS: 100,
    CONF_RUN_ON: 60,
    CONF_WINDOW_START: "00:00:00",
    CONF_WINDOW_END: "00:00:00",
}

# Light control
OFF_ATTEMPTS = 3
OFF_RETRY_DELAY = 5  # s between attempts within one try
OFF_RECHECK = 300  # s before the next try if the light stayed on
DOOR_LEARN_MARGIN = 500  # mm below the last exit distance

SIGNAL_UPDATE = f"{DOMAIN}_update_{{}}"
STORAGE_VERSION = 1
STORAGE_KEY = DOMAIN
