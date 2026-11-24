"""Tests of the pure coordinator helpers and the OIDC token parsing."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.educartable.api import (
    EducartableApi,
    EducartableAuthError,
    EducartableOTPRequired,
)
from custom_components.educartable.coordinator import _homework, _message, _pupil, parse_when, plain_text


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
    assert _homework({"id": "h2", "title": "y", "achievement": "read", "achievements": [7]})["done"] is True


def test_homework_to_check_is_ticked_pupil_by_pupil() -> None:
    raw = {
        "id": "h3",
        "achievement": "check",
        "achievements": [],
        "recipients": [
            {"model": "Pupil", "key": 1, "id": 11, "checked": True},
            {"model": "Pupil", "key": 2, "id": 12, "checked": False},
            {"model": "Classroom", "key": 9, "id": 19, "checked": True},
        ],
    }
    first, second = _homework(raw, "1"), _homework(raw, "2")
    assert (first["done"], first["recipient_id"]) == (True, "11")
    assert (second["done"], second["recipient_id"]) == (False, "12")
    assert _homework(raw, "3")["recipient_id"] == ""


def test_message_to_sign_follows_its_achievement() -> None:
    to_sign = _message({"id": "c1", "achievement": "sign", "achievements": [], "targetChildren": {"7": True}})
    assert (to_sign["to_sign"], to_sign["to_do"], to_sign["children"]) == (True, True, ["7"])
    # Signed once it has an achievement, whatever its recipients say
    signed = _message({"id": "c2", "achievement": "sign", "achievements": [3], "recipients": [{"checked": False}]})
    assert (signed["to_sign"], signed["to_do"]) == (False, False)
    to_read = _message({"id": "c3", "achievement": "read", "achievements": []})
    assert (to_read["to_sign"], to_read["to_do"]) == (False, True)
    assert _message({"id": "c4"})["to_do"] is False
    assert _message({"id": "c5", "achievement": "whatever"})["achievement"] == ""


def test_message_keeps_its_text_author_and_attachments() -> None:
    message = _message(
        {
            "id": "c1",
            "title": "Trip",
            "body": "<p>Bring a <b>lunch</b>&nbsp;box.</p><ul><li>Hat</li><li>Coat</li></ul>",
            "user": {"firstname": "Ann", "name": "Brown"},
            "visibility": "2026-11-20T08:00:00+01:00",
            "medias": [{"id": 5, "name": "Map", "extension": "PDF"}, {"id": 4, "name": "a.jpg", "extension": "jpg"}],
            "pupils": [{"id": 7}],
        }
    )
    assert message["text"] == "Bring a lunch\xa0box.\n• Hat\n• Coat"
    assert message["author"] == "Ann Brown"
    assert message["children"] == ["7"]
    assert message["date"] is not None
    assert message["medias"] == [
        {"id": "4", "name": "a.jpg", "extension": "jpg"},
        {"id": "5", "name": "Map.PDF", "extension": "pdf"},
    ]


def test_plain_text() -> None:
    assert plain_text(None) == ""
    assert plain_text("Line 1<br>Line 2<br/><br><br>Line 3") == "Line 1\nLine 2\n\nLine 3"
    assert plain_text("&lt;b&gt; &amp; <script>x</script>") == "<b> & x"


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
