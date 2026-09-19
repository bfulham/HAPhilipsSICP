"""Select entities generated from the Feature registry's enum fields."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SICPDisplayCoordinator
from .entity import SICPEntity
from .features import CLAIMED_BY_MEDIA_PLAYER, FEATURES, Feature, FieldSpec

_IMAGE_ALL_OPTIONS = {0: "Off", 1: "On", 2: "Clockwise", 3: "Counter-clockwise"}


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
                if spec.platform == "select":
                    entities.append(SICPFieldSelect(coordinator, feature, spec))
        if coordinator.supports("image_rotation"):
            entities.append(SICPImageAllSelect(coordinator))
    async_add_entities(entities)


class SICPFieldSelect(SICPEntity, SelectEntity):
    def __init__(self, coordinator: SICPDisplayCoordinator, feature: Feature, spec: FieldSpec) -> None:
        super().__init__(coordinator, f"{feature.key}_{spec.key}")
        self._feature = feature
        self._spec = spec
        self._attr_name = spec.name if feature.single_field else f"{feature.name} {spec.name}"
        self._attr_options = list(spec.options.values())

    @property
    def current_option(self) -> str | None:
        raw = self.coordinator.field_value(self._feature.key, self._spec.key)
        return self._spec.options.get(raw) if raw is not None else None

    async def async_select_option(self, option: str) -> None:
        for code, label in self._spec.options.items():
            if label == option:
                await self.coordinator.async_write_feature(self._feature.key, **{self._spec.key: code})
                return


class SICPImageAllSelect(SICPEntity, SelectEntity):
    """The 'Image All' rotation mode inside the composite Image Rotation command."""

    _attr_name = "Image Rotation"

    def __init__(self, coordinator: SICPDisplayCoordinator) -> None:
        super().__init__(coordinator, "image_rotation_image_all")
        self._attr_options = list(_IMAGE_ALL_OPTIONS.values())

    @property
    def current_option(self) -> str | None:
        data = (self.coordinator.data or {}).get("image_rotation") or {}
        return _IMAGE_ALL_OPTIONS.get(data.get("image_all"))

    async def async_select_option(self, option: str) -> None:
        for code, label in _IMAGE_ALL_OPTIONS.items():
            if label == option:
                from . import composite

                await self.coordinator.async_write_composite(
                    "image_rotation", composite.set_image_rotation, image_all=code
                )
                return
