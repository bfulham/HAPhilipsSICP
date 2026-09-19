"""Switch entities: Feature registry boolean fields plus a few composite
booleans (Tiling enable/frame-compensation, Stretch enable, Image
Rotation's per-window and auto-rotate flags)."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import composite
from .const import DOMAIN
from .coordinator import SICPDisplayCoordinator
from .entity import SICPEntity
from .features import CLAIMED_BY_MEDIA_PLAYER, FEATURES, Feature, FieldSpec

_IMAGE_ROTATION_SWITCHES = (
    ("auto_rotate", "Auto Rotate"),
    ("osd_portrait", "OSD Portrait"),
    ("main", "Rotate Main Window"),
    ("sub1", "Rotate Sub Window 1"),
    ("sub2", "Rotate Sub Window 2"),
    ("sub3", "Rotate Sub Window 3"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinators: list[SICPDisplayCoordinator] = hass.data[DOMAIN][entry.entry_id]
    entities: list[SICPEntity] = []
    for coordinator in coordinators:
        for feature in FEATURES:
            if feature.key in CLAIMED_BY_MEDIA_PLAYER or feature.set_code is None:
                continue
            if not coordinator.supports(feature.key):
                continue
            for spec in feature.fields:
                if spec.platform == "switch":
                    entities.append(SICPFieldSwitch(coordinator, feature, spec))

        if coordinator.supports("tiling"):
            entities.append(TilingSwitch(coordinator, "enabled", "Tiling Enabled"))
            entities.append(TilingSwitch(coordinator, "frame_compensation", "Tiling Frame Compensation"))
        if coordinator.supports("stretch"):
            entities.append(StretchSwitch(coordinator))
        if coordinator.supports("image_rotation"):
            for field, name in _IMAGE_ROTATION_SWITCHES:
                entities.append(ImageRotationSwitch(coordinator, field, name))
    async_add_entities(entities)


class SICPFieldSwitch(SICPEntity, SwitchEntity):
    def __init__(self, coordinator: SICPDisplayCoordinator, feature: Feature, spec: FieldSpec) -> None:
        super().__init__(coordinator, f"{feature.key}_{spec.key}")
        self._feature = feature
        self._spec = spec
        self._attr_name = spec.name if feature.single_field else f"{feature.name} {spec.name}"

    @property
    def is_on(self) -> bool | None:
        raw = self.coordinator.field_value(self._feature.key, self._spec.key)
        return None if raw is None else bool(raw)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_write_feature(self._feature.key, **{self._spec.key: 1})

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_write_feature(self._feature.key, **{self._spec.key: 0})


class TilingSwitch(SICPEntity, SwitchEntity):
    def __init__(self, coordinator: SICPDisplayCoordinator, field: str, name: str) -> None:
        super().__init__(coordinator, f"tiling_{field}")
        self._field = field
        self._attr_name = name

    @property
    def is_on(self) -> bool | None:
        return ((self.coordinator.data or {}).get("tiling") or {}).get(self._field)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_write_composite("tiling", composite.set_tiling, **{self._field: True})

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_write_composite("tiling", composite.set_tiling, **{self._field: False})


class StretchSwitch(SICPEntity, SwitchEntity):
    _attr_name = "Stretch"

    def __init__(self, coordinator: SICPDisplayCoordinator) -> None:
        super().__init__(coordinator, "stretch_enabled")

    @property
    def is_on(self) -> bool | None:
        return ((self.coordinator.data or {}).get("stretch") or {}).get("enabled")

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_write_composite("stretch", composite.set_stretch, enabled=True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_write_composite("stretch", composite.set_stretch, enabled=False)


class ImageRotationSwitch(SICPEntity, SwitchEntity):
    def __init__(self, coordinator: SICPDisplayCoordinator, field: str, name: str) -> None:
        super().__init__(coordinator, f"image_rotation_{field}")
        self._field = field
        self._attr_name = name

    @property
    def is_on(self) -> bool | None:
        value = ((self.coordinator.data or {}).get("image_rotation") or {}).get(self._field)
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_write_composite(
            "image_rotation", composite.set_image_rotation, **{self._field: 1}
        )

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_write_composite(
            "image_rotation", composite.set_image_rotation, **{self._field: 0}
        )
