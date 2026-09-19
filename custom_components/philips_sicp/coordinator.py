"""Per-display polling, capability probing, and write helpers.

One instance of SICPDisplayCoordinator exists per configured Monitor ID.
Several coordinators typically share a single SICPClient/socket - this is
exactly what lets one config entry drive a LAN-connected display plus any
number of displays daisy-chained from it over RS232 (see protocol.py's
module docstring): they are just different Monitor IDs multiplexed over
the same TCP connection.

Capability detection is done once, right after connecting, by sending the
Get side of every command in the Feature registry and recording whether
it NAVs (unsupported on this platform/firmware), times out, or succeeds.
This is more reliable than trying to encode every "supported from SICP
2.xx onwards" / "Himalaya platform only" footnote in the spec as static
data: the display tells us directly what it actually implements.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import composite
from .features import FEATURES, FEATURES_BY_KEY
from .protocol import (
    SICPChecksumError,
    SICPClient,
    SICPConnectionError,
    SICPNotAvailableError,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL = timedelta(seconds=30)

# Composite (non-Feature) values that get probed/polled the same way as
# ordinary features, but are decoded by dedicated functions in
# composite.py instead of a declarative FieldSpec list. Each entry is
# (key, async_getter(client, monitor_id, group_id)).
_COMPOSITE_PROBES: tuple[tuple[str, Any], ...] = (
    ("date", composite.get_date),
    ("tiling", composite.get_tiling),
    ("stretch", composite.get_stretch),
    ("image_rotation", composite.get_image_rotation),
    ("led_strip", composite.get_led_strip),
    ("channel", composite.get_channel),
    ("failover", composite.get_failover),
    ("frame_h_combined", composite.get_frame_h_combined),
    ("frame_h_left", composite.get_frame_h_left),
    ("frame_h_right", composite.get_frame_h_right),
    ("frame_v_combined", composite.get_frame_v_combined),
    ("frame_v_top", composite.get_frame_v_top),
    ("frame_v_bottom", composite.get_frame_v_bottom),
    ("ip_address", composite.get_ip_address),
    ("ip_subnet", composite.get_ip_subnet),
    ("ip_gateway", composite.get_ip_gateway),
    ("ip_dns1", composite.get_ip_dns1),
    ("ip_dns2", composite.get_ip_dns2),
    ("ip_ethernet_mac", composite.get_ip_ethernet_mac),
    ("ip_wifi_mac", composite.get_ip_wifi_mac),
)


class SICPDisplayCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Polls and drives a single Monitor ID over a shared SICPClient."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: SICPClient,
        monitor_id: int,
        group_id: int,
        name: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"philips_sicp_{monitor_id}",
            update_interval=DEFAULT_POLL_INTERVAL,
        )
        self.entry = entry
        self.client = client
        self.monitor_id = monitor_id
        self.group_id = group_id
        self.display_name = name
        self.supported: set[str] = set()
        self.supported_composite: set[str] = set()
        self._probed = False

    # -- capability probing -------------------------------------------------

    async def async_probe_capabilities(self) -> None:
        """Send every Get command once and record what this display supports."""
        for feature in FEATURES:
            if feature.get_code is None:
                continue
            try:
                data = await self.client.request(
                    self.monitor_id,
                    self.group_id,
                    bytes([feature.get_code, *feature.get_extra]),
                    expect_code=feature.get_code,
                )
            except SICPNotAvailableError:
                _LOGGER.debug("%s: %s not supported (NAV)", self.display_name, feature.key)
                continue
            except (SICPChecksumError, SICPConnectionError) as err:
                _LOGGER.debug(
                    "%s: probing %s failed (%s), treating as unsupported for now",
                    self.display_name, feature.key, err,
                )
                continue
            self.supported.add(feature.key)
            self.data = self.data or {}
            self.data[feature.key] = feature.decode_report(data)

        for key, getter in _COMPOSITE_PROBES:
            try:
                value = await getter(self.client, self.monitor_id, self.group_id)
            except SICPNotAvailableError:
                continue
            except (SICPChecksumError, SICPConnectionError) as err:
                _LOGGER.debug(
                    "%s: probing composite %s failed (%s)", self.display_name, key, err
                )
                continue
            self.supported_composite.add(key)
            self.data = self.data or {}
            self.data[key] = value

        self._probed = True
        _LOGGER.info(
            "%s: detected %d/%d simple features, %d/%d composite features",
            self.display_name, len(self.supported), len(FEATURES),
            len(self.supported_composite), len(_COMPOSITE_PROBES),
        )

    def supports(self, key: str) -> bool:
        return key in self.supported or key in self.supported_composite

    # -- polling --------------------------------------------------------

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        if not self._probed:
            await self.async_probe_capabilities()
        data: dict[str, dict[str, Any]] = dict(self.data or {})
        for key in self.supported:
            feature = FEATURES_BY_KEY[key]
            try:
                raw = await self.client.request(
                    self.monitor_id,
                    self.group_id,
                    bytes([feature.get_code, *feature.get_extra]),
                    expect_code=feature.get_code,
                )
            except SICPNotAvailableError:
                # A feature can legitimately stop being available (e.g.
                # RGB Parameters only while Color Temperature == User 1).
                continue
            except (SICPChecksumError, SICPConnectionError) as err:
                raise UpdateFailed(f"{feature.name}: {err}") from err
            data[key] = feature.decode_report(raw)

        composite_getters = dict(_COMPOSITE_PROBES)
        for key in self.supported_composite:
            try:
                data[key] = await composite_getters[key](
                    self.client, self.monitor_id, self.group_id
                )
            except SICPNotAvailableError:
                continue
            except (SICPChecksumError, SICPConnectionError) as err:
                raise UpdateFailed(f"{key}: {err}") from err
        return data

    # -- writing ----------------------------------------------------------

    async def async_write_feature(self, key: str, **values: Any) -> None:
        """Merge `values` onto the cached fields for `key` and Set them all."""
        feature = FEATURES_BY_KEY[key]
        if feature.set_code is None:
            raise ValueError(f"{key} is read only")
        current = dict((self.data or {}).get(key, {}))
        current.update(values)
        payload = feature.encode_set(current)
        await self.client.request(self.monitor_id, self.group_id, payload)
        if self.data is None:
            self.data = {}
        self.data[key] = current
        self.async_set_updated_data(self.data)

    async def async_write_composite(self, key: str, setter, **kwargs: Any) -> None:
        """Call a composite.py setter, merging `kwargs` onto the cached dict
        for `key` first (when it is dict-shaped) so that writing one field
        of a multi-field composite (e.g. Tiling's h_monitors) doesn't reset
        the others - the same pattern as async_write_feature."""
        current = (self.data or {}).get(key)
        merged = {**current, **kwargs} if isinstance(current, dict) else kwargs
        await setter(self.client, self.monitor_id, self.group_id, **merged)
        composite_getters = dict(_COMPOSITE_PROBES)
        getter = composite_getters.get(key)
        if getter is not None:
            try:
                if self.data is None:
                    self.data = {}
                self.data[key] = await getter(self.client, self.monitor_id, self.group_id)
            except (SICPNotAvailableError, SICPChecksumError, SICPConnectionError):
                pass
        self.async_set_updated_data(self.data or {})

    def field_value(self, key: str, field: str = "value") -> Any:
        return ((self.data or {}).get(key) or {}).get(field)

    # -- media_player convenience helpers ----------------------------------

    @property
    def is_on(self) -> bool | None:
        value = self.field_value("power_state")
        return None if value is None else value == 2

    async def async_set_power(self, on: bool) -> None:
        await self.async_write_feature("power_state", value=2 if on else 1)

    @property
    def current_source_code(self) -> int | None:
        return self.field_value("input_source", "source")

    async def async_select_source(self, code: int) -> None:
        await self.async_write_feature("input_source", source=code, tag=0,
                                        _osd_style=1, _mute_style=0)

    @property
    def volume(self) -> int | None:
        value = self.field_value("volume", "speaker")
        return None if value is None else value / 100

    async def async_set_volume(self, level: float) -> None:
        await self.async_write_feature("volume", speaker=round(level * 100))

    @property
    def is_muted(self) -> bool | None:
        value = self.field_value("mute")
        return None if value is None else bool(value)

    async def async_set_mute(self, mute: bool) -> None:
        await self.async_write_feature("mute", value=int(mute))

    # -- device identity ----------------------------------------------------

    @property
    def model(self) -> str:
        return str(self.field_value("model_number") or "Unknown")

    @property
    def serial_number(self) -> str:
        return str(self.field_value("serial_number") or f"monitor-{self.monitor_id}")

    @property
    def sw_version(self) -> str | None:
        fw = self.field_value("fw_version")
        sicp = self.field_value("sicp_version")
        if fw and sicp:
            return f"{fw} (SICP {sicp})"
        return fw or sicp

    @property
    def hw_version(self) -> str | None:
        return self.field_value("platform_label")
