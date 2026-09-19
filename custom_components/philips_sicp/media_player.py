"""Media player entity: power, input source, volume and mute."""
from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SICPDisplayCoordinator
from .entity import SICPEntity
from .features import INPUT_SOURCE_OPTIONS


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinators: list[SICPDisplayCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(SICPMediaPlayer(c) for c in coordinators)


class SICPMediaPlayer(SICPEntity, MediaPlayerEntity):
    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.TV

    def __init__(self, coordinator: SICPDisplayCoordinator) -> None:
        super().__init__(coordinator, "media_player")

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        features = MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
        if self.coordinator.supports("input_source"):
            features |= MediaPlayerEntityFeature.SELECT_SOURCE
        if self.coordinator.supports("volume"):
            features |= (
                MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_STEP
            )
        if self.coordinator.supports("mute"):
            features |= MediaPlayerEntityFeature.VOLUME_MUTE
        return features

    @property
    def state(self) -> MediaPlayerState | None:
        is_on = self.coordinator.is_on
        if is_on is None:
            return None
        return MediaPlayerState.ON if is_on else MediaPlayerState.OFF

    @property
    def source(self) -> str | None:
        code = self.coordinator.current_source_code
        return INPUT_SOURCE_OPTIONS.get(code) if code is not None else None

    @property
    def source_list(self) -> list[str]:
        return list(INPUT_SOURCE_OPTIONS.values())

    @property
    def volume_level(self) -> float | None:
        return self.coordinator.volume

    @property
    def is_volume_muted(self) -> bool | None:
        return self.coordinator.is_muted

    async def async_turn_on(self) -> None:
        await self.coordinator.async_set_power(True)

    async def async_turn_off(self) -> None:
        await self.coordinator.async_set_power(False)

    async def async_select_source(self, source: str) -> None:
        for code, name in INPUT_SOURCE_OPTIONS.items():
            if name == source:
                await self.coordinator.async_select_source(code)
                return

    async def async_set_volume_level(self, volume: float) -> None:
        await self.coordinator.async_set_volume(volume)

    async def async_volume_up(self) -> None:
        current = self.coordinator.volume or 0
        await self.coordinator.async_set_volume(min(1.0, current + 0.02))

    async def async_volume_down(self) -> None:
        current = self.coordinator.volume or 0
        await self.coordinator.async_set_volume(max(0.0, current - 0.02))

    async def async_mute_volume(self, mute: bool) -> None:
        await self.coordinator.async_set_mute(mute)
