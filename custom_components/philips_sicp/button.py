"""One-shot action commands that can't be safely probed via a Get (there
is no read-side to them), so they are offered unconditionally as
buttons. The genuinely destructive ones (factory reset, clear storage,
firmware upgrade) are disabled by default so a user has to deliberately
enable them in the entity registry before they show up."""
from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import composite
from .const import CONF_ADMIN_PIN, DOMAIN
from .coordinator import SICPDisplayCoordinator
from .entity import SICPEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinators: list[SICPDisplayCoordinator] = hass.data[DOMAIN][entry.entry_id]
    entities: list[SICPEntity] = []
    for coordinator in coordinators:
        entities.append(RestartButton(coordinator))
        entities.append(ScreenshotButton(coordinator))
        entities.append(VgaAutoAdjustButton(coordinator))
        entities.append(AdminMenuButton(coordinator, entry))
        entities.append(ClearStorageButton(coordinator))
        entities.append(FactoryResetButton(coordinator))
        entities.append(FirmwareUpgradeButton(coordinator))
    async_add_entities(entities)


class _ActionButton(SICPEntity, ButtonEntity):
    def __init__(self, coordinator: SICPDisplayCoordinator, key: str, name: str) -> None:
        super().__init__(coordinator, key)
        self._attr_name = name
        self._attr_entity_category = EntityCategory.CONFIG


class RestartButton(_ActionButton):
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(self, coordinator: SICPDisplayCoordinator) -> None:
        super().__init__(coordinator, "restart_android", "Restart Android")

    async def async_press(self) -> None:
        await composite.restart_monitor(
            self.coordinator.client, self.coordinator.monitor_id, self.coordinator.group_id, "android"
        )


class ScreenshotButton(_ActionButton):
    def __init__(self, coordinator: SICPDisplayCoordinator) -> None:
        super().__init__(coordinator, "take_screenshot", "Take Screenshot")

    async def async_press(self) -> None:
        await composite.take_screenshot(
            self.coordinator.client, self.coordinator.monitor_id, self.coordinator.group_id
        )


class VgaAutoAdjustButton(_ActionButton):
    def __init__(self, coordinator: SICPDisplayCoordinator) -> None:
        super().__init__(coordinator, "vga_auto_adjust", "VGA Auto Adjust")

    async def async_press(self) -> None:
        await composite.vga_auto_adjust(
            self.coordinator.client, self.coordinator.monitor_id, self.coordinator.group_id
        )


class AdminMenuButton(_ActionButton):
    def __init__(self, coordinator: SICPDisplayCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, "open_admin_menu", "Open Admin Menu")
        self._entry = entry

    async def async_press(self) -> None:
        pin = self._entry.options.get(CONF_ADMIN_PIN)
        await composite.open_admin_menu(
            self.coordinator.client, self.coordinator.monitor_id, self.coordinator.group_id, pin
        )


class ClearStorageButton(_ActionButton):
    """Clears all USB/SD/internal 'philips' storage folders. Disabled by
    default: this is destructive and takes no confirmation dialog."""

    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: SICPDisplayCoordinator) -> None:
        super().__init__(coordinator, "clear_storage", "Clear Storage (All)")

    async def async_press(self) -> None:
        await composite.clear_storage(
            self.coordinator.client, self.coordinator.monitor_id, self.coordinator.group_id, "all"
        )


class FactoryResetButton(_ActionButton):
    """Factory-resets the scaler. Disabled by default - this cannot be
    undone from Home Assistant."""

    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: SICPDisplayCoordinator) -> None:
        super().__init__(coordinator, "factory_reset_scaler", "Factory Reset (Scaler)")

    async def async_press(self) -> None:
        await composite.factory_reset(
            self.coordinator.client, self.coordinator.monitor_id, self.coordinator.group_id, "scaler"
        )


class FirmwareUpgradeButton(_ActionButton):
    """Starts an Android firmware upgrade from update.zip already staged
    on the display's internal storage. Disabled by default."""

    _attr_device_class = ButtonDeviceClass.UPDATE
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: SICPDisplayCoordinator) -> None:
        super().__init__(coordinator, "start_firmware_upgrade", "Start Firmware Upgrade")

    async def async_press(self) -> None:
        await composite.start_firmware_upgrade(
            self.coordinator.client, self.coordinator.monitor_id, self.coordinator.group_id
        )
