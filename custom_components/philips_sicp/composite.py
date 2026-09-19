"""Codecs for SICP commands that don't fit the Feature/FieldSpec model.

Each function here talks to a `protocol.SICPClient` directly and returns
plain Python values. These back either a small number of bespoke entities
(see number.py/switch.py/light.py/button.py) or the `philips_sicp.*`
services registered in __init__.py, for commands that are too niche,
too variable-length, or too dangerous (network/firmware/factory-reset)
to wire up as a one-tap entity.
"""
from __future__ import annotations

from .features import FAILOVER_SOURCE_OPTIONS
from .protocol import SICPClient


# ---------------------------------------------------------------------------
# 9.1 Date - the two "year" bytes are not a plain big-endian integer; the
# worked examples in the spec only make sense as year = byte4 * 100 + byte3.
# ---------------------------------------------------------------------------

async def get_date(client: SICPClient, monitor_id: int, group: int) -> dict:
    data = await client.request(monitor_id, group, bytes([0x95]), expect_code=0x95)
    day, month, year_b3, year_b4 = data[0], data[1], data[2], data[3]
    return {"day": day, "month": month, "year": year_b4 * 100 + year_b3}


async def set_date(client: SICPClient, monitor_id: int, group: int,
                    day: int, month: int, year: int) -> None:
    year_b3 = year % 100
    year_b4 = year // 100
    await client.request(
        monitor_id, group, bytes([0x96, day, month, year_b3, year_b4])
    )


# ---------------------------------------------------------------------------
# 5.5 Failover priority list (variable length, 14-17 bytes)
# ---------------------------------------------------------------------------

async def get_failover(client: SICPClient, monitor_id: int, group: int) -> list[str]:
    data = await client.request(monitor_id, group, bytes([0xA6]), expect_code=0xA6)
    return [FAILOVER_SOURCE_OPTIONS.get(b, f"0x{b:02X}") for b in data]


async def set_failover(client: SICPClient, monitor_id: int, group: int,
                        sources: list[int]) -> None:
    if not 1 <= len(sources) <= 14:
        raise ValueError("Failover priority list must have 1-14 entries")
    await client.request(monitor_id, group, bytes([0xA5, *sources]))


# ---------------------------------------------------------------------------
# 8.5 Tiling - DATA[4] packs H/V monitor count via a formula, and 0x00 on
# Set means "don't overwrite" for most fields, so it can't share the
# generic Feature no_change handling (0 is also a legitimate "No").
# ---------------------------------------------------------------------------

async def get_tiling(client: SICPClient, monitor_id: int, group: int) -> dict:
    data = await client.request(monitor_id, group, bytes([0x23]), expect_code=0x23)
    enable, frame_comp, position, hv = data[0], data[1], data[2], data[3]
    h_monitors = hv % 15 if hv else 0
    v_monitors = (hv // 15) + 1 if hv else 0
    return {
        "enabled": bool(enable),
        "frame_compensation": bool(frame_comp),
        "position": position,
        "h_monitors": h_monitors,
        "v_monitors": v_monitors,
    }


async def set_tiling(client: SICPClient, monitor_id: int, group: int, *,
                      enabled: bool, frame_compensation: bool | None = None,
                      position: int | None = None,
                      h_monitors: int | None = None,
                      v_monitors: int | None = None) -> None:
    frame_byte = 2 if frame_compensation is None else int(frame_compensation)
    position_byte = 0 if position is None else position
    if h_monitors is not None and v_monitors is not None:
        hv_byte = (v_monitors - 1) * 15 + h_monitors
    else:
        hv_byte = 0  # don't overwrite
    await client.request(
        monitor_id, group,
        bytes([0x22, int(enabled), frame_byte, position_byte, hv_byte]),
    )


# ---------------------------------------------------------------------------
# 8.7 Frame Compensation - Horizontal (0x5E/0x5F) and Vertical (0x67/0x68)
# each take a selector byte (0=combined, 1=left/top, 2=right/bottom) that
# IS echoed back in the report, ahead of the actual 0-100 value.
# ---------------------------------------------------------------------------

async def get_frame_compensation(client: SICPClient, monitor_id: int, group: int,
                                  *, vertical: bool, selector: int) -> int:
    code = 0x67 if vertical else 0x5E
    data = await client.request(
        monitor_id, group, bytes([code, selector]), expect_code=code
    )
    return data[1]


async def set_frame_compensation(client: SICPClient, monitor_id: int, group: int,
                                  *, vertical: bool, selector: int, value: int) -> None:
    code = 0x68 if vertical else 0x5F
    await client.request(monitor_id, group, bytes([code, selector, value]))


# ---------------------------------------------------------------------------
# 8.20 Stretch
# ---------------------------------------------------------------------------

async def get_stretch(client: SICPClient, monitor_id: int, group: int) -> dict:
    data = await client.request(monitor_id, group, bytes([0x4D]), expect_code=0x4D)
    enabled = bool(data[0])
    raw = data[1] if len(data) > 1 else 0
    value = None if raw in (0x00, 0xFF) else raw * 10
    return {"enabled": enabled, "value": value}


async def set_stretch(client: SICPClient, monitor_id: int, group: int,
                       *, enabled: bool, value: int | None = None) -> None:
    raw = 0 if value is None else max(1, min(0x36, round(value / 10)))
    await client.request(monitor_id, group, bytes([0x40, int(enabled), raw]))


# ---------------------------------------------------------------------------
# 8.4 Image Rotation
# ---------------------------------------------------------------------------

async def get_image_rotation(client: SICPClient, monitor_id: int, group: int) -> dict:
    data = await client.request(monitor_id, group, bytes([0x16]), expect_code=0x16)
    keys = ["auto_rotate", "osd_portrait", "image_all", "main", "sub1", "sub2", "sub3"]
    return {k: v for k, v in zip(keys, data)}


async def set_image_rotation(client: SICPClient, monitor_id: int, group: int, **fields) -> None:
    order = ["auto_rotate", "osd_portrait", "image_all", "main", "sub1", "sub2", "sub3"]
    payload = [fields.get(k, 0) for k in order]
    await client.request(monitor_id, group, bytes([0x17, *payload]))


# ---------------------------------------------------------------------------
# 11.8 RGB LED Strip (10BDLxx51T) - exposed as a light entity.
# ---------------------------------------------------------------------------

async def get_led_strip(client: SICPClient, monitor_id: int, group: int) -> dict:
    data = await client.request(monitor_id, group, bytes([0xF4]), expect_code=0xF4)
    return {"on": bool(data[0]), "rgb": (data[1], data[2], data[3])}


async def set_led_strip(client: SICPClient, monitor_id: int, group: int, *,
                         on: bool, rgb: tuple[int, int, int] = (255, 255, 255)) -> None:
    await client.request(monitor_id, group, bytes([0xF3, int(on), *rgb]))


# ---------------------------------------------------------------------------
# 5.9 / 5.10 Tuner channel (only relevant on displays with an internal tuner)
# ---------------------------------------------------------------------------

async def get_channel(client: SICPClient, monitor_id: int, group: int) -> int:
    data = await client.request(monitor_id, group, bytes([0xC1]), expect_code=0xC1)
    return data[0] * 256 + data[1]


async def set_channel(client: SICPClient, monitor_id: int, group: int, channel: int) -> None:
    await client.request(monitor_id, group, bytes([0xC2, channel // 256, channel % 256]))


async def step_channel(client: SICPClient, monitor_id: int, group: int, up: bool) -> None:
    await client.request(monitor_id, group, bytes([0xC3, int(up)]))


# ---------------------------------------------------------------------------
# 7.13 IP Parameters - read side only; the Set side can strand the display
# off the network if misused, so it is only reachable via the
# philips_sicp.set_ip_parameter service (see __init__.py), never a plain
# entity, and callers must opt in explicitly.
# ---------------------------------------------------------------------------

_IP_PARAM_SELECTORS = {
    "ip_address": 0x01, "subnet": 0x02, "gateway": 0x03,
    "dns1": 0x04, "dns2": 0x05, "ethernet_mac": 0x06, "wifi_mac": 0x07,
}


async def get_ip_parameter(client: SICPClient, monitor_id: int, group: int,
                            parameter: str) -> str:
    selector = _IP_PARAM_SELECTORS[parameter]
    data = await client.request(
        monitor_id, group, bytes([0x82, selector]), expect_code=0x82
    )
    raw = data[3:].decode("ascii", errors="replace")
    if parameter in ("ethernet_mac", "wifi_mac"):
        return ":".join(raw[i : i + 2] for i in range(0, len(raw), 2))
    return ".".join(raw[i : i + 3].lstrip("0") or "0" for i in range(0, len(raw), 3))


async def set_ip_parameter(client: SICPClient, monitor_id: int, group: int, *,
                            parameter: str, value: str, dhcp: bool = False,
                            confirm: bool = True) -> None:
    selector = _IP_PARAM_SELECTORS[parameter]
    if dhcp:
        digits = "0" * 12
        dhcp_byte = 0x00
    else:
        octets = value.split(".") if "." in value else value.split(":")
        width = 3 if "." in value else 2
        digits = "".join(o.zfill(width) for o in octets)
        dhcp_byte = 0xFF
    await client.request(
        monitor_id, group,
        bytes([0x81, dhcp_byte, int(confirm), selector, *digits.encode("ascii")]),
    )


# ---------------------------------------------------------------------------
# 7.2 Remote control key simulation
# ---------------------------------------------------------------------------

async def send_remote_key(client: SICPClient, monitor_id: int, group: int, key: int) -> None:
    await client.request(monitor_id, group, bytes([0xFE, key, 0x00]))


# ---------------------------------------------------------------------------
# 7.8 Admin menu (PIN required on SICP >= 2.10)
# ---------------------------------------------------------------------------

async def open_admin_menu(client: SICPClient, monitor_id: int, group: int,
                           pin: str | None = None) -> None:
    if pin:
        digits = [ord(c) for c in pin[:6]]
        await client.request(monitor_id, group, bytes([0x73, *digits]))
    else:
        await client.request(monitor_id, group, bytes([0x73]))


# ---------------------------------------------------------------------------
# 7.15 / 7.16 addressing - Monitor ID is Set-only and re-addresses the
# physical display, so changing it is only ever done explicitly via a
# service call (see __init__.py), never a plain entity.
# ---------------------------------------------------------------------------

async def set_monitor_id(client: SICPClient, monitor_id: int, group: int,
                          new_monitor_id: int) -> None:
    await client.request(monitor_id, group, bytes([0x69, new_monitor_id]))


# ---------------------------------------------------------------------------
# Simple one-shot actions (button entities in button.py)
# ---------------------------------------------------------------------------

async def restart_monitor(client: SICPClient, monitor_id: int, group: int,
                           target: str = "android") -> None:
    await client.request(monitor_id, group, bytes([0x57, 0 if target == "android" else 1]))


async def take_screenshot(client: SICPClient, monitor_id: int, group: int) -> None:
    await client.request(monitor_id, group, bytes([0x58]))


async def vga_auto_adjust(client: SICPClient, monitor_id: int, group: int) -> None:
    await client.request(monitor_id, group, bytes([0x70, 0x40, 0x00]))


async def clear_storage(client: SICPClient, monitor_id: int, group: int,
                         target: str = "all") -> None:
    codes = {"all": 0x00, "internal": 0x01, "usb": 0x02, "sd": 0x03}
    await client.request(monitor_id, group, bytes([0x2E, codes[target]]))


async def factory_reset(client: SICPClient, monitor_id: int, group: int,
                         target: str = "scaler") -> None:
    codes = {"scaler": 0x01, "android": 0x02}
    await client.request(monitor_id, group, bytes([0x56, codes[target]]))


async def start_firmware_upgrade(client: SICPClient, monitor_id: int, group: int) -> None:
    await client.request(monitor_id, group, bytes([0x20, 0x00]))


async def reset_scheduler(client: SICPClient, monitor_id: int, group: int,
                           page: int = 0) -> None:
    await client.request(monitor_id, group, bytes([0x60, page]))


# ---------------------------------------------------------------------------
# Fixed-arity wrappers so the coordinator's generic probe/poll loop can
# call every composite getter with the same (client, monitor_id, group)
# signature, for the ones that otherwise need extra selector arguments.
# ---------------------------------------------------------------------------

def _frame_wrapper(vertical: bool, selector: int):
    async def _get(client: SICPClient, monitor_id: int, group: int) -> int | None:
        return await get_frame_compensation(
            client, monitor_id, group, vertical=vertical, selector=selector
        )

    return _get


get_frame_h_combined = _frame_wrapper(False, 0)
get_frame_h_left = _frame_wrapper(False, 1)
get_frame_h_right = _frame_wrapper(False, 2)
get_frame_v_combined = _frame_wrapper(True, 0)
get_frame_v_top = _frame_wrapper(True, 1)
get_frame_v_bottom = _frame_wrapper(True, 2)


def _ip_wrapper(parameter: str):
    async def _get(client: SICPClient, monitor_id: int, group: int) -> str:
        return await get_ip_parameter(client, monitor_id, group, parameter)

    return _get


get_ip_address = _ip_wrapper("ip_address")
get_ip_subnet = _ip_wrapper("subnet")
get_ip_gateway = _ip_wrapper("gateway")
get_ip_dns1 = _ip_wrapper("dns1")
get_ip_dns2 = _ip_wrapper("dns2")
get_ip_ethernet_mac = _ip_wrapper("ethernet_mac")
get_ip_wifi_mac = _ip_wrapper("wifi_mac")
