"""Shared base entity: one DeviceInfo per Monitor ID."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import SICPDisplayCoordinator


class SICPEntity(CoordinatorEntity[SICPDisplayCoordinator]):
    """Base class giving every entity a consistent unique_id/device_info."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SICPDisplayCoordinator, unique_key: str) -> None:
        super().__init__(coordinator)
        self._unique_key = unique_key
        self._attr_unique_id = f"{coordinator.serial_number}_{unique_key}"

    @property
    def device_info(self) -> DeviceInfo:
        coordinator = self.coordinator
        return DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial_number)},
            name=coordinator.display_name,
            manufacturer=MANUFACTURER,
            model=coordinator.model,
            serial_number=coordinator.serial_number,
            sw_version=coordinator.sw_version,
            hw_version=coordinator.hw_version,
        )
