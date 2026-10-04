"""Constants for Radar Occupancy."""

DOMAIN = "radar_occupancy"

CONF_KIND = "kind"
KIND_ROOM = "room"
KIND_AREA = "area"
KIND_HOME = "home"  # one per installation: map mode, master switch, overview
KIND_PLAN = "plan"  # a floor plan image as map, for homes without a supported robot map

# Room inputs
CONF_PRESENCE = "presence_entity"
CONF_DISTANCE = "distance_entity"
CONF_X = "x_entity"
CONF_Y = "y_entity"
# Further targets (LD2450 tracks three); only used in map mode.
CONF_X2 = "x2_entity"
CONF_Y2 = "y2_entity"
CONF_X3 = "x3_entity"
CONF_Y3 = "y3_entity"

# Floor plan entry
CONF_IMAGE = "image"  # file below <config>/www, e.g. "floorplans/ground.png"
CONF_IMAGE_WIDTH = "image_width"  # real width of the whole image in metres
PLAN_PREFIX = "plan."  # map source value of a floor plan: "plan.<entry id>"

# Map mode, per room
CONF_MAP_CAMERA = "map_camera"  # map source: dreame_vacuum map camera or "plan.<entry id>"
CONF_MAP_ROOM = "map_room"  # segment name on that map
CONF_DOOR_ROOMS = "door_rooms"  # map segments reachable through a real door

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
CONF_REMEMBER_BRIGHTNESS = "remember_brightness"  # fade to the last brightness set by hand

# Home entry
CONF_MANUAL_OFF_RESET = "manual_off_reset"  # minutes empty until "switched off by hand" ends
CONF_APPROACH_BRIGHTNESS = "approach_brightness"  # % of the target brightness when pre-lighting

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
    CONF_REMEMBER_BRIGHTNESS: False,
    CONF_DOOR_ROOMS: [],
}

HOME_DEFAULTS = {
    CONF_MANUAL_OFF_RESET: 30,
    CONF_APPROACH_BRIGHTNESS: 30,
}

# Light control
OFF_ATTEMPTS = 3
OFF_RETRY_DELAY = 5  # s between attempts within one try
OFF_RECHECK = 300  # s before the next try if the light stayed on
DOOR_LEARN_MARGIN = 500  # mm below the last exit distance
OWN_ECHO = 10  # s after own commands: state changes are not by hand
PRELIT_TIMEOUT = 20  # s pre-lit for someone approaching who did not come in
FADE_STEP = 0.1  # s per fade step
LIGHT_SLOTS = 8  # concurrent light commands (cloud integrations have small pools)
NEAR_FIELD = 300  # mm: targets closer to the sensor are echoes, not people
TARGET_MAX_AGE = 5  # s: older radar coordinates are not a live target
DEFAULT_FADE_IN = 0.0
DEFAULT_FADE_OUT = 0.0

SIGNAL_UPDATE = f"{DOMAIN}_update_{{}}"
SIGNAL_HOME = f"{DOMAIN}_home"
CARD_URL = "/radar_occupancy/radar-occupancy-card.js"
MAP_URL = "/api/radar_occupancy/map/{floor}"
STORAGE_VERSION = 1
STORAGE_KEY = DOMAIN
