"""Platform for TV integration."""
from __future__ import annotations

import logging

import voluptuous as vol
from .const import DOMAIN, IGNORE_SELECTS, UNSUPPORTED_VALUES, MANUFACTURER

from pprint import pformat

# Import the device class from the component that you want to support
import homeassistant.helpers.config_validation as cv
from homeassistant.components.select import (PLATFORM_SCHEMA, SelectEntity)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME, EntityCategory
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
    config = hass.data[DOMAIN][config_entry.entry_id] #{0: 'HDMI 1', 1: 'HDMI 1', 2: 'HDMI 1', 3: 'HDMI 1', 4: 'HDMI 1', 5: 'HDMI 1', 6: 'HDMI 1', 7: 'HDMI 1', 8: 'HDMI 1', 9: 'HDMI 1', 10: 'HDMI 1', 11: 'HDMI 1', 12: 'HDMI 1', 13: 'HDMI 1'}
    _LOGGER.info(pformat(config))
    
    parameters = config_entry.device.availableSets()
    data = config_entry.device.data
    for parameter in parameters:
        if parameters[parameter]['name'] not in IGNORE_SELECTS:
            for byte in parameters[parameter]['command']:
                match parameters[parameter]['command'][byte]['type']:
                    case "multilist":
                        if data[parameters[parameter]['name']] not in UNSUPPORTED_VALUES:
                            for key in data[parameters[parameter]['name']]:
                                async_add_entities([Philips_SICP(parameter, config_entry, str(key), parameters[parameter]['name'], str(key + 1))])
                    case "list":
                        if data[parameters[parameter]['name']] not in UNSUPPORTED_VALUES:
                            if len(parameters[parameter]['command']) == 1:
                                async_add_entities([Philips_SICP(parameter, config_entry, parameters[parameter]['name'])])
                            else: 
                                if parameters[parameter]['name'] == "Picture-in-Picture":
                                    async_add_entities([Philips_SICP(parameter, config_entry, parameters[parameter]['command'][byte]['Description'], parameters[parameter]['name'], byte)])
                                else:
                                    async_add_entities([Philips_SICP(parameter, config_entry, parameters[parameter]['command'][byte]['Description'])])
                

class Philips_SICP(SelectEntity):
    """Representation of a Philips SICP display."""

    def __init__(self, parameter, config_entry, name, location = "", byte = "1") -> None:
        """Initialize a Philips SICP display."""
        self._select = config_entry.device
        self._device_name = config_entry.data["name"]
        self._select_name = name
        self._location = location
        self._parameter = parameter
        self._byte = byte
        if self._select.availableSets()[self._parameter]['command']['1']['type'] == 'multilist':
            self._options = list(self._select.availableSets()[self._parameter]['command']['1']['Options'].values())
            self._name = config_entry.data["name"] + " " + self._location + " " + str(self._byte)
            self._state = self._select.data[self._location][int(self._select_name)]
        else:
            self._options = list(self._select.availableSets()[self._parameter]['command'][self._byte]['Options'].values())
            self._name = config_entry.data["name"] + " " + self._select_name
            try:
                if self._location == "":
                    self._state = self._select.data[self._select_name]
                else:
                    self._state = self._select.data[self._location][self._select_name]
            except KeyError:
                self._state = None
        self._manufacturer = MANUFACTURER
        self._model = self._select.data["Model Number"]
        self._serialnumber = self._select.data["Serial Number"]
        self._hwversion = self._select.data["Platform label"], " ", self._select.data["Platform version"]
        self._swversion = self._select.data["FW version"]
        self._unique_id = self._serialnumber


    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._unique_id)
            },
            name=self._device_name,
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
    def entity_category(self) -> EntityCategory:
        return EntityCategory.CONFIG
    
    @property
    def options(self):
        return self._options
    
    @property
    def current_option(self):
        return self._state
    
    @property
    def unique_id(self) -> str:
        return self._name
    
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        data = {}
        for byte in self._select.availableSets()[self._parameter]['command']:
            if byte == self._byte:
                for key, value in self._select.availableSets()[self._parameter]['command'][self._byte]['Options'].items():
                    if value == option:
                        data[byte] = key
            else:
                match self._select.availableSets()[self._parameter]['command'][byte]['type']:
                    case 'reserved':
                        data[byte] = self._select.availableSets()[self._parameter]['command'][byte]['value']
                    case 'multilist':
                        new = self._select.data[self._location][self._select_name] = option
                        self._select.set(self._location, new)
                        return None
                    case _:
                        if self._location == "":
                            self._state = self._select.data[self._select.availableSets()[self._parameter]['name']]
                        else:
                            for key, value in self._select.availableSets()[self._parameter]['command'][byte]['Options'].items():
                                if value == self._select.data[self._location][self._select.availableSets()[self._parameter]['command'][byte]['Description']]:
                                    data[byte] = key
        match len(data):
            case 1:
                self._select.set(self._select.availableSets()[self._parameter]['name'], int(data['1'], 16))
            case 2:
                self._select.set(self._select.availableSets()[self._parameter]['name'], int(data['1'], 16), int(data['2'], 16))
            case 3:
                self._select.set(self._select.availableSets()[self._parameter]['name'], int(data['1'], 16), int(data['2'], 16), int(data['3'], 16))
            case 4:
                self._select.set(self._select.availableSets()[self._parameter]['name'], int(data['1'], 16), int(data['2'], 16), int(data['3'], 16), int(data['4'], 16))
            case 5:
                self._select.set(self._select.availableSets()[self._parameter]['name'], int(data['1'], 16), int(data['2'], 16), int(data['3'], 16), int(data['4'], 16), int(data['5'], 16))
            case 6:
                self._select.set(self._select.availableSets()[self._parameter]['name'], int(data['1'], 16), int(data['2'], 16), int(data['3'], 16), int(data['4'], 16), int(data['5'], 16), int(data['6'], 16))


        
        

    async def async_update(self) -> None:
        """Fetch new state data for this display."""
        if self._select.availableSets()[self._parameter]['command']['1']['type'] == 'multilist':
            self._state = self._select.data[self._location][int(self._select_name)]
        else:
            try:
                if self._location == "":
                    self._state = self._select.data[self._select_name]
                else:
                    self._state = self._select.data[self._location][self._select_name]
            except KeyError:
                self._state = None