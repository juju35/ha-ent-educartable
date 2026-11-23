"""Tests of the pure coordinator helpers and the OIDC token parsing."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.educartable.api import (
    EducartableApi,
    EducartableAuthError,
    EducartableOTPRequired,
)
from custom_components.educartable.coordinator import _homework, _message, _pupil, parse_when


def test_parse_when_handles_millis_iso_and_date() -> None:
    assert parse_when(None) is None
    assert parse_when("") is None
    assert parse_when("2026-11-25").isoformat() == "2026-11-25"
    assert parse_when(1763200000000) is not None


def test_pupil_builds_a_name() -> None:
    pupil = _pupil({"id": 7, "firstname": "Alice", "name": "Test", "classroom": {"name": "CE2 A"}})
    assert pupil == {
        "id": "7",
        "name": "Alice Test",
        "firstname": "Alice",
        "classroom": "CE2 A",
        "teacher": "",
        "grade": "",
    }


def test_homework_done_flag_follows_achievements() -> None:
    assert _homework({"id": "h1", "title": "x", "achievements": []})["done"] is False
    assert _homework({"id": "h2", "title": "y", "achievements": [{"action": "read"}]})["done"] is True


def test_message_to_sign_when_a_recipient_is_unchecked() -> None:
    assert _message({"id": "c1", "recipients": [{"id": "r", "checked": False}]})["to_sign"] is True
    assert _message({"id": "c2", "recipients": [{"id": "r", "checked": True}]})["to_sign"] is False
    assert _message({"id": "c3"})["to_sign"] is False


class _FakeResponse:
    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        self.status = status
        self._payload = payload

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def json(self, content_type: Any = None) -> dict[str, Any]:
        return self._payload


class _FakeSession:
    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        self._status = status
        self._payload = payload

    def post(self, *args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse(self._status, self._payload)


async def test_login_parses_tokens() -> None:
    session = _FakeSession(200, {"access_token": "a", "refresh_token": "r", "expires_in": 3600})
    api = EducartableApi(session, "parent", "secret")  # type: ignore[arg-type]
    await api.login()
    assert api._access_token == "a"


async def test_login_rejects_bad_credentials() -> None:
    session = _FakeSession(401, {"error": "invalid_grant", "error_description": "bad"})
    with pytest.raises(EducartableAuthError):
        await EducartableApi(session, "parent", "nope").login()  # type: ignore[arg-type]


async def test_login_detects_required_otp() -> None:
    session = _FakeSession(401, {"error": "invalid_grant", "error_description": "Missing totp"})
    with pytest.raises(EducartableOTPRequired):
        await EducartableApi(session, "parent", "secret").login()  # type: ignore[arg-type]
