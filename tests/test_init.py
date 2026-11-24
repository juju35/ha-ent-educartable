"""Tests of the Educartable integration with a patched client."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.educartable.api import EducartableAuthError, EducartableError, EducartableUnavailableError
from custom_components.educartable.const import DOMAIN
from custom_components.educartable.diagnostics import async_get_config_entry_diagnostics


class FakeApi:
    """Stands for EducartableApi: same methods, canned answers."""

    def __init__(self, session: Any, username: str, password: str, totp: str | None = None) -> None:
        self.username = username
        self.password = password
        self.pupils_fail = False
        self.carnet_fail = False
        self.force_auth_fail = False
        self.calls: list[tuple] = []
        self.extra_carnet: list[dict[str, Any]] = []
        self.extra_news: list[dict[str, Any]] = []
        self.comment_list: list[dict[str, Any]] = []
        self.livret = True
        self.extra_pupils: list[dict[str, Any]] = []

    def update_credentials(self, username: str, password: str, totp: str | None = None) -> None:
        self.username, self.password = username, password

    async def login(self) -> None:
        if self.force_auth_fail or (self.username, self.password) != ("parent", "secret"):
            raise EducartableAuthError("refused")

    async def user_info(self) -> dict[str, Any]:
        await self.login()
        return {"id": "p1", "name": "Parent Test"}

    async def pupils(self, parent_id: str) -> list[dict[str, Any]]:
        if self.pupils_fail:
            raise EducartableUnavailableError("HTTP 503")
        return [
            {"id": "e1", "firstname": "Alice", "name": "Test", "classroom_id": 3, "classroom": {"name": "CE2 A"}},
            *self.extra_pupils,
        ]

    async def lessons(self, parent_id: str, start: str, *, pupil_id: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "id": "h1",
                "title": "Poésie",
                "subject": "Français",
                "date": "2026-11-25",
                "achievement": "check",
                "achievements": [],
                "recipients": [{"model": "Pupil", "key": "e1", "id": "r9", "checked": False}],
            },
            {"id": "h2", "title": "Lecture", "date": "2026-11-26", "achievement": "read", "achievements": [4]},
        ]

    async def carnet(self, parent_id: str) -> list[dict[str, Any]]:
        if self.carnet_fail:
            raise EducartableError("HTTP 500")
        return [
            {
                "id": "c1",
                "title": "Sortie",
                "type": "info",
                "achievement": "sign",
                "achievements": [],
                "targetChildren": {"e1": True},
                "medias": [{"id": 77, "name": "Autorisation", "extension": "pdf"}],
            },
            {"id": "c2", "title": "Info", "type": "info", "achievement": "read", "achievements": [8]},
            *self.extra_carnet,
        ]

    async def news(self, parent_id: str) -> list[dict[str, Any]]:
        return [{"id": "n1", "title": "Kermesse", "type": "event", "date": "2026-11-28"}, *self.extra_news]

    async def achieve(self, *args: Any) -> None:
        self.calls.append(("achieve", *args))

    async def check(self, *args: Any) -> None:
        self.calls.append(("check", *args))

    async def media(self, media_id: str) -> tuple[bytes, str]:
        self.calls.append(("media", media_id))
        return b"%PDF-1.4 fake", "application/octet-stream"

    async def notebooks(self, parent_id: str) -> list[dict[str, Any]]:
        if not self.livret:
            raise EducartableError("HTTP 404")
        return [
            {
                "id": 31,
                "pupil_id": "e1",
                "title": "Livret scolaire",
                "type": "T1",
                "year": "2026-2027",
                "signatures": [],
                "file": {"id": 900, "direct_hash": "abc123"},
            },
            {"id": 30, "pupil_id": "e1", "title": "Livret", "year": "2017", "signatures": [], "file": None},
        ]

    async def attestations(self, parent_id: str) -> list[dict[str, Any]]:
        if not self.livret:
            raise EducartableError("HTTP 404")
        return [
            {"id": 41, "pupil_id": "e1", "type": "Savoir nager", "date": "2026-06-30", "hash": "h41", "signatures": [1]}
        ]

    async def notebook_file(self, file_id: str, direct_hash: str) -> tuple[bytes, str]:
        self.calls.append(("notebook_file", file_id, direct_hash))
        return b"%PDF-1.4 livret", "application/pdf"

    async def attestation_file(self, attestation_id: str, file_hash: str) -> tuple[bytes, str]:
        self.calls.append(("attestation_file", attestation_id, file_hash))
        return b"%PDF-1.4 attestation", "application/pdf"

    async def sign_document(self, *args: Any) -> None:
        self.calls.append(("sign_document", *args))

    async def comments(self, parent_id: str, message_id: str) -> list[dict[str, Any]]:
        return self.comment_list

    async def comment(self, *args: Any) -> dict[str, Any]:
        self.calls.append(("comment", *args))
        return {"id": 600}

    async def write_message(self, *args: Any) -> dict[str, Any]:
        self.calls.append(("write_message", *args))
        return {"id": 700}

    async def answer_survey(self, *args: Any) -> None:
        self.calls.append(("answer_survey", *args))

    async def delete_survey_answer(self, *args: Any) -> None:
        self.calls.append(("delete_survey_answer", *args))

    async def book(self, *args: Any) -> None:
        self.calls.append(("book", *args))

    async def cancel_booking(self, *args: Any) -> None:
        self.calls.append(("cancel_booking", *args))


@pytest.fixture
def api():
    holder: dict[str, FakeApi] = {}

    def factory(session, username, password, totp=None):
        holder["api"] = FakeApi(session, username, password, totp)
        return holder["api"]

    with patch("custom_components.educartable.EducartableApi", side_effect=factory):
        yield holder


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="p1",
        title="Educartable · Parent Test",
        data={CONF_USERNAME: "parent", CONF_PASSWORD: "secret"},
        options={"scan_interval": 30, "homework_days": 14},
    )


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_creates_sensors(hass: HomeAssistant, api) -> None:
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED

    # Two not-done/sign counts and a per-child homework count.
    homework = hass.states.get("sensor.alice_test_homework_to_do")
    assert homework is not None
    assert homework.state == "1"  # h2 is done (read), h1 still to tick
    assert hass.states.get("sensor.educartable_parent_test_liaison_book_to_sign").state == "1"  # c1 unsigned
    assert hass.states.get("sensor.educartable_parent_test_news").state == "1"


async def test_refresh_service(hass: HomeAssistant, api) -> None:
    await _setup(hass)
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.educartable_parent_test_news").state == "1"


async def test_auth_failure_triggers_reauth(hass: HomeAssistant, api) -> None:
    await _setup(hass)
    api["api"].force_auth_fail = True
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=31))
    await hass.async_block_till_done()
    flows = [f for f in hass.config_entries.flow.async_progress() if f["context"]["source"] == "reauth"]
    assert flows


async def test_diagnostics_redacts_credentials(hass: HomeAssistant, api) -> None:
    entry = await _setup(hass)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["entry"]["data"][CONF_USERNAME] == "**REDACTED**"
    assert diag["entry"]["data"][CONF_PASSWORD] == "**REDACTED**"


async def test_card_and_panel_attributes(hass: HomeAssistant, api) -> None:
    entry = await _setup(hass)
    homework = hass.states.get("sensor.alice_test_homework_to_do").attributes
    # Each homework sensor says whose homework it is, for the card and the panel
    assert homework["config_entry_id"] == entry.entry_id
    assert homework["child_id"] == "e1"
    assert homework["child"] == "Alice"
    last = hass.states.get("sensor.educartable_parent_test_last_update")
    assert last is not None and last.state not in ("unknown", "unavailable")
    assert last.attributes["config_entry_id"] == entry.entry_id
    assert [c["firstname"] for c in last.attributes["children"]] == ["Alice"]
    assert last.attributes["account"] == {"name": "Parent Test"}
    assert last.attributes["panel_tabs"] == ["homework", "words", "news", "documents"]
    assert last.attributes["hide_header"] == "off"


async def test_panel_follows_the_option(hass: HomeAssistant, api) -> None:
    from homeassistant.components import frontend

    entry = await _setup(hass)
    assert "educartable" in hass.data.get(frontend.DATA_PANELS, {})
    hass.config_entries.async_update_entry(entry, options={**entry.options, "show_panel": False})
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done()
    assert "educartable" not in hass.data.get(frontend.DATA_PANELS, {})


async def test_settings_websocket(hass: HomeAssistant, api, hass_ws_client) -> None:
    entry = await _setup(hass)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "educartable/settings"})
    res = await client.receive_json()
    assert res["success"]
    account = res["result"]["accounts"][0]
    assert account["entry_id"] == entry.entry_id
    assert account["options"]["panel_tabs"] == ["homework", "words", "news", "documents"]
    await client.send_json(
        {
            "id": 2,
            "type": "educartable/settings/update",
            "entry_id": entry.entry_id,
            "options": {"scan_interval": 5, "panel_tabs": ["news", "homework"], "hide_header": "all"},
        }
    )
    res = await client.receive_json()
    assert res["success"]
    # Cleaned: never faster than the minimum, tabs in the panel's order
    assert res["result"]["options"]["scan_interval"] == 10
    assert res["result"]["options"]["panel_tabs"] == ["homework", "news"]
    assert entry.options["hide_header"] == "all"
    await client.send_json({"id": 3, "type": "educartable/settings/update", "entry_id": "nope", "options": {}})
    res = await client.receive_json()
    assert not res["success"]
    assert res["error"]["code"] == "not_found"


async def test_options_flow_has_the_panel_options(hass: HomeAssistant, api) -> None:
    entry = await _setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "scan_interval": 60,
            "homework_days": 7,
            "show_panel": True,
            "panel_tabs": ["words"],
            "hide_header": "non_admin",
        },
    )
    assert result["data"] == {
        "scan_interval": 60,
        "homework_days": 7,
        "notify_services": [],
        "show_panel": True,
        "panel_tabs": ["words"],
        "hide_header": "non_admin",
    }


async def test_sign_and_mark_read_services(hass: HomeAssistant, api) -> None:
    await _setup(hass)
    await hass.services.async_call(DOMAIN, "sign", {"message_id": "c1", "name": "Parent Test"}, blocking=True)
    assert api["api"].calls == [("achieve", "p1", "c1", "sign", "Pupil", ["e1"], "Parent Test")]
    # Shown at once, before the next update
    assert hass.states.get("sensor.educartable_parent_test_liaison_book_to_sign").state == "0"
    # Nothing to read on a message that asks for a signature already given, a name too short is refused
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, "mark_read", {"message_id": "c1"}, blocking=True)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "sign", {"message_id": "c1", "name": "ab"}, blocking=True)


async def test_tick_homework_from_the_todo_list_and_the_websocket(hass: HomeAssistant, api, hass_ws_client) -> None:
    entry = await _setup(hass)
    todo = hass.states.get("todo.alice_test_homework")
    assert todo is not None and todo.state == "1"
    await hass.services.async_call(
        "todo",
        "update_item",
        {"item": "h1", "status": "completed"},
        target={"entity_id": todo.entity_id},
        blocking=True,
    )
    assert api["api"].calls == [("check", "p1", "h1", "r9", True)]
    assert hass.states.get("sensor.alice_test_homework_to_do").state == "0"
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "educartable/homework_done",
            "config_entry_id": entry.entry_id,
            "child_id": "e1",
            "homework_id": "h1",
            "done": False,
        }
    )
    assert (await client.receive_json())["success"]
    assert api["api"].calls[-1] == ("check", "p1", "h1", "r9", False)
    # A homework that asks only to be read has no box to tick
    await client.send_json(
        {
            "id": 2,
            "type": "educartable/homework_done",
            "config_entry_id": entry.entry_id,
            "child_id": "e1",
            "homework_id": "h2",
            "done": True,
        }
    )
    assert not (await client.receive_json())["success"]


async def test_calendar_shows_the_homework(hass: HomeAssistant, api) -> None:
    await _setup(hass)
    state = hass.states.get("calendar.educartable_parent_test_homework")
    assert state is not None
    assert "Poésie" in state.attributes["message"]


async def test_new_liaison_message_fires_an_event(hass: HomeAssistant, api) -> None:
    await _setup(hass)
    events = []
    hass.bus.async_listen("educartable_new_message", events.append)
    api["api"].extra_carnet.append({"id": "c3", "title": "Photos", "achievement": "sign", "achievements": []})
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)
    await hass.async_block_till_done()
    assert [e.data["id"] for e in events] == ["c3"]
    assert events[0].data["achievement"] == "sign"


async def test_file_view_serves_a_media_to_admins(hass: HomeAssistant, api, hass_client) -> None:
    entry = await _setup(hass)
    client = await hass_client()
    resp = await client.get(f"/api/educartable/file/{entry.entry_id}?media=77&name=Autorisation.pdf")
    assert resp.status == 200
    assert resp.headers["Content-Type"] == "application/pdf"
    assert "inline" in resp.headers["Content-Disposition"]
    assert api["api"].calls == [("media", "77")]


async def test_diagnostics_hold_counts_only(hass: HomeAssistant, api) -> None:
    entry = await _setup(hass)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    text = str(diag)
    assert "Alice" not in text and "Sortie" not in text and "Poésie" not in text
    assert diag["data"]["carnet"] == 2
    assert diag["data"]["achievements"] == ["check", "read", "sign"]


async def test_reconfigure_changes_the_credentials(hass: HomeAssistant, api) -> None:
    entry = await _setup(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    with patch(
        "custom_components.educartable.config_flow.validate", return_value=({"id": "p1", "name": "Parent Test"}, None)
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: "parent2", CONF_PASSWORD: "secret2"}
        )
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_USERNAME] == "parent2"


SURVEY = {
    "id": "c5",
    "title": "Cantine",
    "type": "info",
    "achievement": "survey",
    "achievements": [],
    "targetChildren": {"e1": True},
    "commentable": True,
    "comments_count": 1,
    "survey": {
        "deadline": "2099-12-31",
        "anonymous": False,
        "content": [
            {
                "value": "q1",
                "label": "Repas",
                "multiple": False,
                "options": [{"value": "a", "label": "Oui"}, {"value": "b", "label": "Non"}],
            },
            {
                "value": "q2",
                "label": "Jours",
                "multiple": True,
                "options": [{"value": "l", "label": "Lundi"}, {"value": "m", "label": "Mardi"}],
            },
        ],
    },
    "form_answers": [],
}

MEETING = {
    "id": "n2",
    "title": "Réunion parents",
    "type": "meeting",
    "achievement": "book",
    "achievements": [],
    "targetChildren": {"e1": True},
    "meetings": [
        {
            "id": 51,
            "start": "2026-12-01T17:00:00",
            "stop": "2026-12-01T17:15:00",
            "status": "FREE",
            "registrations": [],
        },
        {
            "id": 52,
            "start": "2026-12-01T17:15:00",
            "stop": "2026-12-01T17:30:00",
            "status": "BOOKED",
            "registrations": [{"pupil_id": "zz"}],
        },
        {
            "id": 50,
            "start": "2026-12-01T16:45:00",
            "stop": "2026-12-01T17:00:00",
            "status": "FREE",
            "registrations": [],
        },
    ],
}


async def test_livret_documents_sensor_sign_and_file(hass: HomeAssistant, api, hass_client) -> None:
    entry = await _setup(hass)
    state = hass.states.get("sensor.educartable_parent_test_school_reports_to_sign")
    assert state.state == "1"  # the 2026 livret; the 2017 one is not asked, the attestation is signed
    docs = state.attributes["documents"]
    assert docs[0]["id"] == "notebook:31" and docs[0]["to_sign"] and docs[0]["child"] == "Alice"
    assert "abc123" not in str(state.attributes)  # the file's hash never reaches the state machine
    await hass.services.async_call(
        DOMAIN, "sign_document", {"document_id": "notebook:31", "name": "Camille Test"}, blocking=True
    )
    assert ("sign_document", "p1", "notebook", "31", "Camille Test") in api["api"].calls
    assert hass.states.get("sensor.educartable_parent_test_school_reports_to_sign").state == "0"
    client = await hass_client()
    resp = await client.get(f"/api/educartable/file/{entry.entry_id}?document=attestation:41&name=Nager.pdf")
    assert resp.status == 200 and resp.headers["Content-Type"] == "application/pdf"
    assert ("attestation_file", "41", "h41") in api["api"].calls
    resp = await client.get(f"/api/educartable/file/{entry.entry_id}?document=notebook:30")
    assert resp.status == 502  # no file for it


async def test_no_livret_on_the_account_is_no_error(hass: HomeAssistant, api) -> None:
    with patch.object(FakeApi, "notebooks", side_effect=EducartableError("HTTP 404")):
        await _setup(hass)
    state = hass.states.get("sensor.educartable_parent_test_school_reports_to_sign")
    assert state.state == "0"
    assert [d["id"] for d in state.attributes["documents"]] == ["attestation:41"]  # attestations still read


async def test_reply_records_the_awaited_answer(hass: HomeAssistant, api, hass_ws_client) -> None:
    entry = await _setup(hass)
    api["api"].extra_carnet.append({**SURVEY, "id": "c6", "achievement": "comment", "survey": None})
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)
    api["api"].comment_list = [
        {"id": 90, "user_id": "p1", "body": "<p>Bonjour</p>", "user": {"firstname": "Parent", "name": "Test"}},
        {
            "id": 91,
            "user_id": "t1",
            "body": "Merci",
            "user": {"firstname": "Mme", "name": "Prof"},
            "created": "2026-11-20 10:00:00",
        },
    ]
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "educartable/comments", "config_entry_id": entry.entry_id, "message_id": "c6"}
    )
    msg = await client.receive_json()
    assert [(c["text"], c["mine"]) for c in msg["result"]["comments"]] == [("Bonjour", True), ("Merci", False)]
    await hass.services.async_call(DOMAIN, "reply", {"message_id": "c6", "text": "D'accord"}, blocking=True)
    calls = api["api"].calls
    assert ("comment", "p1", "c6", "D'accord", "90") in calls
    assert ("achieve", "p1", "c6", "comment", "Pupil", ["e1"]) in calls
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, "reply", {"message_id": "c1", "text": "Non"}, blocking=True)


async def test_answer_a_survey(hass: HomeAssistant, api) -> None:
    api_extra = [SURVEY]
    with patch.object(FakeApi, "carnet", autospec=True, side_effect=lambda self, pid: api_extra):
        await _setup(hass)
    attrs = hass.states.get("sensor.educartable_parent_test_liaison_book_to_sign").attributes
    survey = attrs["messages"][0]["survey"]
    assert [q["id"] for q in survey["questions"]] == ["q1", "q2"] and survey["answers"] == {}
    with pytest.raises(HomeAssistantError):  # two answers to a single-choice question
        await hass.services.async_call(
            DOMAIN, "answer_survey", {"message_id": "c5", "answers": {"q1": ["a", "b"], "q2": ["l"]}}, blocking=True
        )
    with pytest.raises(HomeAssistantError):  # a question left out
        await hass.services.async_call(
            DOMAIN, "answer_survey", {"message_id": "c5", "answers": {"q1": "a"}}, blocking=True
        )
    await hass.services.async_call(
        DOMAIN, "answer_survey", {"message_id": "c5", "answers": {"q1": "a", "q2": ["l", "m"]}}, blocking=True
    )
    assert ("answer_survey", "c5", "e1", {"q1": ["a"], "q2": ["l", "m"]}) in api["api"].calls
    message = hass.states.get("sensor.educartable_parent_test_liaison_book_to_sign").attributes["messages"][0]
    assert message["survey"]["answers"] == {"e1": {"q1": ["a"], "q2": ["l", "m"]}} and message["achieved"]
    # Answering again replaces the answer given.
    await hass.services.async_call(
        DOMAIN, "answer_survey", {"message_id": "c5", "answers": {"q1": "b", "q2": "m"}}, blocking=True
    )
    assert ("delete_survey_answer", "c5", "e1") in api["api"].calls


async def test_book_and_cancel_an_appointment(hass: HomeAssistant, api) -> None:
    with patch.object(FakeApi, "news", autospec=True, side_effect=lambda self, pid: [MEETING]):
        await _setup(hass)
        slots = hass.states.get("sensor.educartable_parent_test_news").attributes["news"][0]["slots"]
        # Free slots in time order; the one booked by another family is not offered.
        assert [s["id"] for s in slots] == ["50", "51"]
        await hass.services.async_call(DOMAIN, "book_appointment", {"slot_id": "51"}, blocking=True)
        assert ("book", "51", "e1") in api["api"].calls
        news = hass.states.get("sensor.educartable_parent_test_news").attributes["news"][0]
        assert news["achieved"] and [s["id"] for s in news["slots"] if s["booked"]] == ["51"]
        with pytest.raises(HomeAssistantError):  # Alice already has one
            await hass.services.async_call(
                DOMAIN, "book_appointment", {"slot_id": "50", "child_id": "e1"}, blocking=True
            )
        await hass.services.async_call(DOMAIN, "cancel_appointment", {"slot_id": "51"}, blocking=True)
        assert ("cancel_booking", "51") in api["api"].calls


async def test_write_a_message_per_classroom(hass: HomeAssistant, api) -> None:
    await _setup(hass)
    api["api"].extra_pupils.append({"id": "e2", "firstname": "Bob", "name": "Test", "classroom_id": 4})
    api["api"].extra_pupils.append(
        {"id": "e3", "firstname": "Cléo", "name": "Test", "classroom_id": 3, "writable": False}
    )
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)
    await hass.services.async_call(
        DOMAIN, "write_message", {"children": ["e1", "e2"], "title": "Absence", "text": "Malade"}, blocking=True
    )
    writes = [c for c in api["api"].calls if c[0] == "write_message"]
    assert writes == [
        ("write_message", "p1", ["e1"], "Absence", "Malade"),
        ("write_message", "p1", ["e2"], "Absence", "Malade"),
    ]
    with pytest.raises(HomeAssistantError):  # paused by the teacher
        await hass.services.async_call(
            DOMAIN, "write_message", {"children": ["e3"], "title": "A", "text": "B"}, blocking=True
        )


async def test_migration_adds_the_documents_tab(hass: HomeAssistant, api) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="p1",
        title="Educartable · Parent Test",
        data={CONF_USERNAME: "parent", CONF_PASSWORD: "secret"},
        options={"panel_tabs": ["homework", "words"]},
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.minor_version == 2
    assert entry.options["panel_tabs"] == ["homework", "words", "documents"]
