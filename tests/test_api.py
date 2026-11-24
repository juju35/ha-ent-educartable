"""Tests of the pure coordinator helpers and the OIDC token parsing."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.educartable.api import (
    EducartableApi,
    EducartableAuthError,
    EducartableError,
    EducartableOTPRequired,
)
from custom_components.educartable.coordinator import (
    _document,
    _homework,
    _message,
    _pupil,
    parse_when,
    plain_text,
)


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
        "classroom_id": "",
        "writable": True,
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
        self.requests: list[tuple[str, str, Any]] = []

    def post(self, *args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse(self._status, self._payload)

    def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        self.requests.append((method, url, kwargs.get("json")))
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


def _logged_in(session: _FakeSession) -> EducartableApi:
    api = EducartableApi(session, "parent", "secret")  # type: ignore[arg-type]
    api._access_token, api._expires_at = "a", 4e9
    return api


async def test_rpc_posts_params_and_payload() -> None:
    session = _FakeSession(200, {"success": True, "data": {"id": 3}})
    await _logged_in(session).book("51", "e1")
    assert session.requests == [
        (
            "POST",
            "https://api.edumoov.com/rpc/parent.events.register",
            {"params": {"id": "51"}, "payload": {"pupil_id": "e1"}},
        )
    ]


async def test_rpc_refusal_keeps_the_portal_text() -> None:
    session = _FakeSession(200, {"success": False, "error": {"message": "409 - Ce créneau est déjà réservé"}})
    with pytest.raises(EducartableError, match=r"^Ce créneau est déjà réservé$"):
        await _logged_in(session).answer_survey("c5", "e1", {"q1": ["a"]})


async def test_comment_starts_or_continues_the_thread() -> None:
    session = _FakeSession(200, {"data": {"id": 9}})
    await _logged_in(session).comment("p1", "c6", "Bonjour", None)
    _method, url, body = session.requests[0]
    assert url.endswith("/educore/parent/p1/comments")
    assert body == {"key": "c6", "model": "HomeworkMessage", "body": "Bonjour", "lang": "fr", "reply": None}


def test_message_survey_slots_and_conversation() -> None:
    message = _message(
        {
            "id": "c5",
            "commentable": True,
            "comments_count": 2,
            "survey": '{"deadline": "2026-12-01", "uniqByPupil": true, "content": [{"value": 1, "label": "Q",'
            ' "options": [{"value": "a", "label": "A"}]}, {"value": 2, "label": "Empty", "options": []}]}',
            "form_answers": [{"pupil_id": 7, "answers": '{"1": ["a"]}'}],
            "meetings": [
                {"id": 2, "start": "2026-12-01T17:15:00", "status": "FREE"},
                {"id": 1, "start": "2026-12-01T17:00:00", "status": "BOOKED", "registrations": [{"pupil_id": 7}]},
                {"id": 3, "start": "2026-12-01T17:30:00", "status": "CANCELED"},
            ],
        }
    )
    assert message["commentable"] and message["comments"] == 2
    survey = message["survey"]
    assert [q["id"] for q in survey["questions"]] == ["1"]  # a question without options is left out
    assert survey["answers"] == {"7": {"1": ["a"]}} and survey["one_per_child"]
    assert [(s["id"], s["booked"], s["child_id"]) for s in message["slots"]] == [("1", True, "7"), ("2", False, "")]
    assert _message({"id": "x", "survey": "not json"})["survey"] is None


def test_documents_to_sign() -> None:
    notebook = _document({"id": 3, "pupil_id": 7, "title": "Livret", "year": "2025-2026", "signatures": []}, "notebook")
    assert notebook["id"] == "notebook:3" and notebook["to_sign"] and notebook["year"] == "2025-2026"
    old = _document({"id": 2, "title": "Livret", "year": 2018, "signatures": []}, "notebook")
    assert not old["to_sign"]  # the portal does not ask for those
    attestation = _document({"id": 4, "type": "APER", "date": "2026-06-01", "signatures": [{"id": 1}]}, "attestation")
    assert attestation["title"] == "APER" and attestation["signed"] and attestation["year"] == "2026"


def test_event_on_its_own_day_and_meeting_presence() -> None:
    event = _message({"id": "e", "type": "event", "date": "2026-12-12", "visibility": "2026-11-20 08:00:00"})
    assert event["date"].startswith("2026-12-12")
    info = _message({"id": "i", "type": "info", "date": "2026-12-12", "visibility": "2026-11-20 08:00:00"})
    assert info["date"].startswith("2026-11-20")
    assert _message({"id": "m", "type": "meeting", "pupil_present": True})["presence"]
