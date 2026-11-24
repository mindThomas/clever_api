"""Tests for Firebase authentication and backend request construction."""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from typing import Any, Self

sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components" / "clever_api"))

from clever.clever import (
    ANDROID_CERT,
    ANDROID_PACKAGE,
    STATIC_API_KEY,
    CleverClient,
    decode_firestore_value,
)


class FakeResponse:
    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        self.status = status
        self._payload = payload

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def json(self, **kwargs: Any) -> dict[str, Any]:
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.requests.append((method, url, kwargs))
        return self.responses.pop(0)


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_market_requests_are_get_only(self):
        session = FakeSession([FakeResponse(200, {"data": {"prices": []}}),
                               FakeResponse(200, {"data": []})])
        client = CleverClient(session)  # type: ignore[arg-type]
        client._id_token = "test-token"
        client._token_expires_at = float("inf")
        await client.get_electricity_prices("test-address", date(2026, 11, 24), date(2026, 11, 25))
        await client.get_historical_energy_surcharges(date(2024, 1, 1), date(2026, 11, 24))
        self.assertTrue(all(method == "GET" for method, _, _ in session.requests))
        self.assertTrue(session.requests[0][1].endswith("electricity-pricing/app-price"))
        self.assertEqual(session.requests[0][2]["params"],
                         {"darReferenceId": "test-address", "from": "2026-11-24", "to": "2026-11-25"})
        self.assertTrue(session.requests[1][1].endswith("energysurcharge/historical"))
        self.assertEqual(session.requests[1][2]["params"],
                         {"startYear": 2024, "startMonth": 1, "endYear": 2026, "endMonth": 11})

    async def test_invalid_market_dates_do_not_send_requests(self):
        session = FakeSession([])
        client = CleverClient(session)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            await client.get_electricity_prices("test", date(2026, 11, 25), date(2026, 11, 24))
        with self.assertRaises(ValueError):
            await client.get_historical_energy_surcharges(date(2026, 11, 25), date(2026, 11, 24))
        with self.assertRaises(TypeError):
            await client.get_electricity_prices("test", datetime(2026, 11, 24), date(2026, 11, 25))
        self.assertEqual(session.requests, [])

    async def test_power_engagements_are_read_only(self) -> None:
        agreements = [{"powerMeterEngagementInfos": [{"gsrn": "test-meter"}]}]
        session = FakeSession([FakeResponse(200, {"data": agreements})])
        client = CleverClient(session)  # type: ignore[arg-type]
        client._id_token = "test-token"
        client._token_expires_at = float("inf")
        self.assertEqual(await client.get_power_engagements(), agreements)
        method, url, _ = session.requests[0]
        self.assertEqual(method, "GET")
        self.assertTrue(url.endswith("/powerconsumption/powerEngagements"))

    async def test_power_consumption_periods_and_calendar_date(self) -> None:
        for period in ("daily", "monthly", "yearly"):
            with self.subTest(period=period):
                payload = {
                    "totalConsumption": {
                        "totalPowerMeterkWh": 23.44,
                        "totalChargePointkWh": 6.105,
                        "powerConsumptionPrPeriod": [],
                    }
                }
                session = FakeSession([FakeResponse(200, {"data": payload})])
                client = CleverClient(session)  # type: ignore[arg-type]
                client._id_token = "test-token"
                client._token_expires_at = float("inf")
                result = await client.get_power_consumption(
                    "test/meter", date(2026, 11, 22), period
                )
                self.assertEqual(result, payload)
                method, url, kwargs = session.requests[0]
                self.assertEqual(method, "GET")
                self.assertTrue(url.endswith(f"/{period}/gsnr/test%2Fmeter"))
                self.assertEqual(kwargs["params"], {"startDate": "2026-11-22"})
                totals = result["totalConsumption"]
                self.assertAlmostEqual(
                    totals["totalPowerMeterkWh"] - totals["totalChargePointkWh"],
                    17.335,
                )

    async def test_invalid_power_parameters_send_no_requests(self) -> None:
        session = FakeSession([])
        client = CleverClient(session)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            await client.get_power_consumption("test", date(2026, 11, 22), "bad")
        with self.assertRaises(ValueError):
            await client.get_power_consumption(" ", date(2026, 11, 22))
        with self.assertRaises(TypeError):
            await client.get_power_consumption("test", datetime(2026, 11, 22))
        self.assertEqual(session.requests, [])

    async def test_login_and_authenticated_profile_request(self) -> None:
        session = FakeSession(
            [
                FakeResponse(
                    200,
                    {
                        "idToken": "id-token",
                        "refreshToken": "refresh-token",
                        "localId": "uid",
                        "expiresIn": "3600",
                    },
                ),
                FakeResponse(
                    200,
                    {
                        "data": {"customerId": "customer-1"},
                        "status": True,
                        "statusMessage": "",
                    },
                ),
            ]
        )
        client = CleverClient(session)  # type: ignore[arg-type]
        await client.login("person@example.com", "temporary-password")
        profile = await client.get_profile()

        self.assertEqual(profile["customerId"], "customer-1")
        login_headers = session.requests[0][2]["headers"]
        self.assertEqual(login_headers["X-Android-Package"], ANDROID_PACKAGE)
        self.assertEqual(login_headers["X-Android-Cert"], ANDROID_CERT)
        api_headers = session.requests[1][2]["headers"]
        self.assertEqual(api_headers["Authorization"], "Bearer id-token")
        self.assertEqual(api_headers["x-api-key"], STATIC_API_KEY)

    async def test_refresh_token_rotation_callback(self) -> None:
        updates: list[tuple[str, str]] = []
        session = FakeSession(
            [
                FakeResponse(
                    200,
                    {
                        "id_token": "new-id-token",
                        "refresh_token": "new-refresh-token",
                        "user_id": "uid",
                        "expires_in": "3600",
                    },
                )
            ]
        )
        client = CleverClient(
            session,  # type: ignore[arg-type]
            refresh_token="old-refresh-token",
            firebase_uid="uid",
            token_update_callback=lambda token, uid: updates.append((token, uid)),
        )
        await client.refresh_authentication()
        self.assertEqual(updates, [("new-refresh-token", "uid")])
        self.assertEqual(session.requests[0][2]["data"]["grant_type"], "refresh_token")

    async def test_firestore_collection_path_and_decoding(self) -> None:
        session = FakeSession(
            [
                FakeResponse(
                    200,
                    {
                        "id_token": "id-token",
                        "refresh_token": "refresh-token",
                        "user_id": "uid",
                        "expires_in": "3600",
                    },
                ),
                FakeResponse(
                    200,
                    {
                        "documents": [
                            {
                                "name": "document-name",
                                "fields": {
                                    "status": {"stringValue": "Offline"},
                                    "connectorId": {"integerValue": "1"},
                                },
                            }
                        ]
                    },
                ),
            ]
        )
        client = CleverClient(  # type: ignore[arg-type]
            session, refresh_token="refresh-token", firebase_uid="uid"
        )
        documents = await client.get_home_chargepoints()
        self.assertEqual(documents[0]["status"], "Offline")
        self.assertIn(
            "/databases/user-database/documents/v1-user-data/uid/home-chargepoints",
            session.requests[1][1],
        )

    async def test_control_request_contracts(self) -> None:
        session = FakeSession(
            [
                FakeResponse(
                    200,
                    {
                        "id_token": "id-token",
                        "refresh_token": "refresh-token",
                        "user_id": "uid",
                        "expires_in": "3600",
                    },
                ),
                FakeResponse(200, {"status": True, "data": None}),
                FakeResponse(200, {"status": True, "data": None}),
                FakeResponse(200, {"status": True, "data": None}),
                FakeResponse(200, {"status": True, "data": None}),
            ]
        )
        client = CleverClient(  # type: ignore[arg-type]
            session, refresh_token="refresh-token", firebase_uid="uid"
        )
        await client.set_charging_profile_enabled("profile/1", True)
        await client.set_departure_time("profile/1", "07:00")
        await client.set_power_required("profile/1", 80)
        await client.set_preheat("profile/1", True)

        requests = session.requests[1:]
        self.assertTrue(requests[0][1].endswith("chargingprofiles/profile%2F1/enable"))
        self.assertEqual(requests[0][2]["json"], {"enable": True})
        self.assertEqual(requests[1][2]["json"], {"departureTime": "07:00"})
        self.assertEqual(requests[2][2]["json"], {"powerRequired": 80})
        self.assertEqual(requests[3][2]["json"], {"enable": True})

    def test_firestore_decoder(self) -> None:
        value = {
            "mapValue": {
                "fields": {
                    "status": {"stringValue": "Charging"},
                    "connectorId": {"integerValue": "1"},
                    "values": {
                        "arrayValue": {
                            "values": [
                                {"doubleValue": 1.5},
                                {"booleanValue": True},
                            ]
                        }
                    },
                }
            }
        }
        self.assertEqual(
            decode_firestore_value(value),
            {"status": "Charging", "connectorId": 1, "values": [1.5, True]},
        )


if __name__ == "__main__":
    unittest.main()
