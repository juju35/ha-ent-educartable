"""Data update coordinator for Educartable."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    EducartableApi,
    EducartableAuthError,
    EducartableError,
    EducartableUnavailableError,
)
from .const import (
    CONF_HOMEWORK_DAYS,
    CONF_SCAN_INTERVAL,
    DEFAULT_HOMEWORK_DAYS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MESSAGES_KEPT,
    MIN_SCAN_INTERVAL,
    NEWS_KEPT,
)
from .secret import SecretNotFoundError, async_credentials

_LOGGER = logging.getLogger(__name__)

type EducartableConfigEntry = ConfigEntry[EducartableCoordinator]


@dataclass
class EducartableData:
    """Everything one update read from Educartable."""

    account: dict[str, Any] = field(default_factory=dict)
    pupils: list[dict[str, Any]] = field(default_factory=list)
    homework: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    carnet: list[dict[str, Any]] = field(default_factory=list)
    news: list[dict[str, Any]] = field(default_factory=list)
    # Sections whose last read failed: their content is the one of the update before.
    stale: list[str] = field(default_factory=list)


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def parse_when(value: Any) -> datetime | date | None:
    """An Educartable date: milliseconds, an ISO date or an ISO date-time."""
    if isinstance(value, int | float) and not isinstance(value, bool):
        try:
            return dt_util.utc_from_timestamp(value / 1000)
        except (OverflowError, OSError, ValueError):
            return None
    text = _str(value).strip()
    if not text:
        return None
    parsed = None if len(text) == 10 else dt_util.parse_datetime(text)
    if parsed is None:
        return dt_util.parse_date(text[:10])
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt_util.get_default_time_zone())


def _iso(value: Any) -> str | None:
    when = parse_when(value)
    if isinstance(when, datetime):
        return dt_util.as_local(when).isoformat()
    return when.isoformat() if when else None


def _pupil(raw: dict[str, Any]) -> dict[str, Any]:
    classroom = raw.get("classroom") or {}
    grade = raw.get("grade") or {}
    name = " ".join(p for p in (raw.get("firstname"), raw.get("name")) if p).strip()
    return {
        "id": _str(raw.get("id")),
        "name": name or _str(raw.get("firstname")) or "?",
        "firstname": _str(raw.get("firstname")),
        "classroom": _str(classroom.get("name")),
        "teacher": _str(classroom.get("teacher_name")),
        "grade": _str(grade.get("letters") or grade.get("name")),
    }


def _due(value: Any) -> date | None:
    when = parse_when(value)
    if isinstance(when, datetime):
        return dt_util.as_local(when).date()
    return when


def _homework(raw: dict[str, Any]) -> dict[str, Any]:
    achievements = raw.get("achievements") or []
    return {
        "id": _str(raw.get("id")),
        "title": _str(raw.get("title")),
        "subject": _str(raw.get("subject") or raw.get("discipline")),
        "due": _iso(raw.get("date")),
        "done": bool(achievements),
    }


def _message(raw: dict[str, Any]) -> dict[str, Any]:
    recipients = raw.get("recipients") or []
    return {
        "id": _str(raw.get("id")),
        "title": _str(raw.get("title")),
        "type": _str(raw.get("type")),
        "date": _iso(raw.get("date") or raw.get("created")),
        "to_sign": any(not r.get("checked", False) for r in recipients) if recipients else False,
    }


class EducartableCoordinator(DataUpdateCoordinator[EducartableData]):
    """Poll one Educartable family account."""

    config_entry: EducartableConfigEntry

    def __init__(self, hass: HomeAssistant, entry: EducartableConfigEntry, api: EducartableApi) -> None:
        minutes = max(MIN_SCAN_INTERVAL, int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)))
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=timedelta(minutes=minutes))
        self.api = api
        self.homework_days = int(entry.options.get(CONF_HOMEWORK_DAYS, DEFAULT_HOMEWORK_DAYS))

    async def _async_update_data(self) -> EducartableData:
        try:
            self.api.update_credentials(*await async_credentials(self.hass, self.config_entry.data))
        except SecretNotFoundError as err:
            raise UpdateFailed(str(err)) from err
        try:
            return await self._read()
        except EducartableAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except EducartableError as err:
            raise UpdateFailed(str(err)) from err

    async def _read(self) -> EducartableData:
        previous = self.data or EducartableData()
        info = await self.api.user_info()
        parent_id = _str(info.get("id"))
        if not parent_id:
            raise UpdateFailed("no parent id in the account")
        data = EducartableData(
            account={"parent_id": parent_id, "name": _str(info.get("name") or info.get("firstname"))}
        )
        today = dt_util.now().date()
        start = today.isoformat()
        cutoff = today + timedelta(days=self.homework_days)

        try:
            data.pupils = [_pupil(p) for p in await self.api.pupils(parent_id)]
        except EducartableUnavailableError:
            data.pupils, _ = previous.pupils, data.stale.append("pupils")

        for pupil in data.pupils:
            try:
                raw = await self.api.lessons(parent_id, start, pupil_id=pupil["id"])
                # Keep homework due within the window (and anything undated), newest cap applied client-side.
                data.homework[pupil["id"]] = [
                    _homework(h) for h in raw if (d := _due(h.get("date"))) is None or d <= cutoff
                ]
            except EducartableUnavailableError:
                data.homework[pupil["id"]] = previous.homework.get(pupil["id"], [])
                if "homework" not in data.stale:
                    data.stale.append("homework")

        try:
            data.carnet = [_message(m) for m in await self.api.carnet(parent_id)][:MESSAGES_KEPT]
        except EducartableUnavailableError:
            data.carnet, _ = previous.carnet, data.stale.append("carnet")
        try:
            data.news = [_message(m) for m in await self.api.news(parent_id)][:NEWS_KEPT]
        except EducartableUnavailableError:
            data.news, _ = previous.news, data.stale.append("news")
        return data
