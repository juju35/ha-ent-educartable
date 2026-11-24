"""Client for the Educartable (EDUMOOV family portal) unofficial API.

Unofficial API — it can change without notice. Authentication is OpenID Connect (Keycloak); the data routes
are plain REST with the access token as a Bearer header; surveys and appointments go through the portal's RPC API
(POST <method> with {params, payload}, answered with {success, data, error}). Routes follow the portal's own web app
(mobile.educartable.com): reads, the achievement of a message (sign, read, comment…), the done box of a homework, the
private conversation of a message, new messages to the teacher, surveys, appointment slots, the pupil's livret
(notebooks and attestations, signed as consulted) and the attachments (medias, livret PDFs).
"""

from __future__ import annotations

import re
import time
from typing import Any

import aiohttp

from .const import (
    ACTIVITY_TYPES,
    API_CORE,
    API_EDUCARTABLE,
    API_EDUCORE,
    API_LIVRET,
    CARNET_TYPES,
    CLIENT_ID,
    LESSON_TYPES,
    NEWS_TYPES,
    RPC_BASE,
    SCOPE,
    TOKEN_URL,
)

_TIMEOUT = aiohttp.ClientTimeout(total=30)
# Attachments are served through Home Assistant: never more than this in memory.
MEDIA_MAX_BYTES = 25 * 1024 * 1024
# A media id is a plain identifier: anything else would let a caller reach another route.
MEDIA_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
# The language comments are written in (the portal translates them for teachers who ask).
COMMENT_LANG = "fr"


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
        return await self._request("GET", url, params=params)

    async def _post(self, url: str, payload: dict[str, Any]) -> Any:
        return await self._request("POST", url, json=payload)

    async def _request(
        self, method: str, url: str, *, params: dict[str, Any] | None = None, json: dict[str, Any] | None = None
    ) -> Any:
        await self._ensure_token()
        for attempt in (1, 2):
            headers = {"Authorization": f"Bearer {self._access_token}", "Accept": "application/json"}
            try:
                async with self._session.request(
                    method, url, params=params, json=json, headers=headers, timeout=_TIMEOUT
                ) as resp:
                    if resp.status == 401 and attempt == 1:
                        self._access_token = None
                        await self.login()
                        continue
                    if resp.status == 401:
                        raise EducartableAuthError("session refused")
                    if resp.status >= 500:
                        raise EducartableUnavailableError(f"HTTP {resp.status}")
                    if resp.status not in (200, 201, 204):
                        raise EducartableError(f"HTTP {resp.status} on {url}")
                    if resp.status == 204:
                        return {}
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

    async def activities(self, parent_id: str, limit: int) -> list[dict[str, Any]]:
        """The cahier de vie: the class's posts, newest first."""
        return await self._messages(parent_id, ACTIVITY_TYPES, sort="date", direction="desc", limit=limit)

    async def notifications(self, parent_id: str) -> list[dict[str, Any]]:
        """The portal's notifications of the account (new message, reply, cancelled appointment…)."""
        data = await self._get(f"{API_EDUCORE}/parent/{parent_id}/notifications", {"app": "Educartable"})
        return data.get("data", []) if isinstance(data, dict) else []

    async def next_appointments(self, start: str, stop: str) -> list[dict[str, Any]]:
        """The appointment slots booked for the family's children between two days."""
        data = await self.rpc("cartable.events.nextRegisteredEvents", {"start": start, "stop": stop})
        return data if isinstance(data, list) else []

    # ── Writes (as the portal's web app) ────────────────────────────────────────────────────────────────────

    async def achieve(
        self, parent_id: str, message_id: str, action: str, subject_model: str, subject_key: list[str], body: str = ""
    ) -> None:
        """Record the action a message asks for: sign (body = the signer's name), read, check, comment…"""
        await self._post(
            f"{API_EDUCARTABLE}/parent/{parent_id}/messages/{message_id}/achieve",
            {"subject_model": subject_model, "subject_key": subject_key, "action": action, "body": body},
        )

    async def check(self, parent_id: str, message_id: str, recipient_id: str, checked: bool) -> None:
        """Tick (or untick) a homework for one pupil: `recipient_id` is the pupil's recipient entry."""
        await self._post(
            f"{API_EDUCARTABLE}/parent/{parent_id}/messages/{message_id}/check",
            {"recipient_id": recipient_id, "checked": checked},
        )

    async def comments(self, parent_id: str, message_id: str) -> list[dict[str, Any]]:
        """The private conversation of a message with the teacher, oldest first."""
        data = await self._get(
            f"{API_EDUCORE}/parent/{parent_id}/comments",
            {"model": "HomeworkMessage", "key": message_id, "sort": "created"},
        )
        return data.get("data", []) if isinstance(data, dict) else []

    async def comment(self, parent_id: str, message_id: str, body: str, reply_to: str | None) -> dict[str, Any]:
        """Write in that conversation: `reply_to` is its first comment (none starts it)."""
        data = await self._post(
            f"{API_EDUCORE}/parent/{parent_id}/comments",
            {"key": message_id, "model": "HomeworkMessage", "body": body, "lang": COMMENT_LANG, "reply": reply_to},
        )
        return (data.get("data") or {}) if isinstance(data, dict) else {}

    async def write_message(self, parent_id: str, children: list[str], title: str, body: str) -> dict[str, Any]:
        """A new message to the teacher of these children (one classroom per call, as the portal's app does)."""
        data = await self._post(
            f"{API_EDUCARTABLE}/parent/{parent_id}/messages", {"children": children, "title": title, "body": body}
        )
        return (data.get("data") or {}) if isinstance(data, dict) else {}

    async def notebooks(self, parent_id: str) -> list[dict[str, Any]]:
        """The pupils' livrets (school reports), each with its PDF and its signatures."""
        data = await self._get(f"{API_LIVRET}/parent/{parent_id}/notebooks")
        return data.get("data", []) if isinstance(data, dict) else []

    async def attestations(self, parent_id: str) -> list[dict[str, Any]]:
        """The pupils' attestations (swimming, first aid…), each with its PDF and its signatures."""
        data = await self._get(f"{API_LIVRET}/parent/{parent_id}/attestations_validations")
        return data.get("data", []) if isinstance(data, dict) else []

    async def sign_document(self, parent_id: str, kind: str, document_id: str, name: str) -> None:
        """Sign a notebook or an attestation as consulted, with the signer's name."""
        route = {"notebook": "notebooks", "attestation": "attestations_validations"}[kind]
        await self._post(f"{API_LIVRET}/parent/{parent_id}/{route}/{document_id}/sign", {"name": name})

    async def like(self, parent_id: str, activity_id: str) -> str:
        """Like a post of the cahier de vie; the like's id is what unlikes it."""
        data = await self._post(
            f"{API_CORE}/parent/{parent_id}/likes", {"key": activity_id, "model": "HomeworkMessage"}
        )
        like = data.get("data") if isinstance(data, dict) else None
        return str(like.get("id") or "") if isinstance(like, dict) else ""

    async def unlike(self, parent_id: str, like_id: str) -> None:
        await self._request("DELETE", f"{API_CORE}/parent/{parent_id}/likes/{like_id}")

    async def read_notification(self, parent_id: str, notification_id: str) -> None:
        await self._request(
            "PUT", f"{API_EDUCORE}/parent/{parent_id}/notifications/{notification_id}", json={"read": True}
        )

    async def read_all_notifications(self, parent_id: str) -> None:
        await self._request(
            "PUT", f"{API_EDUCORE}/parent/{parent_id}/notifications/close_all", params={"app": "Educartable"}
        )

    async def delete_comment(self, parent_id: str, comment_id: str) -> None:
        """Delete one of the family's own comments (the portal keeps a "deleted" trace)."""
        await self._request("DELETE", f"{API_EDUCORE}/parent/{parent_id}/comments/{comment_id}/trash")

    async def rpc(self, method: str, params: dict[str, Any], payload: dict[str, Any] | None = None) -> Any:
        """Call a method of the portal's RPC API; its refusal ("code - text") is raised with its text."""
        data = await self._request("POST", f"{RPC_BASE}/{method}", json={"params": params, "payload": payload or {}})
        if not isinstance(data, dict):
            raise EducartableError(f"unexpected answer to {method}")
        if not data.get("success"):
            error = data.get("error") or {}
            message = str(error.get("message") or "refused") if isinstance(error, dict) else str(error)
            raise EducartableError(message.split(" - ", 1)[-1])
        return data.get("data")

    async def answer_survey(self, message_id: str, pupil_id: str, answers: dict[str, list[str]]) -> None:
        await self.rpc("parent.messages.answerSurvey", {"id": message_id, "pupil_id": pupil_id}, {"answers": answers})

    async def delete_survey_answer(self, message_id: str, pupil_id: str) -> None:
        await self.rpc("parent.messages.deleteAnswerSurvey", {"id": message_id, "pupil_id": pupil_id})

    async def book(self, slot_id: str, pupil_id: str) -> None:
        """Book an appointment slot of a message for a pupil."""
        await self.rpc("parent.events.register", {"id": slot_id}, {"pupil_id": pupil_id})

    async def cancel_booking(self, slot_id: str) -> None:
        await self.rpc("parent.events.unregister", {"id": slot_id})

    # ── Files ───────────────────────────────────────────────────────────────────────────────────────────────

    async def media(self, media_id: str) -> tuple[bytes, str]:
        """An attachment of a message: its bytes and the type the portal declares."""
        if not MEDIA_ID.fullmatch(media_id):
            raise EducartableError("invalid media id")
        return await self._download(f"{API_EDUCORE}/medias/{media_id}/file", f"media {media_id}")

    async def notebook_file(self, file_id: str, direct_hash: str) -> tuple[bytes, str]:
        """The PDF of a livret, stored on the portal's file service."""
        if not (MEDIA_ID.fullmatch(file_id) and MEDIA_ID.fullmatch(direct_hash)):
            raise EducartableError("invalid file id")
        return await self._download(f"{API_CORE}/cloudy_files/{file_id}/file/{direct_hash}/educartable", "livret")

    async def attestation_file(self, attestation_id: str, file_hash: str) -> tuple[bytes, str]:
        """The PDF of an attestation."""
        if not (MEDIA_ID.fullmatch(attestation_id) and MEDIA_ID.fullmatch(file_hash)):
            raise EducartableError("invalid file id")
        return await self._download(
            f"{API_LIVRET}/attestations_validations/pdf/{attestation_id}", "attestation", {"hash": file_hash}
        )

    async def _download(self, url: str, what: str, params: dict[str, str] | None = None) -> tuple[bytes, str]:
        await self._ensure_token()
        headers = {"Authorization": f"Bearer {self._access_token}"}
        try:
            async with self._session.get(url, params=params, headers=headers, timeout=_TIMEOUT) as resp:
                if resp.status >= 500:
                    raise EducartableUnavailableError(f"HTTP {resp.status}")
                if resp.status != 200:
                    raise EducartableError(f"HTTP {resp.status} on {what}")
                if (resp.content_length or 0) > MEDIA_MAX_BYTES:
                    raise EducartableError("file too large")
                body = await resp.read()
                if len(body) > MEDIA_MAX_BYTES:
                    raise EducartableError("file too large")
                return body, resp.headers.get("Content-Type", "")
        except aiohttp.ClientError as err:
            raise EducartableUnavailableError(str(err)) from err
