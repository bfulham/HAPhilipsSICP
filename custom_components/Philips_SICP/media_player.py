"""Platform for light integration."""
from __future__ import annotations

import logging

import serialdevicelib
import voluptuous as vol

# Import the device class from the component that you want to support
import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player import 
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.int
})


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the Awesome Light platform."""
    # Assign configuration variables.
    # The configuration check takes care they are present.
    host = config[CONF_HOST]
    username = config[CONF_USERNAME]
    password = config.get(CONF_PASSWORD)

    # Setup connection with devices/cloud
    hub = awesomelights.Hub(host, username, password)

    # Verify that passed in configuration works
    if not hub.is_valid_login():
        _LOGGER.error("Could not connect to AwesomeLight hub")
        return

    # Add devices
    add_entities(AwesomeLight(light) for light in hub.lights())


class AwesomeLight(LightEntity):
    """Representation of an Awesome Light."""

    def __init__(self, light) -> None:
        """Initialize an AwesomeLight."""

    @property
    def name(self) -> str:
        """Return the display name of this light."""

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""


    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on.

        You can skip the brightness part if your light does not support
        brightness control.
        """


    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""


    def update(self) -> None:
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
