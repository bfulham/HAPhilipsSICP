"""Platform for TV integration."""
from __future__ import annotations

import logging
from multiprocessing.dummy import connection

import voluptuous as vol
from .const import DOMAIN, MANUFACTURER

from pprint import pformat

# Import the device class from the component that you want to support
import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player import (PLATFORM_SCHEMA, MediaPlayerEntity, MediaPlayerState, MediaPlayerEntityFeature, MediaPlayerDeviceClass)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME
from homeassistant import config_entries, core
from homeassistant.helpers.device_registry import DeviceInfo

_LOGGER = logging.getLogger(DOMAIN)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.string
})

async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Set up the Philips SICP platform."""
    # Add devices
    config = hass.data[DOMAIN][config_entry.entry_id]
    _LOGGER.info(pformat(config))
    
    async_add_entities([Philips_SICP(config_entry)])

class Philips_SICP(MediaPlayerEntity):
    """Representation of a Philips SICP display."""

    def __init__(self, config_entry) -> None:
        """Initialize a Philips SICP display."""
        self._media_player = config_entry.device
        self._name = config_entry.data["name"]
        self._state = None
        self._source = None
        self._source_list = []
        self._manufacturer = MANUFACTURER
        self._model = self._media_player.data["Model Number"]
        self._serialnumber = self._media_player.data["Serial Number"]
        self._hwversion = self._media_player.data["Platform label"], " ", self._media_player.data["Platform version"]
        self._swversion = self._media_player.data["FW version"]
        self._unique_id = self._serialnumber
        self._is_volume_muted = False
        self._volume = self._media_player.data["Volume"]["Speaker Volume"] / 100

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._unique_id)
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
    def unique_id(self) -> str:
        return self._name

    @property
    def is_on(self) -> bool | None:
        """Return true if display is on."""
        return self.state
    
    @property
    def is_volume_muted(self) -> bool | None:
        """Return true if muted."""
        return self._is_volume_muted
    
    @property
    def supported_features(self):
        return MediaPlayerEntityFeature.VOLUME_SET|MediaPlayerEntityFeature.VOLUME_MUTE|MediaPlayerEntityFeature.TURN_ON|MediaPlayerEntityFeature.TURN_OFF|MediaPlayerEntityFeature.SELECT_SOURCE|MediaPlayerEntityFeature.VOLUME_STEP

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
    
    @property
    def volume_level(self) -> float | None:
        """Return the volume of this entity."""
        return self._volume
    
    @property
    def volume_step(self) -> float | None:
        return 0.01

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        self._media_player.set("Mute", mute)

    async def async_set_volume_level(self, volume: float) -> None:
        """set the volume."""
        self._media_player.set("Volume", int(volume * 100), 0)

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
                self._media_player.set("Input Source", int(key, 16), 0, 1, 0)

    async def async_will_remove_from_hass(self) -> bool:
        self._media_player.disconnect()
        return True

    async def async_update(self) -> None:
        """Fetch new state data for this display."""
        try:
            self._media_player.updateAll()
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            _LOGGER.error("Connection to device lost, attempting to reconnect...")
            self._media_player.disconnect()
            try:
                self._media_player.connect()
                self._media_player.updateAll()
                _LOGGER.info("Connection restored.")
            except:
                _LOGGER.error("Connection restore failed.")
                raise ConnectionError
            return
        if self._media_player.data['Power State']:
            self.state = MediaPlayerState.ON
        else:
            self.state = MediaPlayerState.OFF
        self._source = self._media_player.data['Input Source']['Input Source Type/Number']
        self._source_list = list(self._media_player.bible['AC']['command']['1']['Options'].values())
        self._is_volume_muted = False
        self._volume = self._media_player.data["Volume"]["Speaker Volume"] / 100