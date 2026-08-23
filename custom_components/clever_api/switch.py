"""Switch controls for Clever smart charging."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
            [CleverPreheatSwitch(coordinator), CleverBoostSwitch(coordinator)]
        )


class CleverPreheatSwitch(CleverApiEntity, SwitchEntity):
    """Enable or disable preheating in the home charging profile."""

    _attr_name = "Preheat"
    _attr_translation_key = "preheat"
    _attr_icon = "mdi:radiator"

    def __init__(self, coordinator: CleverApiUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.data.profile.customer_id}_preheat"

    @property
    def is_on(self) -> bool:
        profile = self.coordinator.data.home_charging_profile
        return bool(profile and profile.preheat_minutes > 0)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_preheat(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_preheat(False)

    async def _set_preheat(self, enable: bool) -> None:
        profile = self.coordinator.data.home_charging_profile
        if profile is None:
            raise HomeAssistantError("No Clever home charging profile is available")
        await self.coordinator.client.set_preheat(profile.profile_id, enable)
        await self.coordinator.async_refresh_configuration()


class CleverBoostSwitch(CleverApiEntity, SwitchEntity):
    """Temporarily bypass intelligent charging for the active session."""

    _attr_name = "Skip intelligent charging"
    _attr_translation_key = "boost"
    _attr_icon = "mdi:fast-forward"

    def __init__(self, coordinator: CleverApiUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.data.profile.customer_id}_boost"

    @property
    def is_on(self) -> bool:
        transaction = self.coordinator.data.active_home_transaction
        return bool(transaction and transaction.is_boosted_at(datetime.now(UTC)))

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data.active_home_transaction is not None
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        installation = self.coordinator.data.home_installation
        if installation is None:
            raise HomeAssistantError("No Clever home charger is available")
        await self.coordinator.client.boost(
            installation.charge_box_id, installation.connector_id
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        installation = self.coordinator.data.home_installation
        if installation is None:
            raise HomeAssistantError("No Clever home charger is available")
        await self.coordinator.client.unboost(
            installation.charge_box_id, installation.connector_id
        )
        await self.coordinator.async_request_refresh()
