"""Platform for TV integration."""
from __future__ import annotations

import logging

import serialdevicelib
import voluptuous as vol
from .const import DOMAIN

from pprint import pformat

# Import the device class from the component that you want to support
import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player import (PLATFORM_SCHEMA, MediaPlayerEntity, MediaPlayerState, MediaPlayerEntityFeature, MediaPlayerDeviceClass)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME
from homeassistant import config_entries, core
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.device_registry import DeviceInfo

_LOGGER = logging.getLogger("Philips_SICP")

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.string
})

async def async_setup_platform(
    hass: core.HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the Philips SICP platform."""
    # Add devices
    _LOGGER.info(pformat(config))
    
    media_player = {
        "name": config[CONF_NAME],
        "host": config[CONF_HOST],
        "port": config[CONF_PORT]
    }
    
    async_add_entities([Philips_SICP(media_player)])

async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Set up the Philips SICP platform."""
    # Add devices
    config = hass.data[DOMAIN][config_entry.entry_id]
    _LOGGER.info(pformat(config))
    
    media_player = {
        "name": config[CONF_NAME],
        "host": config[CONF_HOST],
        "port": config[CONF_PORT]
    }
    
    async_add_entities([Philips_SICP(media_player)])

class Philips_SICP(MediaPlayerEntity):
    """Representation of a Philips SICP display."""

    def __init__(self, media_player) -> None:
        """Initialize a Philips SICP display."""
        _LOGGER.info(pformat(media_player))
        self._media_player = serialdevicelib.serial_device(media_player["host"], int(media_player["port"]), 1, 0, "/config/custom_components/Philips_SICP/data.JSON")
        self._name = media_player["name"]
        self.state = None
        self._source = None
        self._source_list = []
        self._media_player.connect()
        self._manufacturer = "Philips"
        self._model = self._media_player.get('Model & Firmware Information', 0)
        self._serialnumber = self._media_player.get('Serial Number')
        self._hwversion = self._media_player.get('SICP Version & Platform Information', 1), " ", self._media_player.get('SICP Version & Platform Information', 2)
        self._swversion = self._media_player.get('SICP Version & Platform Information', 0)
        self.unique_id = self._serialnumber

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            name=self._name,
            suggested_area="Lounge Room",
            manufacturer=self._manufacturer,
            model=self._model,
            serial_number=self._serialnumber,
            sw_version=self._swversion,
            hw_version=self._hwversion,
        )

    @property
    def name(self) -> str:
        """Return the display name of this device."""
        return self._name

    @property
    def is_on(self) -> bool | None:
        """Return true if display is on."""
        return self.state
    
    @property
    def supported_features(self):
        return MediaPlayerEntityFeature.PAUSE|MediaPlayerEntityFeature.VOLUME_SET|MediaPlayerEntityFeature.VOLUME_MUTE|MediaPlayerEntityFeature.TURN_ON|MediaPlayerEntityFeature.TURN_OFF|MediaPlayerEntityFeature.SELECT_SOURCE

    @property
    def source(self) -> str | None:
        """Name of the current input source."""
        return self._source
    
    @property
    def source_list(self) -> list[str] | None:
        """List of available input sources."""
        return self._source_list
    
    @property
    def device_class(self) -> MediaPlayerDeviceClass | None:
        """Return the class of this entity."""
        return MediaPlayerDeviceClass.TV
    
    async def shutdown(self):
        """Shutdown the service"""
        self._media_player.disconnect()

    async def async_turn_on(self) -> None:
        """Instruct the display to turn on."""
        self._media_player.set("Power State", 2)

    async def async_turn_off(self) -> None:
        """Instruct the display to turn off."""
        self._media_player.set("Power State", 1)

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        for key, value in self._media_player.bible['AC']['command']['1']['Options'].items():
            if value == source:
                self._media_player.set("Input Source", key, 0, 1, 0)

    async def async_update(self) -> None:
        """Fetch new state data for this display."""
        if self._media_player.get('Power State'):
            self.state = MediaPlayerState.ON
        else:
            self.state = MediaPlayerState.OFF
        self._source = self._media_player.get('Input Source')['Input Source Type/Number']
        self._source_list = list(self._media_player.bible['AC']['command']['1']['Options'].values())