"""Tests of the Educartable integration with a patched client."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
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
        return [{"id": "e1", "firstname": "Alice", "name": "Test", "classroom": {"name": "CE2 A"}}]

    async def lessons(self, parent_id: str, start: str, *, pupil_id: str | None = None) -> list[dict[str, Any]]:
        return [
            {"id": "h1", "title": "Poésie", "date": "2026-11-25", "achievements": []},
            {"id": "h2", "title": "Lecture", "date": "2026-11-26", "achievements": [{"action": "read"}]},
        ]

    async def carnet(self, parent_id: str) -> list[dict[str, Any]]:
        if self.carnet_fail:
            raise EducartableError("HTTP 500")
        return [
            {"id": "c1", "title": "Sortie", "type": "info", "recipients": [{"id": "r1", "checked": False}]},
            {"id": "c2", "title": "Info", "type": "info", "recipients": [{"id": "r2", "checked": True}]},
        ]

    async def news(self, parent_id: str) -> list[dict[str, Any]]:
        return [{"id": "n1", "title": "Kermesse", "type": "event", "date": "2026-11-28"}]


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
    assert homework.state == "1"  # h2 is done
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
    assert last.attributes["panel_tabs"] == ["homework", "words", "news"]
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
    assert account["options"]["panel_tabs"] == ["homework", "words", "news"]
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
        "show_panel": True,
        "panel_tabs": ["words"],
        "hide_header": "non_admin",
    }
