"""Independent, read-only Clever Power history sensors."""

from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .clever.exceptions import CleverError

LOGGER = logging.getLogger(__name__)


def consumption_rows(payload):
    """Keep API period labels intact; never convert missing energy to zero."""
    rows = payload["totalConsumption"]["powerConsumptionPrPeriod"]
    return [
        {"date": row["date"], "total_kwh": round(float(row["powerMeterConsumptionkWh"]), 3),
         "charging_kwh": round(float(row["chargePointConsumptionkWh"]), 3),
         "household_kwh": round(float(row["powerMeterConsumptionkWh"]) - float(row["chargePointConsumptionkWh"]), 3)}
        for row in rows
    ]


class CleverPowerCoordinator(DataUpdateCoordinator):
    """Failure here does not affect the charging coordinator."""

    def __init__(self, charging, meter_id):
        self.client = charging.client
        self.meter_id = meter_id
        super().__init__(charging.hass, LOGGER, config_entry=charging.config_entry,
                         name="Clever Power history", update_interval=timedelta(hours=6))

    async def _async_update_data(self):
        today = dt_util.now().date()
        try:
            month = await self.client.get_power_consumption(self.meter_id, today.replace(day=1), "monthly")
            year = await self.client.get_power_consumption(self.meter_id, today.replace(month=1, day=1), "yearly")
            days = consumption_rows(month)
            months = consumption_rows(year)
            # A new calendar month may have no published daily values yet.
            if not days:
                previous = today.replace(day=1) - timedelta(days=1)
                month = await self.client.get_power_consumption(self.meter_id, previous.replace(day=1), "monthly")
                days = consumption_rows(month)
            if not days:
                raise ValueError("No published daily consumption")
            latest = max(days, key=lambda row: row["date"])
            day = await self.client.get_power_consumption(self.meter_id, dt_util.parse_datetime(latest["date"]).date(), "daily")
            current = next((row for row in months if row["date"][:7] == today.isoformat()[:7]), None)
            return {"month_kwh": current["household_kwh"] if current else None,
                    "latest_day_kwh": latest["household_kwh"], "latest_date": latest["date"][:10],
                    "days": days, "months": months, "hours": consumption_rows(day),
                    "updated_at": dt_util.utcnow().isoformat()}
        except (CleverError, ValueError, KeyError, TypeError, AttributeError) as err:
            # Do not put meter IDs, tokens or address-bearing responses in logs.
            raise UpdateFailed(f"Clever Power history unavailable ({type(err).__name__})") from err


class CleverPowerSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator, customer_id, device_info, key, name):
        super().__init__(coordinator)
        self.key = key
        self._attr_unique_id = f"{customer_id}_{coordinator.meter_id}_power_{key}"
        self._attr_name = name
        self._attr_device_info = device_info

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.key)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        if self.key == "month_kwh":
            return {k: data[k] for k in ("days", "months", "hours", "latest_date", "updated_at") if k in data} | {
                "description": "Husforbrug uden ladeboks. Historiske Clever Power-data; indevaerende perioder er ufuldstaendige."}
        return {"date": data.get("latest_date"), "updated_at": data.get("updated_at")}


async def async_setup_power_sensors(charging, async_add_entities):
    """Discover active meters; never register control services or actions."""
    try:
        if not getattr(charging.data.profile, "customer_id", None):
            return
        agreements = await charging.client.get_power_engagements()
        meters = {m["gsrn"] for group in agreements for m in group.get("powerMeterEngagementInfos", [])
                  if m.get("gsrn") and not m.get("endDate")}
    except (CleverError, KeyError, TypeError):
        LOGGER.warning("Clever Power meter discovery failed; charging is unaffected")
        return
    for meter in meters:
        coordinator = CleverPowerCoordinator(charging, meter)
        await coordinator.async_refresh()
        device = {"identifiers": {("clever_api", charging.data.profile.customer_id)}}
        async_add_entities([
            CleverPowerSensor(coordinator, charging.data.profile.customer_id, device, "month_kwh", "Husforbrug denne maaned"),
            CleverPowerSensor(coordinator, charging.data.profile.customer_id, device, "latest_day_kwh", "Husforbrug seneste maalte dag"),
        ])
