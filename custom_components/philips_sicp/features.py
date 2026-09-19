"""Declarative registry of SICP commands mapped to Home Assistant entities.

Every entry here is reverse engineered directly from "The SICP Commands
Document V2.10". Commands whose payload is "one command code + N
independent fixed-width fields" (the large majority of the document) are
expressed as a single `Feature` with one `FieldSpec` per field, and are
turned into entities generically by the platform modules.

A handful of commands do not fit that shape at all (Date, Failover
priority lists, Tiling, Scheduling, IP Parameters, ...) because their
encoding is either variable-length, addressed by a selector byte that
isn't echoed back, or otherwise irregular. Those are handled by
dedicated codec functions in composite.py instead of being forced into
this table.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FieldKind = Literal["enum", "number", "ascii"]
Platform = Literal[
    "select", "number", "switch", "sensor", "binary_sensor", "button"
]


# --------------------------------------------------------------------------
# Shared option tables
# --------------------------------------------------------------------------

INPUT_SOURCE_OPTIONS: dict[int, str] = {
    0x01: "Video",
    0x02: "S-Video",
    0x03: "Component",
    0x05: "VGA",
    0x06: "HDMI 2",
    0x07: "DisplayPort 2",
    0x08: "USB 2",
    0x09: "Card DVI-D",
    0x0A: "DisplayPort",
    0x0B: "Card OPS",
    0x0C: "USB",
    0x0D: "HDMI",
    0x0E: "DVI-D",
    0x0F: "HDMI 3",
    0x10: "Browser",
    0x11: "SmartCMS",
    0x12: "DMS",
    0x13: "Internal Storage",
    0x16: "Media Player",
    0x17: "PDF Player",
    0x18: "Custom",
    0x19: "HDMI 4",
    0x1A: "VGA 2",
    0x1B: "VGA 3",
    0x1C: "IWB",
    0x1D: "CMND & Play Web",
    0x1E: "Home / Launcher",
    0x1F: "USB Type-C",
    0x20: "Kiosk",
    0x21: "Smart Info",
    0x22: "Tuner",
    0x23: "Google Cast",
    0x24: "Interact",
    0x25: "USB Type-C 2",
}

BOOT_SOURCE_OPTIONS: dict[int, str] = {0x00: "Last input", **INPUT_SOURCE_OPTIONS}

FAILOVER_SOURCE_OPTIONS: dict[int, str] = {
    0x00: "HDMI",
    0x01: "Component",
    0x02: "Composite",
    0x03: "DisplayPort",
    0x04: "DVI-D",
    0x05: "VGA",
    0x06: "OPS",
    0x07: "USB",
    0x08: "Browser",
    0x09: "SmartCMS",
    0x0A: "Internal Storage",
    0x0B: "DMS",
    0x0C: "HDMI 2",
    0x0D: "HDMI 3",
    0x0E: "USB Playlist",
    0x0F: "USB AutoPlay",
    0x10: "Media Player",
    0x11: "PDF Player",
    0x12: "Custom",
    0x13: "HDMI 4",
    0x14: "VGA 2",
    0x15: "VGA 3",
    0x16: "IWB",
    0x17: "CMND & Play Web",
    0x18: "Home / Launcher",
    0x19: "USB Type-C",
    0x1A: "Kiosk",
    0x1B: "Smart Info",
    0x1C: "Tuner",
    0x1D: "Google Cast",
    0x1E: "Interact",
    0x1F: "USB Type-C 2",
}

TIME_ZONE_OPTIONS: dict[int, str] = {
    0x01: "Pacific/Midway", 0x02: "Pacific/Honolulu", 0x03: "America/Anchorage",
    0x04: "America/Los_Angeles", 0x05: "America/Tijuana", 0x06: "America/Phoenix",
    0x07: "America/Chihuahua", 0x08: "America/Denver", 0x09: "America/Costa_Rica",
    0x0A: "America/Chicago", 0x0B: "America/Mexico_City", 0x0C: "America/Regina",
    0x0D: "America/Bogota", 0x0E: "America/New_York", 0x0F: "America/Caracas",
    0x10: "America/Barbados", 0x11: "America/Halifax", 0x12: "America/Manaus",
    0x13: "America/Santiago", 0x14: "America/St_Johns", 0x15: "America/Sao_Paulo",
    0x16: "America/Argentina/Buenos_Aires", 0x17: "America/Godthab",
    0x18: "America/Montevideo", 0x19: "Atlantic/South_Georgia", 0x1A: "Atlantic/Azores",
    0x1B: "Atlantic/Cape_Verde", 0x1C: "Africa/Casablanca", 0x1D: "Europe/London",
    0x1E: "Europe/Amsterdam", 0x1F: "Europe/Belgrade", 0x20: "Europe/Brussels",
    0x21: "Europe/Sarajevo", 0x22: "Africa/Windhoek", 0x23: "Africa/Brazzaville",
    0x24: "Asia/Amman", 0x25: "Europe/Athens", 0x26: "Asia/Beirut", 0x27: "Africa/Cairo",
    0x28: "Europe/Helsinki", 0x29: "Asia/Jerusalem", 0x2A: "Africa/Harare",
    0x2B: "Europe/Minsk", 0x2C: "Asia/Baghdad", 0x2D: "Europe/Moscow", 0x2E: "Asia/Kuwait",
    0x2F: "Africa/Nairobi", 0x30: "Asia/Tehran", 0x31: "Asia/Baku", 0x32: "Asia/Tbilisi",
    0x33: "Asia/Yerevan", 0x34: "Asia/Dubai", 0x35: "Asia/Kabul", 0x36: "Asia/Karachi",
    0x37: "Asia/Oral", 0x38: "Asia/Yekaterinburg", 0x39: "Asia/Calcutta",
    0x3A: "Asia/Colombo", 0x3B: "Asia/Katmandu", 0x3C: "Asia/Almaty",
    0x3D: "Asia/Rangoon", 0x3E: "Asia/Krasnoyarsk", 0x3F: "Asia/Bangkok",
    0x40: "Asia/Jakarta", 0x41: "Asia/Shanghai", 0x42: "Asia/Hong_Kong",
    0x43: "Asia/Irkutsk", 0x44: "Asia/Kuala_Lumpur", 0x45: "Australia/Perth",
    0x46: "Asia/Taipei", 0x47: "Asia/Seoul", 0x48: "Asia/Tokyo", 0x49: "Asia/Yakutsk",
    0x4A: "Australia/Adelaide", 0x4B: "Australia/Darwin", 0x4C: "Australia/Brisbane",
    0x4D: "Australia/Hobart", 0x4E: "Australia/Sydney", 0x4F: "Asia/Vladivostok",
    0x50: "Pacific/Guam", 0x51: "Asia/Magadan", 0x52: "Pacific/Majuro",
    0x53: "Pacific/Auckland", 0x54: "Pacific/Fiji", 0x55: "Pacific/Tongatapu",
}

LANGUAGE_OPTIONS: dict[int, str] = {
    0x01: "English", 0x02: "Español", 0x03: "Français", 0x04: "Italiano",
    0x05: "Latviešu", 0x06: "Lietuvių", 0x07: "Nederlands", 0x08: "Norsk bokmål",
    0x09: "Polski", 0x0A: "Português", 0x0B: "Suomi", 0x0C: "Svenska",
    0x0D: "Türkçe", 0x0E: "Pyccкий", 0x0F: "Arabic", 0x10: "Simplified Chinese",
    0x11: "Traditional Chinese", 0x12: "Japanese", 0x13: "Čeština", 0x14: "Dansk",
    0x15: "Deutsch", 0x16: "Eesti", 0x17: "Ελληνικά",
}

REMOTE_KEY_OPTIONS: dict[int, str] = {
    0x00: "0", 0x01: "1", 0x02: "2", 0x03: "3", 0x04: "4", 0x05: "5", 0x06: "6",
    0x07: "7", 0x08: "8", 0x09: "9", 0x0A: "back", 0x0D: "mute", 0x0F: "info",
    0x10: "volume_up", 0x11: "volume_down", 0x28: "forward", 0x2B: "rewind",
    0x2C: "play", 0x30: "pause", 0x31: "stop", 0x38: "sources", 0x40: "options",
    0x54: "home", 0x58: "up", 0x59: "down", 0x5A: "left", 0x5B: "right",
    0x5C: "ok", 0x6D: "red", 0x6E: "green", 0x6F: "yellow", 0x70: "blue",
    0x8B: "list", 0x90: "adjust", 0xBE: "power_on", 0xBF: "power_off",
    0xF5: "format",
}

GAMMA_OPTIONS = {
    0x01: "Native", 0x02: "S gamma", 0x03: "2.2", 0x04: "2.4", 0x05: "DICOM",
}

COLOR_TEMPERATURE_OPTIONS = {
    0x00: "User 1", 0x01: "Native", 0x03: "10000K", 0x04: "9300K", 0x05: "7500K",
    0x06: "6500K", 0x09: "5000K", 0x0A: "4000K", 0x0D: "3000K", 0x12: "User 2",
}


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldSpec:
    """One value inside a (possibly multi-field) command payload."""

    key: str
    name: str
    kind: FieldKind = "number"
    options: dict[int, str] | None = None
    min_value: int = 0
    max_value: int = 255
    unit: str | None = None
    step: int = 1
    width: int = 1  # bytes; only 1 or 2 supported for numeric fields
    invert: bool = False  # for 2-option booleans where 0 == "on"
    no_change: int | None = None  # Set-side sentinel meaning "leave as is"
    platform: Platform = "sensor"
    diagnostic: bool = False

    def decode(self, raw: bytes) -> int | str:
        if self.kind == "ascii":
            return raw.decode("ascii", errors="replace").rstrip("\x00")
        value = int.from_bytes(raw, "big")
        if self.invert:
            value = 1 - value
        return value

    def encode(self, value: int | str) -> bytes:
        if self.kind == "ascii":
            text = str(value)
            data = text.encode("ascii")
            return data[: self.width] if self.width > 1 else data
        ivalue = int(value)
        if self.invert:
            ivalue = 1 - ivalue
        return ivalue.to_bytes(self.width, "big")


@dataclass(frozen=True)
class Feature:
    """A single SICP command, decomposed into one or more FieldSpecs."""

    key: str
    name: str
    category: str
    get_code: int | None
    set_code: int | None
    fields: tuple[FieldSpec, ...]
    get_extra: bytes = b""  # extra bytes sent after Data[0] on a Get (selectors)
    min_sicp_version: tuple[int, int] | None = None
    platform_note: str | None = None
    probe_safe: bool = True  # False = pure action, cannot be probed via Get
    ascii_width: int | None = None  # for single ascii fields spanning "the rest"

    def decode_report(self, data: bytes) -> dict[str, int | str]:
        """Decode Data[1:] (i.e. everything after the echoed command code)."""
        result: dict[str, int | str] = {}
        offset = 0
        for spec in self.fields:
            width = (
                (len(data) - offset) if spec.kind == "ascii" else spec.width
            )
            chunk = data[offset : offset + width]
            if len(chunk) < width:
                break
            result[spec.key] = spec.decode(chunk)
            offset += width
        return result

    def encode_set(self, values: dict[str, int | str]) -> bytes:
        """Build Data[0:] for a Set command from a values dict.

        Fields missing from `values` fall back to their `no_change`
        sentinel when the command supports one, otherwise to 0.
        """
        assert self.set_code is not None
        out = bytearray([self.set_code])
        for spec in self.fields:
            if spec.key in values:
                out += spec.encode(values[spec.key])
            elif spec.no_change is not None:
                out += spec.no_change.to_bytes(spec.width, "big")
            else:
                out += bytes(spec.width)
        return bytes(out)

    @property
    def single_field(self) -> FieldSpec | None:
        return self.fields[0] if len(self.fields) == 1 else None


def _f(key: str, name: str, kind: str = "number", **kwargs) -> FieldSpec:
    return FieldSpec(key=key, name=name, kind=kind, **kwargs)


def _pct(key: str, name: str, no_change: int | None = None) -> FieldSpec:
    return _f(key, name, "number", min_value=0, max_value=100, unit="%",
              platform="number", no_change=no_change)


def _enum(key: str, name: str, options: dict[int, str], **kwargs) -> FieldSpec:
    return _f(key, name, "enum", options=options, platform="select", **kwargs)


def _bool(key: str, name: str, invert: bool = False, **kwargs) -> FieldSpec:
    return _f(key, name, "enum", options={0: "Off", 1: "On"}, platform="switch",
              invert=invert, **kwargs)


# --------------------------------------------------------------------------
# Feature registry
# --------------------------------------------------------------------------

FEATURES: tuple[Feature, ...] = (
    # ---- 3. Display Information (read only) -----------------------------
    Feature("model_number", "Model Number", "diagnostic", 0xA1, None,
            (_f("value", "Model Number", "ascii", platform="sensor", diagnostic=True),),
            get_extra=b"\x00"),
    Feature("fw_version", "Firmware Version", "diagnostic", 0xA1, None,
            (_f("value", "Firmware Version", "ascii", platform="sensor", diagnostic=True),),
            get_extra=b"\x01"),
    Feature("build_date", "Build Date", "diagnostic", 0xA1, None,
            (_f("value", "Build Date", "ascii", platform="sensor", diagnostic=True),),
            get_extra=b"\x02"),
    Feature("android_fw_version", "Android Firmware Version", "diagnostic", 0xA1, None,
            (_f("value", "Android Firmware Version", "ascii", platform="sensor", diagnostic=True),),
            get_extra=b"\x03"),
    Feature("hdmi_switch_version", "HDMI Switch Firmware Version", "diagnostic", 0xA1, None,
            (_f("value", "HDMI Switch Firmware Version", "ascii", platform="sensor", diagnostic=True),),
            get_extra=b"\x04"),
    Feature("lan_fw_version", "LAN Firmware Version", "diagnostic", 0xA1, None,
            (_f("value", "LAN Firmware Version", "ascii", platform="sensor", diagnostic=True),),
            get_extra=b"\x05"),
    Feature("hdmi_switch2_version", "HDMI Switch 2 Firmware Version", "diagnostic", 0xA1, None,
            (_f("value", "HDMI Switch 2 Firmware Version", "ascii", platform="sensor", diagnostic=True),),
            get_extra=b"\x06", min_sicp_version=(2, 10)),
    Feature("sicp_version", "SICP Version", "diagnostic", 0xA2, None,
            (_f("value", "SICP Version", "ascii", platform="sensor", diagnostic=True),),
            get_extra=b"\x00"),
    Feature("platform_label", "Platform Label", "diagnostic", 0xA2, None,
            (_f("value", "Platform Label", "ascii", platform="sensor", diagnostic=True),),
            get_extra=b"\x01"),
    Feature("platform_version", "Platform Version", "diagnostic", 0xA2, None,
            (_f("value", "Platform Version", "ascii", platform="sensor", diagnostic=True),),
            get_extra=b"\x02"),
    Feature("operating_hours", "Operating Hours", "diagnostic", 0x0F, None,
            (_f("value", "Operating Hours", "number", width=2, unit="h",
                platform="sensor", diagnostic=True, max_value=65535),),
            get_extra=b"\x02"),
    Feature("temperature_1", "Temperature Sensor 1", "diagnostic", 0x2F, None,
            (_f("value", "Temperature Sensor 1", "number", unit="°C",
                platform="sensor", max_value=100),),),
    Feature("serial_number", "Serial Number", "diagnostic", 0x15, None,
            (_f("value", "Serial Number", "ascii", platform="sensor", diagnostic=True),),),
    Feature("video_signal_present", "Video Signal Present", "diagnostic", 0x59, None,
            (_f("value", "Video Signal Present", "enum",
                options={0: "Off", 1: "On"}, platform="binary_sensor"),),
            min_sicp_version=(2, 3)),

    # ---- 4. Power ---------------------------------------------------------
    # power_state and input_source (below, under Inputs) are consumed
    # directly by media_player.py for a proper power/source UI rather
    # than being exposed a second time as generic select entities - see
    # CLAIMED_BY_MEDIA_PLAYER.
    Feature("power_state", "Power State", "power", 0x19, 0x18,
            (_enum("value", "Power State", {1: "Off", 2: "On"}),)),
    Feature("power_cold_start", "Power State at Cold Start", "power", 0xA4, 0xA3,
            (_enum("value", "Power State at Cold Start",
                   {0: "Off", 1: "Forced On", 2: "Last Status"}),)),
    Feature("power_save_mode", "Power Save Mode", "power", 0xD3, 0xD2,
            (_enum("value", "Power Save Mode", {
                0: "RGB Off & Video Off", 1: "RGB Off, Video On",
                2: "RGB On, Video Off", 3: "RGB On & Video On",
                4: "Mode 1", 5: "Mode 2", 6: "Mode 3", 7: "Mode 4"}),)),
    Feature("smart_power", "Smart Power", "power", 0xDE, 0xDD,
            (_enum("value", "Smart Power",
                   {0: "Off", 1: "Low", 2: "Medium", 3: "High"}),)),
    Feature("advanced_power_management", "Advanced Power Management", "power", 0xD1, 0xD0,
            (_enum("value", "Advanced Power Management", {
                0: "Off", 1: "On", 2: "Mode 1 (TCP off / WOL on)",
                3: "Mode 2 (TCP on / WOL off)"}),),
            platform_note="Himalaya: Off/Mode1/Mode2 only. Eagle 1.3: On/Off only."),
    Feature("eco_mode", "ECO Mode", "power", 0x63, 0x64,
            (_bool("value", "ECO Mode"),), min_sicp_version=(2, 0)),
    Feature("backlight", "Backlight", "power", 0x71, 0x72,
            (_bool("value", "Backlight", invert=True),), min_sicp_version=(2, 3)),
    Feature("ops_sdm_power", "OPS/SDM Power", "power", 0x6E, 0x6F,
            (_enum("value", "OPS/SDM Power",
                   {0: "Always Off", 1: "Always On", 2: "Auto"}),),
            min_sicp_version=(2, 8)),

    # ---- 5. Inputs ----------------------------------------------------
    Feature("input_source", "Input Source", "input", 0xAD, 0xAC,
            (_enum("source", "Input Source", INPUT_SOURCE_OPTIONS),
             _f("tag", "Playlist/URL Tag", "number", max_value=8, platform="number"),
             _f("_osd_style", "OSD Style", "number", platform="sensor", diagnostic=True),
             _f("_mute_style", "Mute Style", "number", platform="sensor", diagnostic=True)),),
    Feature("boot_source", "Boot on Source", "input", 0xBA, 0xBB,
            (_enum("source", "Boot on Source", BOOT_SOURCE_OPTIONS),
             _f("tag", "Bookmark/Playlist Tag", "number", max_value=8,
                platform="number")),
            min_sicp_version=(2, 5)),
    Feature("auto_signal_detection", "Auto Signal Detection", "input", 0xAF, 0xAE,
            (_enum("value", "Auto Signal Detection", {
                0: "Off", 1: "All", 3: "PC sources only",
                4: "Video sources only", 5: "Failover"}),)),
    Feature("pip_mode", "Picture-in-Picture", "picture", 0x3D, 0x3C,
            (_enum("mode", "PIP Mode", {
                0: "Off", 1: "On (PIP)", 2: "POP", 3: "Quick swap",
                4: "PBP 2 windows", 5: "PBP 3 windows", 6: "PBP 4 windows",
                7: "PBP 3 windows (1)", 8: "PBP 3 windows (2)",
                9: "PBP 4 windows (1)", 10: "Custom (SICP)"}),
             _enum("position", "PIP Position", {
                 0: "Bottom left", 1: "Top left", 2: "Top right",
                 3: "Bottom right", 4: "Center"}),
             _f("_reserved1", "Reserved", "number", platform="sensor", diagnostic=True),
             _f("_reserved2", "Reserved", "number", platform="sensor", diagnostic=True)),
            platform_note=("Eagle 1.3: On/Off only. Himalaya 1.x/1.2: modes 0-6 only. "
                            "Dragon 1.x/1.5/1.6: 0/1/3/4/10 only. Phoenix: unsupported.")),

    # ---- 6. Audio -----------------------------------------------------
    Feature("volume", "Volume", "audio", 0x45, 0x44,
            (_pct("speaker", "Speaker Volume", no_change=0xFF),
             _pct("line_out", "Line Out Volume", no_change=0xFF)),
            platform_note="Speaker-only on HIMALAYA 1.0/1.2 and Eagle platforms."),
    Feature("mute", "Mute", "audio", 0x46, 0x47, (_bool("value", "Mute"),),
            min_sicp_version=(2, 0)),
    Feature("speaker_volume_limits", "Speaker Volume Limits", "audio", 0xB6, 0xB8,
            (_pct("min", "Speaker Min Volume"), _pct("max", "Speaker Max Volume"),
             _pct("switch_on", "Speaker Switch-on Volume")),
            min_sicp_version=(1, 88)),
    Feature("audio_out_volume_limits", "Audio Out Volume Limits", "audio", 0xB7, 0xB9,
            (_pct("min", "Audio Out Min Volume"), _pct("max", "Audio Out Max Volume"),
             _pct("switch_on", "Audio Out Switch-on Volume")),
            min_sicp_version=(1, 88)),
    Feature("speakers_on_off", "Speakers", "audio", 0x8F, 0x8E,
            (_bool("value", "Speakers"),), min_sicp_version=(2, 7)),
    Feature("audio_sync", "Audio Sync", "audio", 0x8D, 0x8C,
            (_bool("value", "Audio Sync"),), min_sicp_version=(2, 7)),
    Feature("audio_parameters", "Audio Parameters", "audio", 0x43, 0x42,
            (_pct("treble", "Treble"), _pct("bass", "Bass")),
            platform_note="Range is -8..8 (not 0-100%) on Phoenix 2.0 platform."),

    # ---- 7. Control -----------------------------------------------------
    Feature("remote_control_lock", "Remote Control Lock", "control", 0x1D, 0x1C,
            (_enum("value", "Remote Control Lock", {
                1: "Unlock all", 2: "Lock all", 3: "Lock all but power",
                4: "Lock all but volume", 5: "Primary (master)",
                6: "Secondary (daisy chain)", 7: "Lock all except power & volume"}),)),
    Feature("keypad_lock", "Keypad Lock", "control", 0x1B, 0x1A,
            (_enum("value", "Keypad Lock", {
                1: "Unlock all", 2: "Lock all", 3: "Lock all but power",
                4: "Lock all but volume", 7: "Lock all except power & volume"}),)),
    Feature("rs232_routing", "RS232 Routing", "control", 0x9A, 0x9B,
            (_enum("value", "RS232 Routing",
                   {0: "RS232", 1: "LAN > RS232", 2: "Card-OPS > RS232"}),),
            min_sicp_version=(2, 7)),
    Feature("sicp_serial_forwarding", "SICP Serial Port Forwarding", "control", 0xBE, 0xBF,
            (_bool("value", "SICP Serial Port Forwarding"),),
            min_sicp_version=(2, 7), platform_note="CRD50 only."),
    Feature("hdmi_cec", "HDMI One Wire (CEC)", "control", 0xBC, 0xBD,
            (_enum("value", "HDMI One Wire (CEC)", {
                0x00: "Off", 0x01: "On", 0x11: "On + power off"}),),
            min_sicp_version=(2, 7)),
    Feature("touch_lock", "Touch Lock", "control", 0x1F, 0x1E,
            (_enum("value", "Touch Lock", {
                0x00: "Locked (with PIN)", 0x01: "Unlocked",
                0x10: "Locked (no PIN)"}),)),
    Feature("navigation_bar", "Navigation Bar", "control", 0x74, 0x75,
            (_enum("value", "Navigation Bar",
                   {0: "Always off", 1: "Always on", 2: "Auto hide"}),),
            min_sicp_version=(2, 4)),
    Feature("teamviewer", "TeamViewer", "control", 0x93, 0x94,
            (_bool("value", "TeamViewer"),), min_sicp_version=(2, 7)),
    Feature("light_sensor", "Light Sensor", "control", 0x25, 0x24,
            (_bool("value", "Light Sensor"),), platform_note="Requires CRD41 or internal sensor."),
    Feature("human_sensor", "Human Sensor", "control", 0xB3, 0xB4,
            (_enum("value", "Human Sensor Timeout", {
                0: "Off", 1: "10 min", 2: "20 min", 3: "30 min", 4: "40 min",
                5: "50 min", 6: "60 min"}),),
            min_sicp_version=(1, 99), platform_note="Requires CRD41 or internal sensor."),
    Feature("off_timer", "Off Timer", "control", 0x91, 0x92,
            (_f("value", "Off Timer", "number", min_value=0, max_value=24,
                unit="h", platform="number"),),
            min_sicp_version=(1, 99)),
    Feature("wake_on_lan", "Wake on LAN", "control", 0x9C, 0x9D,
            (_bool("value", "Wake on LAN"),), min_sicp_version=(2, 7)),
    Feature("group_id", "Group ID", "control", 0x5D, 0x5C,
            (_f("value", "Group ID", "number", min_value=1, max_value=254,
                platform="number", diagnostic=True),),
            min_sicp_version=(1, 86)),

    # ---- 8. Picture -----------------------------------------------------
    Feature("freeze_image", "Freeze Image", "picture", 0x76, 0x77,
            (_bool("value", "Freeze Image"),), min_sicp_version=(2, 6)),
    Feature("av_mute", "A/V Mute", "picture", 0x7A, 0x7B,
            (_bool("value", "A/V Mute"),), min_sicp_version=(2, 9)),
    Feature("osd_rotation", "OSD Rotation", "picture", 0x27, 0x26,
            (_bool("value", "OSD Rotation"),)),
    Feature("switch_on_delay", "Switch On Delay", "picture", 0x55, 0x54,
            (_f("value", "Switch On Delay", "number", min_value=0, max_value=255,
                unit="s", platform="number"),)),
    Feature("picture_style", "Picture Style", "picture", 0x65, 0x66,
            (_enum("value", "Picture Style", {
                0: "Highbright", 1: "sRGB", 2: "Vivid", 3: "Natural",
                4: "Standard", 5: "Video", 6: "Static Signage", 7: "Text",
                8: "Energy saving", 9: "Soft", 10: "User"}),),
            min_sicp_version=(2, 3)),
    Feature("video_parameters", "Video Parameters", "picture", 0x33, 0x32,
            (_pct("brightness", "Brightness", no_change=0xFF),
             _pct("color", "Color", no_change=0xFF),
             _pct("contrast", "Contrast", no_change=0xFF),
             _pct("sharpness", "Sharpness", no_change=0xFF),
             _pct("tint", "Tint", no_change=0xFF),
             _pct("black_level", "Black Level", no_change=0xFF),
             _enum("gamma", "Gamma", GAMMA_OPTIONS, no_change=0xFF)),
            platform_note=("0xFF 'no change' on Set requires SICP 2.09+. Sharpness/tint "
                            "range and units differ on Phoenix 2.0.")),
    Feature("color_temperature", "Color Temperature", "picture", 0x35, 0x34,
            (_enum("value", "Color Temperature", COLOR_TEMPERATURE_OPTIONS),)),
    Feature("color_temperature_100k", "Color Temperature (100K steps)", "picture", 0x12, 0x11,
            (_f("value", "Color Temperature", "number", min_value=20, max_value=100,
                unit="00K", platform="number"),),
            platform_note='Only active while Color Temperature is "User 2".'),
    Feature("rgb_parameters", "RGB Parameters", "picture", 0x37, 0x36,
            (_f("red_gain", "Red Gain", "number", max_value=255, platform="number"),
             _f("green_gain", "Green Gain", "number", max_value=255, platform="number"),
             _f("blue_gain", "Blue Gain", "number", max_value=255, platform="number"),
             _f("red_offset", "Red Offset", "number", max_value=255, platform="number"),
             _f("green_offset", "Green Offset", "number", max_value=255, platform="number"),
             _f("blue_offset", "Blue Offset", "number", max_value=255, platform="number")),
            platform_note='Only active while Color Temperature is "User 1". Not on QL3 for internal sources.'),
    Feature("picture_format", "Picture Format", "picture", 0x3B, 0x3A,
            (_enum("value", "Picture Format", {
                0: "Normal (4:3)", 1: "Custom", 2: "Real (1:1)", 3: "Full",
                4: "21:9", 5: "Dynamic", 6: "16:9"}),),
            platform_note="Dynamic (5) unsupported on 2016 Dragon 1.0."),
    Feature("hdmi_input_range", "HDMI Input Range", "picture", 0x6A, 0x6B,
            (_enum("value", "HDMI Input Range",
                   {1: "Auto", 2: "Limited (PC)", 3: "Full (Video)"}),),
            min_sicp_version=(2, 6)),
    Feature("scan_mode", "Scan Mode", "picture", 0x51, 0x50,
            (_enum("value", "Scan Mode",
                   {0: "Overscan", 1: "Underscan", 2: "Off"}),)),
    Feature("scan_conversion", "Scan Conversion", "picture", 0x53, 0x52,
            (_enum("value", "Scan Conversion",
                   {0: "Progressive", 1: "Interlace"}),)),
    Feature("memc", "MEMC", "picture", 0x29, 0x28,
            (_enum("value", "MEMC",
                   {0: "Off", 1: "Low", 2: "Medium", 3: "High"}),)),
    Feature("noise_reduction", "Noise Reduction", "picture", 0x2B, 0x2A,
            (_enum("value", "Noise Reduction",
                   {0: "Off", 1: "Low", 2: "Middle", 3: "High", 4: "Default"}),)),
    Feature("pixel_shift", "Pixel Shift", "picture", 0xB1, 0xB2,
            (_enum("value", "Pixel Shift", {
                0: "Off", 1: "10s", 2: "20s", 3: "30s", 4: "40s", 5: "50s",
                0x5A: "900s", 0x5B: "Auto"}),),
            min_sicp_version=(1, 99),
            platform_note="Intermediate 10s steps between 40s and 900s omitted for brevity; raw range is 0x00-0x5B."),
    Feature("test_pattern", "Test Pattern", "picture", 0x6C, 0x6D,
            (_enum("value", "Test Pattern", {
                0: "Off", 1: "White 100%", 2: "Red", 3: "Green", 4: "Blue",
                5: "Black", 6: "Half white (top)", 7: "Half white (bottom)",
                8: "Ramp", 9: "White 12%", 10: "White 25%", 11: "White 65%"}),),
            min_sicp_version=(2, 6)),
    Feature("vga_parameters", "VGA Parameters", "picture", 0x39, 0x38,
            (_pct("clock", "VGA Clock"), _pct("clock_phase", "VGA Clock Phase"),
             _pct("h_position", "VGA H Position"), _pct("v_position", "VGA V Position")),),

    # ---- 9. Date & Time ---------------------------------------------------
    Feature("clock", "Clock", "datetime", 0x87, 0x86,
            (_f("hour", "Hour", "number", min_value=0, max_value=23, platform="number"),
             _f("minute", "Minute", "number", min_value=0, max_value=59, platform="number")),
            min_sicp_version=(2, 7),
            platform_note="Set only takes effect while Auto Time Sync is off."),
    Feature("auto_time_sync", "Auto Time Sync", "datetime", 0x89, 0x88,
            (_bool("value", "Auto Time Sync"),), min_sicp_version=(2, 7)),
    Feature("time_zone", "Time Zone", "datetime", 0x8B, 0x8A,
            (_enum("value", "Time Zone", TIME_ZONE_OPTIONS),), min_sicp_version=(2, 7)),
    Feature("auto_restart", "Auto Restart", "misc", 0x9E, 0x9F,
            (_bool("enabled", "Auto Restart Enabled"),
             _f("hour", "Restart Hour", "number", min_value=0, max_value=24, platform="number"),
             _f("minute", "Restart Minute", "number", min_value=0, max_value=60, platform="number")),
            min_sicp_version=(2, 7)),

    # ---- 11. Miscellaneous ------------------------------------------------
    Feature("power_on_logo", "Power On Logo", "misc", 0x3F, 0x3E,
            (_enum("value", "Power On Logo",
                   {0: "Off", 1: "On", 2: "User"}),)),
    Feature("external_storage_lock", "External Storage Lock", "misc", 0xF2, 0xF1,
            (_bool("value", "External Storage Lock"),)),
    Feature("information_osd", "Information OSD Duration", "misc", 0x2D, 0x2C,
            (_f("value", "Information OSD Duration", "number", min_value=0,
                max_value=60, unit="s", platform="number"),)),
    Feature("osd_language", "OSD Language", "misc", 0xA7, 0xA8,
            (_enum("value", "OSD Language", LANGUAGE_OPTIONS),), min_sicp_version=(2, 7)),
    Feature("power_led", "Power LED", "misc", 0x48, 0x49,
            (_bool("value", "Power LED"),), min_sicp_version=(2, 8)),
    Feature("force_restart_custom_app", "Force Restart Custom App", "misc", 0x78, 0x79,
            (_bool("value", "Force Restart Custom App"),), min_sicp_version=(2, 8)),
    Feature("fan_speed", "Fan Speed", "misc", 0x62, 0x61,
            (_enum("value", "Fan Speed",
                   {0: "Off", 1: "Auto", 2: "Low", 3: "Middle", 4: "High"}),),
            min_sicp_version=(1, 87)),
    Feature("factory_color_calibration", "Factory Color Calibration", "misc", 0x31, 0x30,
            (_enum("value", "Factory Color Calibration",
                   {0: "Off", 1: "Locked", 2: "Adjustable"}),),
            min_sicp_version=(2, 9)),
)

FEATURES_BY_KEY: dict[str, Feature] = {f.key: f for f in FEATURES}

# These are polled and written directly by media_player.py, which gives
# them a proper power switch / source list / volume slider UI. The
# generic select/sensor/switch platforms skip them to avoid duplicate
# entities for the same underlying command.
CLAIMED_BY_MEDIA_PLAYER: frozenset[str] = frozenset(
    {"power_state", "input_source", "volume", "mute"}
)
