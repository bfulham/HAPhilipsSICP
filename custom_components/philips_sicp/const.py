"""Constants for the Philips SICP integration."""
from homeassistant.const import Platform

DOMAIN = "philips_sicp"
MANUFACTURER = "Philips"

CONF_MONITOR_ID = "monitor_id"
CONF_GROUP_ID = "group_id"
CONF_DISPLAYS = "displays"
CONF_ADMIN_PIN = "admin_pin"

DEFAULT_GROUP_ID = 0

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.LIGHT,
]
