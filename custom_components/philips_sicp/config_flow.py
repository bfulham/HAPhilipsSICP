"""Config flow: host/port once, then add one or more Monitor IDs.

A single LAN connection can drive several physical displays - the
LAN-connected one plus anything RS232-daisy-chained from it - by
addressing each one's Monitor ID (see protocol.py). This flow lets the
user register the host once and then add as many Monitor IDs as they
have displays behind that connection, validating each one live by
querying its SICP version before accepting it.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_ADMIN_PIN,
    CONF_DISPLAYS,
    CONF_GROUP_ID,
    CONF_MONITOR_ID,
    DEFAULT_GROUP_ID,
    DOMAIN,
)
from .protocol import DEFAULT_PORT, SICPClient, SICPConnectionError, SICPNotAvailableError

_LOGGER = logging.getLogger(__name__)


async def _probe_monitor(client: SICPClient, monitor_id: int, group_id: int) -> str:
    """Return the SICP version string reported by this Monitor ID, or raise."""
    data = await client.request(
        monitor_id, group_id, bytes([0xA2, 0x00]), expect_code=0xA2
    )
    return data.decode("ascii", errors="replace")


class PhilipsSICPConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._port: int = DEFAULT_PORT
        self._client: SICPClient | None = None
        self._displays: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]
            client = SICPClient(self._host, self._port)
            try:
                await client.connect()
            except (OSError, SICPConnectionError):
                errors["base"] = "cannot_connect"
            else:
                self._client = client
                return await self.async_step_add_display()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=errors,
        )

    async def async_step_add_display(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        assert self._client is not None

        if user_input is not None:
            monitor_id = user_input[CONF_MONITOR_ID]
            group_id = user_input[CONF_GROUP_ID]
            name = user_input[CONF_NAME]
            try:
                await _probe_monitor(self._client, monitor_id, group_id)
            except SICPNotAvailableError:
                errors["base"] = "not_available"
            except SICPConnectionError:
                errors["base"] = "monitor_not_responding"
            else:
                self._displays.append(
                    {CONF_MONITOR_ID: monitor_id, CONF_GROUP_ID: group_id, CONF_NAME: name}
                )
                if user_input.get("add_another"):
                    return await self.async_step_add_display()
                await self._client.disconnect()
                return self.async_create_entry(
                    title=self._host or "Philips SICP",
                    data={
                        CONF_HOST: self._host,
                        CONF_PORT: self._port,
                        CONF_DISPLAYS: self._displays,
                    },
                )

        next_id = 1 + max([d[CONF_MONITOR_ID] for d in self._displays], default=0)
        return self.async_show_form(
            step_id="add_display",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MONITOR_ID, default=next_id): vol.All(
                        int, vol.Range(min=1, max=255)
                    ),
                    vol.Required(CONF_GROUP_ID, default=DEFAULT_GROUP_ID): vol.All(
                        int, vol.Range(min=0, max=254)
                    ),
                    vol.Required(CONF_NAME, default=f"Display {next_id}"): str,
                    vol.Optional("add_another", default=False): bool,
                }
            ),
            description_placeholders={"count": str(len(self._displays))},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: config_entries.ConfigEntry) -> "PhilipsSICPOptionsFlow":
        return PhilipsSICPOptionsFlow(entry)


class PhilipsSICPOptionsFlow(config_entries.OptionsFlow):
    """Add another daisy-chained display, or set the admin menu PIN."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            new_display_id = user_input.get(CONF_MONITOR_ID)
            if new_display_id:
                client = SICPClient(self.entry.data[CONF_HOST], self.entry.data[CONF_PORT])
                try:
                    await client.connect()
                    await _probe_monitor(client, new_display_id, user_input[CONF_GROUP_ID])
                except (OSError, SICPConnectionError, SICPNotAvailableError):
                    errors["base"] = "monitor_not_responding"
                finally:
                    await client.disconnect()
                if not errors:
                    displays = list(self.entry.data[CONF_DISPLAYS])
                    displays.append(
                        {
                            CONF_MONITOR_ID: new_display_id,
                            CONF_GROUP_ID: user_input[CONF_GROUP_ID],
                            CONF_NAME: user_input[CONF_NAME],
                        }
                    )
                    self.hass.config_entries.async_update_entry(
                        self.entry, data={**self.entry.data, CONF_DISPLAYS: displays}
                    )
            if not errors:
                return self.async_create_entry(
                    title="", data={CONF_ADMIN_PIN: user_input.get(CONF_ADMIN_PIN, "")}
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_MONITOR_ID): vol.All(int, vol.Range(min=1, max=255)),
                    vol.Optional(CONF_GROUP_ID, default=DEFAULT_GROUP_ID): vol.All(
                        int, vol.Range(min=0, max=254)
                    ),
                    vol.Optional(CONF_NAME, default=""): str,
                    vol.Optional(
                        CONF_ADMIN_PIN, default=self.entry.options.get(CONF_ADMIN_PIN, "")
                    ): str,
                }
            ),
            errors=errors,
        )
