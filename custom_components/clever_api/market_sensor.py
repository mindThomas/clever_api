"""Read-only app prices and published energy surcharge history.

These entities are intentionally not used by the charging coordinator.
"""

from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .clever.exceptions import CleverError
from .clever.market import prices, surcharges

LOGGER = logging.getLogger(__name__)


class CleverMarketCoordinator(DataUpdateCoordinator):
    def __init__(self, charging, kind, address_id=None):
        self.client = charging.client
        self.kind = kind
        self.address_id = address_id
        super().__init__(charging.hass, LOGGER, config_entry=charging.config_entry,
                         name=f"Clever {kind}", update_interval=timedelta(
                             minutes=20 if kind == "prices" else 1440))

    async def _async_update_data(self):
        today = dt_util.now().date()
        try:
            if self.kind == "prices":
                payload = await self.client.get_electricity_prices(
                    self.address_id, today, today + timedelta(days=1))
                rows = prices(payload)
            else:
                rows = surcharges(await self.client.get_historical_energy_surcharges(
                    today.replace(year=today.year - 2, month=1, day=1), today))
            if not rows:
                raise ValueError("No published data")
            return {"records": rows, "updated_at": dt_util.utcnow().isoformat()}
        except (CleverError, ValueError, TypeError, KeyError) as err:
            raise UpdateFailed(f"Clever {self.kind} unavailable ({type(err).__name__})") from err


class CleverMarketSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "DKK/kWh"
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator, customer_id):
        super().__init__(coordinator)
        identity = coordinator.address_id or "account"
        self._attr_unique_id = f"{customer_id}_market_{coordinator.kind}_{identity}"
        self._attr_device_info = {"identifiers": {("clever_api", customer_id)}}
        self._attr_name = ("Elpris fra app" if coordinator.kind == "prices"
                           else "Seneste offentliggjorte energitillaeg")

    @property
    def native_value(self):
        rows = (self.coordinator.data or {}).get("records", [])
        if self.coordinator.kind == "surcharges":
            return rows[-1]["price"] if rows else None
        now = dt_util.utcnow()
        return next((r["price"] for r in rows
                     if dt_util.parse_datetime(r["start"]) <= now < dt_util.parse_datetime(r["end"])), None)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        rows = data.get("records", [])
        if self.coordinator.kind == "prices":
            return {"prices": rows, "updated_at": data.get("updated_at"),
                    "source": "Clever app API", "used_for_charging_control": False}
        return {"history": rows, "period": rows[-1]["start"][:7] if rows else None,
                "updated_at": data.get("updated_at"),
                "description": "Seneste offentliggjorte maaned; ikke et estimat for indevaerende maaned.",
                "used_for_charging_control": False}


async def async_setup_market_sensors(charging, async_add_entities):
    customer = charging.data.profile.customer_id
    # Surcharge history also works for customers without a Power agreement.
    coordinator = CleverMarketCoordinator(charging, "surcharges")
    await coordinator.async_refresh()
    async_add_entities([CleverMarketSensor(coordinator, customer)])
    try:
        agreements = await charging.client.get_power_engagements()
        addresses = {g["darReferenceId"] for g in agreements if g.get("darReferenceId")
                     and any(not m.get("endDate") for m in g.get("powerMeterEngagementInfos", []))}
    except (CleverError, KeyError, TypeError):
        LOGGER.warning("Clever app price discovery failed; charging is unaffected")
        return
    for address in addresses:
        coordinator = CleverMarketCoordinator(charging, "prices", address)
        await coordinator.async_refresh()
        async_add_entities([CleverMarketSensor(coordinator, customer)])
