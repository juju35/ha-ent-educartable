"""Client for the Educartable (EDUMOOV family portal) unofficial API.

Unofficial API — it can change without notice. Authentication is OpenID Connect (Keycloak); the data routes
are plain REST with the access token as a Bearer header. Only read operations are implemented.
"""

from __future__ import annotations

import time
from typing import Any

import aiohttp

from .const import (
    API_EDUCARTABLE,
    API_EDUCORE,
    CARNET_TYPES,
    CLIENT_ID,
    LESSON_TYPES,
    NEWS_TYPES,
    SCOPE,
    TOKEN_URL,
)

_TIMEOUT = aiohttp.ClientTimeout(total=30)


class EducartableError(Exception):
    """A communication error with Educartable."""


class EducartableAuthError(EducartableError):
    """The credentials were refused."""


class EducartableOTPRequired(EducartableAuthError):
    """A one-time code (2FA) is required and was missing or wrong."""


class EducartableUnavailableError(EducartableError):
    """Educartable is temporarily unavailable (network, 5xx)."""


class EducartableApi:
    """Minimal async client for one family account."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        totp: str | None = None,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._totp = totp
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._scope = SCOPE
        self._expires_at = 0.0

    def update_credentials(self, username: str, password: str, totp: str | None = None) -> None:
        """Replace the credentials read again from secrets.yaml at each update; drop the stale tokens."""
        if (username, password) != (self._username, self._password):
            self._access_token = self._refresh_token = None
        self._username, self._password, self._totp = username, password, totp

    # ── Authentication ──────────────────────────────────────────────────────────────────────────────────────

    async def _token(self, data: dict[str, str]) -> None:
        form = {"client_id": CLIENT_ID, "scope": self._scope, **data}
        try:
            async with self._session.post(
                TOKEN_URL,
                data=form,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=_TIMEOUT,
            ) as resp:
                payload = await resp.json(content_type=None)
                if resp.status in (400, 401):
                    blob = f"{(payload or {}).get('error', '')} {(payload or {}).get('error_description', '')}".lower()
                    if "totp" in blob or "otp" in blob:
                        raise EducartableOTPRequired(blob.strip() or "otp required")
                    raise EducartableAuthError((payload or {}).get("error_description") or "invalid credentials")
                if resp.status >= 500:
                    raise EducartableUnavailableError(f"auth HTTP {resp.status}")
                if resp.status != 200:
                    raise EducartableError(f"auth HTTP {resp.status}")
        except aiohttp.ClientError as err:
            raise EducartableUnavailableError(str(err)) from err
        self._access_token = payload["access_token"]
        self._refresh_token = payload.get("refresh_token")
        self._scope = payload.get("scope", self._scope)
        self._expires_at = time.time() + int(payload.get("expires_in", 3600))

    async def login(self) -> None:
        """Password grant (plus a one-time code when the account has 2FA)."""
        data = {"grant_type": "password", "username": self._username, "password": self._password}
        if self._totp:
            data["totp"] = self._totp
        await self._token(data)

    async def _ensure_token(self) -> None:
        if self._access_token and time.time() < self._expires_at - 60:
            return
        if self._refresh_token:
            try:
                await self._token({"grant_type": "refresh_token", "refresh_token": self._refresh_token})
                return
            except EducartableAuthError:
                self._refresh_token = None  # expired: fall back to a full login
        await self.login()

    # ── HTTP ────────────────────────────────────────────────────────────────────────────────────────────────

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        await self._ensure_token()
        for attempt in (1, 2):
            headers = {"Authorization": f"Bearer {self._access_token}", "Accept": "application/json"}
            try:
                async with self._session.get(url, params=params, headers=headers, timeout=_TIMEOUT) as resp:
                    if resp.status == 401 and attempt == 1:
                        self._access_token = None
                        await self.login()
                        continue
                    if resp.status == 401:
                        raise EducartableAuthError("session refused")
                    if resp.status >= 500:
                        raise EducartableUnavailableError(f"HTTP {resp.status}")
                    if resp.status != 200:
                        raise EducartableError(f"HTTP {resp.status} on {url}")
                    return await resp.json(content_type=None)
            except aiohttp.ClientError as err:
                raise EducartableUnavailableError(str(err)) from err
        raise EducartableError("unreachable")  # pragma: no cover

    # ── Reads ───────────────────────────────────────────────────────────────────────────────────────────────

    async def user_info(self) -> dict[str, Any]:
        """The family account: data.id is the parent id used by the other routes."""
        data = await self._get(f"{API_EDUCORE}/users/me", {"light": 1})
        return data.get("data", data) if isinstance(data, dict) else {}

    async def pupils(self, parent_id: str) -> list[dict[str, Any]]:
        data = await self._get(f"{API_EDUCORE}/parent/{parent_id}/pupils")
        return data.get("data", []) if isinstance(data, dict) else []

    async def _messages(
        self,
        parent_id: str,
        types: tuple[str, ...],
        *,
        pupil_id: str | None = None,
        sort: str = "date",
        direction: str = "desc",
        start: str | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"type": ",".join(types), "sort": sort, "direction": direction, "limit": limit}
        if pupil_id is not None:
            params["pupil_id"] = pupil_id
        if start is not None:
            params["start"] = start
        data = await self._get(f"{API_EDUCARTABLE}/parent/{parent_id}/messages", params)
        return data.get("data", []) if isinstance(data, dict) else []

    async def lessons(self, parent_id: str, start: str, *, pupil_id: str | None = None) -> list[dict[str, Any]]:
        return await self._messages(
            parent_id, LESSON_TYPES, pupil_id=pupil_id, sort="date", direction="asc", start=start
        )

    async def carnet(self, parent_id: str) -> list[dict[str, Any]]:
        return await self._messages(parent_id, CARNET_TYPES, sort="visibility", direction="desc")

    async def news(self, parent_id: str) -> list[dict[str, Any]]:
        return await self._messages(parent_id, NEWS_TYPES, sort="visibility", direction="desc")
