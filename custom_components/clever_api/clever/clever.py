"""Asynchronous client for the current Clever Android app backends."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from aiohttp import ClientError, ClientSession

from .exceptions import (
    CleverApiError,
    CleverAuthenticationError,
    CleverConnectionError,
)

API_BASE = "https://mobileapp-backend.clever.dk/api/v6/"
FIREBASE_API_KEY = "AIzaSyAQpjnGi6Tvk_sO9JFdS5Hj2NBuIEIAZjo"
FIREBASE_PROJECT = "clever-app-prod"
FIRESTORE_DATABASE = "user-database"
ANDROID_PACKAGE = "dk.clever.app"
ANDROID_CERT = "2B187B6CBA980988B235ED26BF755FEE7C1E0A43"
APP_VERSION = "26.33.0"
STATIC_API_KEY = "Basic bW9iaWxlYXBwOmFwaWtleQ=="

TokenUpdateCallback = Callable[[str, str], None]


class CleverClient:
    """Firebase-authenticated Clever REST and Firestore client."""

    def __init__(
        self,
        session: ClientSession,
        *,
        refresh_token: str | None = None,
        firebase_uid: str | None = None,
        request_timeout: int = 30,
        token_update_callback: TokenUpdateCallback | None = None,
    ) -> None:
        self._session = session
        self._refresh_token = refresh_token
        self._firebase_uid = firebase_uid
        self._request_timeout = request_timeout
        self._token_update_callback = token_update_callback
        self._id_token: str | None = None
        self._token_expires_at = 0.0
        self._refresh_lock = asyncio.Lock()

    @property
    def refresh_token(self) -> str | None:
        return self._refresh_token

    @property
    def firebase_uid(self) -> str | None:
        return self._firebase_uid

    async def login(self, email: str, password: str) -> None:
        """Sign in with Firebase email/password authentication."""
        payload = await self._request_json(
            "POST",
            "https://identitytoolkit.googleapis.com/v1/"
            f"accounts:signInWithPassword?key={FIREBASE_API_KEY}",
            headers=self._firebase_headers,
            json={"email": email, "password": password, "returnSecureToken": True},
            authentication_request=True,
        )
        self._set_tokens(payload)

    async def refresh_authentication(self, *, force: bool = False) -> None:
        """Exchange the saved Firebase refresh token for an ID token."""
        if not force and self._id_token and time.monotonic() < self._token_expires_at:
            return
        async with self._refresh_lock:
            if (
                not force
                and self._id_token
                and time.monotonic() < self._token_expires_at
            ):
                return
            if not self._refresh_token:
                raise CleverAuthenticationError(
                    "No Firebase refresh token is available"
                )
            payload = await self._request_json(
                "POST",
                f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}",
                headers=self._firebase_headers,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                },
                authentication_request=True,
            )
            self._set_tokens(payload)

    async def get_profile(self) -> dict[str, Any]:
        return await self._clever_data("GET", "profiles/get-profile")

    async def get_installations(self) -> list[dict[str, Any]]:
        return await self._clever_data("GET", "installations")

    async def get_consumption_history(self) -> list[dict[str, Any]]:
        data = await self._clever_data("GET", "consumption/history")
        return list(data.get("consumptionRecords") or [])

    async def get_energy_surcharge(self) -> dict[str, Any]:
        return await self._clever_data("GET", "energysurcharge/estimated")

    async def get_charging_profiles(self) -> list[dict[str, Any]]:
        return await self._clever_data("GET", "chargingprofiles")

    async def get_home_chargepoints(self) -> list[dict[str, Any]]:
        return await self._firestore_collection("home-chargepoints")

    async def get_active_transactions(self) -> list[dict[str, Any]]:
        return await self._firestore_collection("active-transactions")

    async def set_charging_profile_enabled(self, profile_id: str, enable: bool) -> None:
        await self._clever_request(
            "PUT",
            f"chargingprofiles/{quote(profile_id, safe='')}/enable",
            json={"enable": enable},
        )

    async def set_departure_time(self, profile_id: str, departure_time: str) -> None:
        await self._clever_request(
            "PUT",
            f"chargingprofiles/{quote(profile_id, safe='')}/departure-time",
            json={"departureTime": departure_time},
        )

    async def set_power_required(self, profile_id: str, power_required: int) -> None:
        await self._clever_request(
            "PUT",
            f"chargingprofiles/{quote(profile_id, safe='')}/power-required",
            json={"powerRequired": power_required},
        )

    async def set_preheat(self, profile_id: str, enable: bool) -> None:
        await self._clever_request(
            "PUT",
            f"chargingprofiles/{quote(profile_id, safe='')}/preheat",
            json={"enable": enable},
        )

    async def boost(self, charge_point_id: str, connector_id: int) -> None:
        await self._clever_request(
            "POST",
            "smartcharging/chargePoints/"
            f"{quote(charge_point_id, safe='')}/connectors/{connector_id}/boost",
        )

    async def timebox_boost(
        self, charge_point_id: str, connector_id: int, duration_minutes: int
    ) -> None:
        await self._clever_request(
            "POST",
            "smartcharging/chargePoints/"
            f"{quote(charge_point_id, safe='')}/connectors/{connector_id}/timebox-boost",
            params={"durationInMinutes": duration_minutes},
        )

    async def unboost(self, charge_point_id: str, connector_id: int) -> None:
        await self._clever_request(
            "POST",
            "smartcharging/chargePoints/"
            f"{quote(charge_point_id, safe='')}/connectors/{connector_id}/unboost",
        )

    @property
    def _firebase_headers(self) -> dict[str, str]:
        return {
            "X-Android-Package": ANDROID_PACKAGE,
            "X-Android-Cert": ANDROID_CERT,
        }

    def _set_tokens(self, payload: dict[str, Any]) -> None:
        id_token = payload.get("idToken") or payload.get("id_token")
        refresh_token = payload.get("refreshToken") or payload.get("refresh_token")
        firebase_uid = payload.get("localId") or payload.get("user_id")
        if not id_token or not refresh_token or not firebase_uid:
            raise CleverAuthenticationError(
                "Firebase returned an incomplete token response"
            )
        self._id_token = str(id_token)
        self._refresh_token = str(refresh_token)
        self._firebase_uid = str(firebase_uid)
        expires_in = int(payload.get("expiresIn") or payload.get("expires_in") or 3600)
        self._token_expires_at = time.monotonic() + max(0, expires_in - 60)
        if self._token_update_callback:
            self._token_update_callback(self._refresh_token, self._firebase_uid)

    async def _clever_data(self, method: str, path: str, **kwargs: Any) -> Any:
        payload = await self._clever_request(method, path, **kwargs)
        if not isinstance(payload, dict) or "data" not in payload:
            raise CleverApiError(200, "Clever returned an invalid response wrapper")
        return payload["data"]

    async def _clever_request(
        self, method: str, path: str, *, _retry: bool = True, **kwargs: Any
    ) -> Any:
        await self.refresh_authentication()
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._id_token}",
            "x-api-key": STATIC_API_KEY,
            "App-Version": APP_VERSION,
            "App-Platform": "Android",
            "App-OS": "16",
            "App-Device": "Home Assistant",
            "Accept-Language": "da-DK",
            "User-Agent": f"dk.clever.core.network/{APP_VERSION}",
        }
        try:
            payload = await self._request_json(
                method, API_BASE + path, headers=headers, **kwargs
            )
        except CleverAuthenticationError:
            if not _retry:
                raise
            await self.refresh_authentication(force=True)
            return await self._clever_request(method, path, _retry=False, **kwargs)
        if isinstance(payload, dict) and payload.get("status") is False:
            raise CleverApiError(
                200, str(payload.get("statusMessage") or "Clever request failed")
            )
        return payload

    async def _firestore_collection(
        self, collection: str, *, _retry: bool = True
    ) -> list[dict[str, Any]]:
        await self.refresh_authentication()
        if not self._firebase_uid:
            raise CleverAuthenticationError("Firebase user ID is unavailable")
        url = (
            "https://firestore.googleapis.com/v1/projects/"
            f"{FIREBASE_PROJECT}/databases/{FIRESTORE_DATABASE}/documents/"
            f"v1-user-data/{quote(self._firebase_uid, safe='')}/{collection}"
        )
        try:
            payload = await self._request_json(
                "GET", url, headers={"Authorization": f"Bearer {self._id_token}"}
            )
        except CleverAuthenticationError:
            if not _retry:
                raise
            await self.refresh_authentication(force=True)
            return await self._firestore_collection(collection, _retry=False)
        documents: list[dict[str, Any]] = []
        for document in payload.get("documents") or []:
            decoded = {
                key: decode_firestore_value(value)
                for key, value in (document.get("fields") or {}).items()
            }
            decoded["_document_name"] = document.get("name")
            documents.append(decoded)
        return documents

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        params: dict[str, Any] | None = None,
        authentication_request: bool = False,
    ) -> dict[str, Any]:
        try:
            async with asyncio.timeout(self._request_timeout):
                async with self._session.request(
                    method,
                    url,
                    headers=headers,
                    json=json,
                    data=data,
                    params=params,
                ) as response:
                    if response.status == 204:
                        payload: Any = {}
                    else:
                        try:
                            payload = await response.json(content_type=None)
                        except (ValueError, TypeError):
                            payload = {}
                    if response.status in {400, 401, 403} and authentication_request:
                        raise CleverAuthenticationError(_error_message(payload))
                    if response.status == 401:
                        raise CleverAuthenticationError(_error_message(payload))
                    if response.status >= 400:
                        raise CleverApiError(response.status, _error_message(payload))
                    if not isinstance(payload, dict):
                        raise CleverApiError(
                            response.status, "Backend returned non-object JSON"
                        )
                    return payload
        except (TimeoutError, ClientError) as error:
            raise CleverConnectionError("Unable to reach the Clever backend") from error


def decode_firestore_value(value: dict[str, Any]) -> Any:
    """Decode a value from the Firestore REST wire representation."""
    if "nullValue" in value:
        return None
    if "booleanValue" in value:
        return bool(value["booleanValue"])
    if "integerValue" in value:
        return int(value["integerValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "timestampValue" in value:
        return value["timestampValue"]
    if "stringValue" in value:
        return value["stringValue"]
    if "bytesValue" in value:
        return value["bytesValue"]
    if "referenceValue" in value:
        return value["referenceValue"]
    if "geoPointValue" in value:
        return dict(value["geoPointValue"])
    if "arrayValue" in value:
        return [
            decode_firestore_value(item)
            for item in value["arrayValue"].get("values", [])
        ]
    if "mapValue" in value:
        return {
            key: decode_firestore_value(item)
            for key, item in value["mapValue"].get("fields", {}).items()
        }
    return None


def _error_message(payload: Any) -> str:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or "Authentication failed")
        if isinstance(error, str):
            return error
        return str(
            payload.get("statusMessage") or payload.get("message") or "Request failed"
        )
    return "Request failed"
