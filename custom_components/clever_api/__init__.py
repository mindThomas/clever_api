"""Support for Clever subscriptions and home chargers."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

from .const import (
    CONF_DEPT_TIME,
    CONF_DESIRED_RANGE,
    CONF_PHASE_COUNT,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    SERVICE_DISABLE_FLEX,
    SERVICE_ENABLE_FLEX,
)
from .coordinator import CleverApiUpdateCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH]

SERVICE_ENABLE_FLEX_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEPT_TIME): vol.Match(r"^(?:[01]\d|2[0-3]):[0-5]\d$"),
        vol.Required(CONF_DESIRED_RANGE): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
        # Retained so existing automations remain valid. The v6 API no longer
        # exposes phase count as a charging-profile setting.
        vol.Optional(CONF_PHASE_COUNT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=3)
        ),
    }
)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove obsolete v1 tokens and require Firebase reauthentication."""
    if entry.version >= 2:
        return True
    data = dict(entry.data)
    for obsolete_key in ("api_key", "api_token", "url"):
        data.pop(obsolete_key, None)
    hass.config_entries.async_update_entry(entry, data=data, version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Clever from a config entry."""
    if not entry.data.get(CONF_REFRESH_TOKEN):
        raise ConfigEntryAuthFailed("Clever must be reauthenticated with a password")

    coordinator = CleverApiUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, SERVICE_ENABLE_FLEX):

        async def enable_flex(call: ServiceCall) -> None:
            profile = coordinator.data.home_charging_profile
            if profile is None:
                raise HomeAssistantError("No Clever home charging profile is available")
            await coordinator.client.set_departure_time(
                profile.profile_id, call.data[CONF_DEPT_TIME]
            )
            await coordinator.client.set_power_required(
                profile.profile_id, call.data[CONF_DESIRED_RANGE]
            )
            await coordinator.client.set_charging_profile_enabled(
                profile.profile_id, True
            )
            await coordinator.async_refresh_configuration()

        async def disable_flex(call: ServiceCall) -> None:
            profile = coordinator.data.home_charging_profile
            if profile is None:
                raise HomeAssistantError("No Clever home charging profile is available")
            await coordinator.client.set_charging_profile_enabled(
                profile.profile_id, False
            )
            await coordinator.async_refresh_configuration()

        hass.services.async_register(
            DOMAIN, SERVICE_ENABLE_FLEX, enable_flex, schema=SERVICE_ENABLE_FLEX_SCHEMA
        )
        hass.services.async_register(DOMAIN, SERVICE_DISABLE_FLEX, disable_flex)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Clever config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_ENABLE_FLEX)
            hass.services.async_remove(DOMAIN, SERVICE_DISABLE_FLEX)
            del hass.data[DOMAIN]
    return unload_ok
