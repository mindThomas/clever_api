"""Tests for Firebase authentication and backend request construction."""

from __future__ import annotations

import sys
import unittest
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
