"""The RGB LED strip found on 10BDLxx51T-family displays (chapter 11.8)."""
from __future__ import annotations

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import composite
from .const import DOMAIN
from .coordinator import SICPDisplayCoordinator
from .entity import SICPEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinators: list[SICPDisplayCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SICPLedStripLight(c) for c in coordinators if c.supports("led_strip")
    )


class SICPLedStripLight(SICPEntity, LightEntity):
    _attr_name = "LED Strip"
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    def __init__(self, coordinator: SICPDisplayCoordinator) -> None:
        super().__init__(coordinator, "led_strip")

    @property
    def _data(self) -> dict:
        return (self.coordinator.data or {}).get("led_strip") or {}

    @property
    def is_on(self) -> bool | None:
        return self._data.get("on")

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        return self._data.get("rgb")

    async def async_turn_on(self, rgb_color: tuple[int, int, int] | None = None, **kwargs) -> None:
        color = rgb_color or self._data.get("rgb") or (255, 255, 255)
        await self.coordinator.async_write_composite(
            "led_strip", composite.set_led_strip, on=True, rgb=tuple(color)
        )

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_write_composite("led_strip", composite.set_led_strip, on=False)
