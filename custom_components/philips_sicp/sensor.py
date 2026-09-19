"""Read-only diagnostic/status sensors, generated from the Feature registry
plus a handful of composite values that don't fit that model (Failover
priority list, IP parameters, tuner channel)."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SICPDisplayCoordinator
from .entity import SICPEntity
from .features import CLAIMED_BY_MEDIA_PLAYER, FEATURES, FieldSpec, Feature

_COMPOSITE_SENSORS: tuple[tuple[str, str, bool], ...] = (
    # (composite key, friendly name, diagnostic)
    ("failover", "Failover Priority", True),
    ("channel", "Tuner Channel", False),
    ("ip_address", "IP Address", True),
    ("ip_subnet", "Subnet Mask", True),
    ("ip_gateway", "Gateway", True),
    ("ip_dns1", "DNS 1", True),
    ("ip_dns2", "DNS 2", True),
    ("ip_ethernet_mac", "Ethernet MAC", True),
    ("ip_wifi_mac", "Wi-Fi MAC", True),
)


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
                if spec.platform == "sensor":
                    entities.append(SICPFieldSensor(coordinator, feature, spec))
        for key, name, diagnostic in _COMPOSITE_SENSORS:
            if coordinator.supports(key):
                entities.append(SICPCompositeSensor(coordinator, key, name, diagnostic))
    async_add_entities(entities)


class SICPFieldSensor(SICPEntity, SensorEntity):
    def __init__(self, coordinator: SICPDisplayCoordinator, feature: Feature, spec: FieldSpec) -> None:
        super().__init__(coordinator, f"{feature.key}_{spec.key}")
        self._feature = feature
        self._spec = spec
        self._attr_name = spec.name if feature.single_field else f"{feature.name} {spec.name}"
        self._attr_native_unit_of_measurement = spec.unit
        if spec.diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        raw = self.coordinator.field_value(self._feature.key, self._spec.key)
        if raw is None:
            return None
        if self._spec.options:
            return self._spec.options.get(raw, raw)
        return raw


class SICPCompositeSensor(SICPEntity, SensorEntity):
    def __init__(self, coordinator: SICPDisplayCoordinator, key: str, name: str, diagnostic: bool) -> None:
        super().__init__(coordinator, f"composite_{key}")
        self._key = key
        self._attr_name = name
        if diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        value = (self.coordinator.data or {}).get(self._key)
        if isinstance(value, list):
            return ", ".join(value)
        return value
