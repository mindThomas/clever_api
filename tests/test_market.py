"""Offline parsing tests: no private data and no network access."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components" / "clever_api"))
from clever.market import prices, surcharges


class MarketTests(unittest.TestCase):
    def test_price_intervals_and_negative_prices(self):
        rows = prices({"prices": [{"startTime": "2026-11-24T00:00:00Z",
            "endTime": "2026-11-24T01:00:00Z", "totalPrice": -0.25,
            "currency": "DKK", "unit": "kWh", "tariffs": {"spotPrice": -0.5}}]})
        self.assertEqual(rows[0]["price"], -0.25)
        self.assertEqual(rows[0]["tariffs"]["spotPrice"], -0.5)
        self.assertTrue(rows[0]["start"].endswith("+00:00"))

    def test_bad_prices_are_not_silently_zero(self):
        base = {"startTime": "2026-11-24T00:00:00Z", "endTime": "2026-11-24T01:00:00Z",
                "totalPrice": 1.0, "currency": "DKK", "unit": "kWh"}
        for patch in ({"totalPrice": None}, {"totalPrice": float("nan")},
                      {"currency": "EUR"}, {"endTime": base["startTime"]},
                      {"startTime": "2026-11-24T00:00:00"}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                prices({"prices": [base | patch]})

    def test_history_preserves_zero_and_excludes_extra_data(self):
        rows = surcharges([{"startDate": "2026-09-01", "endDate": "2026-09-30",
                            "energySurchargePriceDkk": 0, "averagePriceDkk": 0.75,
                            "cutOffPriceDkk": 0.89, "dailyAverages": [1, 2]}])
        self.assertEqual(rows[0]["price"], 0)
        self.assertEqual(rows[0]["threshold"], 0.89)
        self.assertNotIn("dailyAverages", rows[0])
