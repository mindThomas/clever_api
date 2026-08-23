"""Tests for Clever response models."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components" / "clever_api"))

from clever.models import (
    ActiveTransaction,
    ChargingProfile,
    ConsumptionRecord,
    Installation,
    summarize_consumption,
)


class ModelTests(unittest.TestCase):
    def test_consumption_microsecond_timestamps_and_summary(self) -> None:
        record = ConsumptionRecord.from_api(
            {
                "chargePointId": "home-1",
                "connectorId": 1,
                "startTimeUtc": 1785542400000000,
                "stopTimeUtc": 1785546000000000,
                "kWh": 12.5,
            }
        )
        self.assertEqual(record.start, datetime(2026, 8, 1, tzinfo=UTC))
        summary = summarize_consumption(
            [record], datetime(2026, 8, 1, tzinfo=UTC), "home-1"
        )
        self.assertEqual(summary.kwh_this_month, 12.5)
        self.assertEqual(summary.kwh_this_month_box, 12.5)
        self.assertEqual(summary.last_charge, record.stop)

    def test_charging_profile_matches_installation(self) -> None:
        installation = Installation.from_api(
            {
                "installationId": "installation-1",
                "chargeBoxId": "box-1",
                "connectorId": 1,
                "installationStatus": "Operational",
                "smartChargingConfiguration": None,
            }
        )
        profile = ChargingProfile.from_api(
            {
                "id": "profile-1",
                "type": "Home",
                "filters": {
                    "locations": [{"chargePoints": [{"id": "box-1", "connectorId": 1}]}]
                },
                "strategySettings": {
                    "disabled": False,
                    "departureTime": "07:00",
                    "powerRequired": 80,
                    "preheatDurationMinutes": 0,
                },
            }
        )
        self.assertTrue(profile.matches(installation))
        self.assertTrue(profile.enabled)

    def test_completed_transaction_is_not_active(self) -> None:
        transaction = ActiveTransaction.from_firestore(
            {
                "chargePointId": "box-1",
                "connectorId": 1,
                "cpmsChargingStatus": "Completed",
                "consumedWh": 18713,
            }
        )
        self.assertFalse(transaction.is_active)

    def test_active_boost_segment(self) -> None:
        transaction = ActiveTransaction.from_firestore(
            {
                "chargePointId": "box-1",
                "connectorId": 1,
                "cpmsChargingStatus": "Charging",
                "chargingPlan": {
                    "segments": [
                        {
                            "start": "2026-08-23T18:00:00Z",
                            "end": "2026-08-23T20:00:00Z",
                            "reason": {"strategy": "Boost"},
                        }
                    ]
                },
            }
        )
        self.assertTrue(
            transaction.is_boosted_at(datetime(2026, 8, 23, 19, tzinfo=UTC))
        )


if __name__ == "__main__":
    unittest.main()
