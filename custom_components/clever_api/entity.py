"""Base entity for the Clever API integration."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CleverApiUpdateCoordinator


class CleverApiEntity(CoordinatorEntity[CleverApiUpdateCoordinator]):
    """Base class shared by all Clever entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CleverApiUpdateCoordinator) -> None:
        super().__init__(coordinator)
        installation = coordinator.data.home_installation
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.profile.customer_id)},
            manufacturer="Clever",
            name="Clever",
            model=installation.model if installation else "Subscription",
        )
