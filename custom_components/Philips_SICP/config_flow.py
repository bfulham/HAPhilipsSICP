from homeassistant import config_entries, core
from .const import DOMAIN
import voluptuous as vol
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv
from typing import Any, Dict, Optional
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get,
)
import socket

async def validate_host(host: cv.string, port: cv.port, hass: core.HomeAssistant) -> bool:
    """Validates a GitHub access token.
    Raises a ValueError if the auth token is invalid.
    """
    connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    connection.settimeout(5)
    if connection.connect_ex((host, port)) == 0:
        connection.close()
    else:
        raise ConnectionError

class Philips_SICPConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    data: Optional[Dict[str, Any]]
    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        """Invoked when a user initiates a flow via the user interface."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_host(user_input[CONF_HOST], user_input[CONF_PORT], self.hass)
            except ConnectionError:
                errors["base"] = "Failed to connect to device"
            if not errors:
                # Input is valid, set data.
                self.data = user_input
                # User is done adding repos, create the config entry.
                return self.async_create_entry(title="Philips professional display", data=self.data)
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({
                vol.Required(CONF_NAME): cv.string,
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PORT, default=5000): cv.port
            }), errors=errors
        )
    

class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Manage the options for the custom component."""
        errors: Dict[str, str] = {}
        # Grab all configured repos from the entity registry so we can populate the
        # multi-select dropdown that will allow a user to remove a repo.
        entity_registry = async_get(self.hass)
        entries = async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        )

        if user_input is not None:
            updated_config = dict(self.config_entry.data)

            updated_config[CONF_NAME] = user_input.get(CONF_NAME, updated_config.get(CONF_NAME))
            updated_config[CONF_HOST] = user_input.get(CONF_HOST, updated_config.get(CONF_HOST))
            updated_config[CONF_PORT] = user_input.get(CONF_PORT, updated_config.get(CONF_PORT, 5000))

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=updated_config,
                title=self.config_entry.title,
            )
            
        

        options_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=self.config_entry.data.get(CONF_NAME)): cv.string,
                vol.Required(CONF_HOST, default=self.config_entry.data.get(CONF_HOST)): cv.string,
                vol.Required(CONF_PORT, default=self.config_entry.data.get(CONF_PORT, 5000)): cv.port,
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )