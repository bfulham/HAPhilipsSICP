"""Platform for TV integration."""
from __future__ import annotations

import logging

import voluptuous as vol
from datetime import datetime
from .const import DOMAIN, UNSUPPORTED_VALUES, IGNORE_SENSORS, SENSOR_SUBVALUES, MANUFACTURER

from pprint import pformat

# Import the device class from the component that you want to support
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import (PLATFORM_SCHEMA, SensorEntity, SensorDeviceClass, SensorStateClass)
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
    
    sensors = config_entry.device.data
    for sensor in sensors:
        if sensors[sensor] not in UNSUPPORTED_VALUES:
            if sensor not in IGNORE_SENSORS:
                if sensor in SENSOR_SUBVALUES:
                    for i in sensors[sensor]:
                        async_add_entities([Philips_SICP(i, config_entry, sensor)])
                else:
                    async_add_entities([Philips_SICP(sensor, config_entry)])
                

class Philips_SICP(SensorEntity):
    """Representation of a Philips SICP display."""

    def __init__(self, sensor, config_entry, location = "") -> None:
        """Initialize a Philips SICP display."""
        self._sensor = config_entry.device
        self._device_name = config_entry.data["name"]
        self._name = config_entry.data["name"] + " " + sensor
        self._location = location
        self._sensor_name = sensor
        if self._location == "":
            self._state = self._sensor.data[self._sensor_name]
        else:
            self._state = self._sensor.data[self._location][self._sensor_name]
        self._manufacturer = MANUFACTURER
        self._model = self._sensor.data["Model Number"]
        self._serialnumber = self._sensor.data["Serial Number"]
        self._hwversion = self._sensor.data["Platform label"], " ", self._sensor.data["Platform version"]
        self._swversion = self._sensor.data["FW version"]
        self._unique_id = self._serialnumber
        match self._sensor_name:
            case "Temperature Sensor 1":
                self._device_class = SensorDeviceClass.TEMPERATURE
                self._state_class = SensorStateClass.MEASUREMENT
                self._unit = "°C"
            case "Temperature Sensor 2":
                self._device_class = SensorDeviceClass.TEMPERATURE
                self._state_class = SensorStateClass.MEASUREMENT
                self._unit = "°C"
            case "Operating Hours":
                self._device_class = SensorDeviceClass.DURATION
                self._state_class = SensorStateClass.TOTAL
                self._unit = "h"
            case "Build date":
                self._device_class = SensorDeviceClass.DATE
                self._state_class = None
                self._unit = None
            case _:
                self._device_class = None
                self._state_class = None
                self._unit = None


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
    def state(self):
        if self._sensor_name == "Build date":
            return datetime.strptime(self._state, "%b %d %Y")
        else:
            return self._state
    
    @property
    def state_class(self) -> SensorStateClass:
        return self._state_class
    
    @property
    def device_class(self) -> SensorDeviceClass:
        return self._device_class
    
    @property
    def native_unit_of_measurement(self) -> str | None:
        return self._unit
    
    @property
    def unique_id(self) -> str:
        return self._name

    async def async_update(self) -> None:
        """Fetch new state data for this display."""
        if self._location == "":
            self._state = self._sensor.data[self._sensor_name]
        else:
            self._state = self._sensor.data[self._location][self._sensor_name]