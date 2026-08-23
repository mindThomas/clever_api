"""Binary sensors for Clever smart charging."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CleverApiUpdateCoordinator
from .entity import CleverApiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CleverApiUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.data.home_installation is not None:
        async_add_entities(
            [
                CleverSmartChargingBinarySensor(coordinator),
                CleverChargingBinarySensor(coordinator),
                CleverVehicleConnectedBinarySensor(coordinator),
            ]
        )


class CleverSmartChargingBinarySensor(CleverApiEntity, BinarySensorEntity):
    """Whether intelligent charging is enabled for the home charger."""

    _attr_name = "Intelligent charging"
    _attr_translation_key = "intelligent_charging"
    _attr_icon = "mdi:ev-station"

    def __init__(self, coordinator: CleverApiUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.data.profile.customer_id}_intelligent_charging"
        )

    @property
    def is_on(self) -> bool:
        profile = self.coordinator.data.home_charging_profile
        if profile is not None:
            return profile.enabled
        installation = self.coordinator.data.home_installation
        return bool(installation and installation.smart_charging.enabled)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        profile = self.coordinator.data.home_charging_profile
        installation = self.coordinator.data.home_installation
        settings = installation.smart_charging if installation else None
        return {
            "planned_departure": (
                profile.departure_time
                if profile
                else settings.departure_time
                if settings
                else None
            ),
            "desired_range": (
                profile.power_required
                if profile
                else settings.power_required
                if settings
                else None
            ),
            "configured_phase_count": settings.phase_count if settings else None,
            "preheat_enabled": (
                profile.preheat_minutes > 0
                if profile
                else bool(settings and settings.preheat_minutes > 0)
            ),
        }


class CleverChargingBinarySensor(CleverApiEntity, BinarySensorEntity):
    """Whether the home charger is actively charging."""

    _attr_name = "Charging"
    _attr_translation_key = "charging"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def __init__(self, coordinator: CleverApiUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.data.profile.customer_id}_charging"

    @property
    def is_on(self) -> bool:
        transaction = self.coordinator.data.active_home_transaction
        return bool(transaction and transaction.status.casefold() == "charging")


class CleverVehicleConnectedBinarySensor(CleverApiEntity, BinarySensorEntity):
    """Whether a vehicle is connected to the home charger."""

    _attr_name = "Vehicle connected"
    _attr_translation_key = "vehicle_connected"
    _attr_device_class = BinarySensorDeviceClass.PLUG

    def __init__(self, coordinator: CleverApiUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.data.profile.customer_id}_vehicle_connected"
        )

    @property
    def is_on(self) -> bool:
        transaction = self.coordinator.data.active_home_transaction
        if transaction is None:
            return False
        plugged_in = transaction.vehicle_is_plugged_in
        return True if plugged_in is None else plugged_in
