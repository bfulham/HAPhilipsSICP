"""The Philips SICP integration.

Talks directly to Philips professional displays over the SICP protocol
(TCP, port 5000 by default) - see protocol.py for the wire format. No
external device library is required. A single config entry holds one
connection (host/port) and one or more Monitor IDs; each Monitor ID gets
its own SICPDisplayCoordinator and Home Assistant device, which is what
lets one LAN-connected display plus any RS232-daisy-chained displays
behind it show up as separate, fully controllable devices.
"""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr

from . import composite
from .const import CONF_DISPLAYS, CONF_GROUP_ID, CONF_MONITOR_ID, DOMAIN, PLATFORMS
from .coordinator import SICPDisplayCoordinator
from .features import REMOTE_KEY_OPTIONS
from .protocol import SICPClient, SICPConnectionError

_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE_ID = "device_id"

SERVICE_SEND_REMOTE_KEY = "send_remote_key"
SERVICE_SET_IP_PARAMETER = "set_ip_parameter"
SERVICE_SET_MONITOR_ID = "set_monitor_id"
SERVICE_SET_FAILOVER = "set_failover_priority"
SERVICE_RESET_SCHEDULER = "reset_scheduler"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = SICPClient(entry.data[CONF_HOST], entry.data[CONF_PORT])
    try:
        await client.connect()
    except (OSError, SICPConnectionError) as err:
        raise ConfigEntryNotReady(f"Could not connect to {entry.data[CONF_HOST]}") from err

    coordinators: list[SICPDisplayCoordinator] = []
    for display in entry.data[CONF_DISPLAYS]:
        coordinator = SICPDisplayCoordinator(
            hass, entry, client,
            display[CONF_MONITOR_ID], display[CONF_GROUP_ID], display[CONF_NAME],
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators.append(coordinator)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinators
    hass.data[DOMAIN].setdefault("_clients", {})[entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        client: SICPClient = hass.data[DOMAIN].get("_clients", {}).pop(entry.entry_id, None)
        if client is not None:
            await client.disconnect()
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _find_coordinator(hass: HomeAssistant, device_id: str) -> SICPDisplayCoordinator:
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise ValueError(f"Unknown device_id {device_id}")
    serial = next((ident[1] for ident in device.identifiers if ident[0] == DOMAIN), None)
    for coordinators in hass.data.get(DOMAIN, {}).values():
        if not isinstance(coordinators, list):
            continue
        for coordinator in coordinators:
            if coordinator.serial_number == serial:
                return coordinator
    raise ValueError(f"No Philips SICP display found for device_id {device_id}")


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_SEND_REMOTE_KEY):
        return

    async def send_remote_key(call: ServiceCall) -> None:
        coordinator = _find_coordinator(hass, call.data[ATTR_DEVICE_ID])
        key_name = call.data["key"]
        key = next(code for code, name in REMOTE_KEY_OPTIONS.items() if name == key_name)
        await composite.send_remote_key(coordinator.client, coordinator.monitor_id, coordinator.group_id, key)

    async def set_ip_parameter(call: ServiceCall) -> None:
        coordinator = _find_coordinator(hass, call.data[ATTR_DEVICE_ID])
        await composite.set_ip_parameter(
            coordinator.client, coordinator.monitor_id, coordinator.group_id,
            parameter=call.data["parameter"], value=call.data.get("value", ""),
            dhcp=call.data.get("dhcp", False),
        )

    async def set_monitor_id(call: ServiceCall) -> None:
        coordinator = _find_coordinator(hass, call.data[ATTR_DEVICE_ID])
        await composite.set_monitor_id(
            coordinator.client, coordinator.monitor_id, coordinator.group_id, call.data["new_monitor_id"]
        )

    async def set_failover(call: ServiceCall) -> None:
        coordinator = _find_coordinator(hass, call.data[ATTR_DEVICE_ID])
        await coordinator.async_write_composite(
            "failover", composite.set_failover, sources=call.data["sources"]
        )

    async def reset_scheduler(call: ServiceCall) -> None:
        coordinator = _find_coordinator(hass, call.data[ATTR_DEVICE_ID])
        await composite.reset_scheduler(
            coordinator.client, coordinator.monitor_id, coordinator.group_id, call.data.get("page", 0)
        )

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_REMOTE_KEY, send_remote_key,
        schema=vol.Schema({
            vol.Required(ATTR_DEVICE_ID): cv.string,
            vol.Required("key"): vol.In(sorted(set(REMOTE_KEY_OPTIONS.values()))),
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_IP_PARAMETER, set_ip_parameter,
        schema=vol.Schema({
            vol.Required(ATTR_DEVICE_ID): cv.string,
            vol.Required("parameter"): vol.In(
                ["ip_address", "subnet", "gateway", "dns1", "dns2"]
            ),
            vol.Optional("value"): cv.string,
            vol.Optional("dhcp", default=False): cv.boolean,
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_MONITOR_ID, set_monitor_id,
        schema=vol.Schema({
            vol.Required(ATTR_DEVICE_ID): cv.string,
            vol.Required("new_monitor_id"): vol.All(int, vol.Range(min=1, max=255)),
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_FAILOVER, set_failover,
        schema=vol.Schema({
            vol.Required(ATTR_DEVICE_ID): cv.string,
            vol.Required("sources"): [vol.All(int, vol.Range(min=0, max=0x1F))],
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RESET_SCHEDULER, reset_scheduler,
        schema=vol.Schema({
            vol.Required(ATTR_DEVICE_ID): cv.string,
            vol.Optional("page", default=0): vol.All(int, vol.Range(min=0, max=7)),
        }),
    )
