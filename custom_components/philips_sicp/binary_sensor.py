"""Read-only boolean status entities generated from the Feature registry."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SICPDisplayCoordinator
from .entity import SICPEntity
from .features import CLAIMED_BY_MEDIA_PLAYER, FEATURES, Feature, FieldSpec


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinators: list[SICPDisplayCoordinator] = hass.data[DOMAIN][entry.entry_id]
    entities: list[SICPEntity] = []
    for coordinator in coordinators:
        for feature in FEATURES:
            if feature.key in CLAIMED_BY_MEDIA_PLAYER:
                continue
            if not coordinator.supports(feature.key):
                continue
            for spec in feature.fields:
                if spec.platform == "binary_sensor":
                    entities.append(SICPBinarySensor(coordinator, feature, spec))
    async_add_entities(entities)


class SICPBinarySensor(SICPEntity, BinarySensorEntity):
    def __init__(self, coordinator: SICPDisplayCoordinator, feature: Feature, spec: FieldSpec) -> None:
        super().__init__(coordinator, f"{feature.key}_{spec.key}")
        self._feature = feature
        self._spec = spec
        self._attr_name = spec.name if feature.single_field else f"{feature.name} {spec.name}"

    @property
    def is_on(self) -> bool | None:
        raw = self.coordinator.field_value(self._feature.key, self._spec.key)
        return None if raw is None else bool(raw)
