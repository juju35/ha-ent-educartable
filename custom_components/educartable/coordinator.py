"""Data update coordinator for Educartable."""

from __future__ import annotations

import html
import logging
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.translation import async_get_translations
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
    CONF_NOTIFY,
    CONF_SCAN_INTERVAL,
    DEFAULT_HOMEWORK_DAYS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_NEW_HOMEWORK,
    EVENT_NEW_MESSAGE,
    EVENT_NEW_NEWS,
    MESSAGES_KEPT,
    MIN_SCAN_INTERVAL,
    NEWS_KEPT,
)
from .secret import SecretNotFoundError, async_credentials

_LOGGER = logging.getLogger(__name__)

# Attachments fetched for the card are kept a few minutes, within a size budget.
FILE_CACHE_TTL = 300
FILE_CACHE_BYTES = 30 * 1024 * 1024

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
    # When this update read the portal.
    updated: datetime | None = None


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


# The action a message asks of the family (its `achievement`), as the portal's app names it.
ACHIEVEMENTS = ("read", "sign", "check", "comment", "book", "survey")


def plain_text(value: Any) -> str:
    """A message body (HTML from the portal's editor) as plain text, paragraphs kept."""
    text = _str(value)
    text = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6])>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "• ", text)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(line.strip() for line in text.splitlines())).strip()


def _author(raw: dict[str, Any]) -> str:
    user = raw.get("user") or {}
    if not isinstance(user, dict):
        return ""
    return " ".join(p for p in (_str(user.get("firstname")), _str(user.get("name"))) if p).strip()


def _medias(raw: dict[str, Any]) -> list[dict[str, str]]:
    medias = raw.get("medias") or []
    out = []
    for m in medias if isinstance(medias, list) else []:
        if isinstance(m, dict) and m.get("id") is not None:
            ext = _str(m.get("extension")).lstrip(".")
            name = _str(m.get("name")) or _str(m.get("id"))
            if ext and not name.lower().endswith(f".{ext.lower()}"):
                name = f"{name}.{ext}"
            out.append({"id": _str(m.get("id")), "name": name, "extension": ext.lower()})
    return sorted(out, key=lambda m: m["name"].casefold())


def _pupil_recipients(raw: dict[str, Any]) -> list[dict[str, Any]]:
    recipients = raw.get("recipients") or []
    return [r for r in recipients if isinstance(r, dict) and r.get("model") == "Pupil"]


def _children(raw: dict[str, Any]) -> list[str]:
    """Ids of the pupils a message concerns: its target children, else its pupils, else its pupil recipients."""
    target = raw.get("targetChildren")
    if isinstance(target, dict) and target:
        return [str(k) for k in target]
    pupils = raw.get("pupils")
    if isinstance(pupils, list) and pupils:
        return [_str(p.get("id") if isinstance(p, dict) else p) for p in pupils]
    return [_str(r.get("key")) for r in _pupil_recipients(raw)]


def _common(raw: dict[str, Any]) -> dict[str, Any]:
    achievement = _str(raw.get("achievement"))
    return {
        "id": _str(raw.get("id")),
        "title": _str(raw.get("title")),
        "text": plain_text(raw.get("body")),
        "type": _str(raw.get("type")),
        "author": _author(raw),
        "achievement": achievement if achievement in ACHIEVEMENTS else "",
        # The family did what the message asks once it has an achievement (the app's own test).
        "achieved": bool(raw.get("achievements")),
        "medias": _medias(raw),
    }


def _homework(raw: dict[str, Any], pupil_id: str = "") -> dict[str, Any]:
    item = _common(raw)
    recipient = next((r for r in _pupil_recipients(raw) if _str(r.get("key")) == pupil_id), None)
    if item["achievement"] == "check" and recipient is not None:
        # "To do": ticked pupil by pupil in its recipients.
        done = bool(recipient.get("checked"))
    else:
        done = item["achieved"]
    subject = raw.get("subject")
    return {
        **item,
        "subject": _str(subject.get("name") if isinstance(subject, dict) else subject or raw.get("discipline")),
        "due": _iso(raw.get("date")),
        "done": done,
        "recipient_id": _str(recipient.get("id")) if recipient else "",
    }


def _message(raw: dict[str, Any]) -> dict[str, Any]:
    item = _common(raw)
    return {
        **item,
        "date": _iso(raw.get("visibility") or raw.get("date") or raw.get("created")),
        "children": _children(raw),
        # Liaison book: still to sign when it asks for a signature that nobody gave yet.
        "to_sign": item["achievement"] == "sign" and not item["achieved"],
        "to_do": bool(item["achievement"]) and not item["achieved"],
    }


class EducartableCoordinator(DataUpdateCoordinator[EducartableData]):
    """Poll one Educartable family account."""

    config_entry: EducartableConfigEntry

    def __init__(self, hass: HomeAssistant, entry: EducartableConfigEntry, api: EducartableApi) -> None:
        minutes = max(MIN_SCAN_INTERVAL, int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)))
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=timedelta(minutes=minutes))
        self.api = api
        self.homework_days = int(entry.options.get(CONF_HOMEWORK_DAYS, DEFAULT_HOMEWORK_DAYS))
        self.notify_services: list[str] = list(entry.options.get(CONF_NOTIFY, []))
        # Ids seen by kind, from the first successful read: only what appears after it fires an event.
        self._seen: dict[str, set[str]] = {}
        self._file_cache: OrderedDict[str, tuple[float, bytes, str]] = OrderedDict()

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
            account={"parent_id": parent_id, "name": _str(info.get("name") or info.get("firstname"))},
            updated=dt_util.utcnow(),
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
                    _homework(h, pupil["id"]) for h in raw if (d := _due(h.get("date"))) is None or d <= cutoff
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
        # The first names of the children a message concerns, for the card, the panel and the events.
        names = {p["id"]: p["firstname"] or p["name"] for p in data.pupils}
        for message in (*data.carnet, *data.news):
            message["child"] = " · ".join(names[c] for c in message["children"] if c in names)
        self._fire_new(data)
        return data

    def _fire_new(self, data: EducartableData) -> None:
        """Fire educartable_new_* for homework to do, liaison-book messages and news seen the first time.

        A kind starts being followed at its first successful read, which only records what is there; the ids kept
        are the ones of the last read, so the set stays small and an item never fires twice.
        """
        names = {p["id"]: p["firstname"] or p["name"] for p in data.pupils}
        homework = [
            {**h, "child_id": pid, "child": names.get(pid, "")} for pid, items in data.homework.items() for h in items
        ]
        kinds = {
            "homework": (
                "homework",
                homework,
                lambda h: not h["done"],
                EVENT_NEW_HOMEWORK,
                ("child_id", "child", "title", "subject", "due"),
            ),
            "message": (
                "carnet",
                data.carnet,
                lambda m: m["to_do"],
                EVENT_NEW_MESSAGE,
                ("child", "title", "achievement", "author"),
            ),
            "news": ("news", data.news, lambda _: True, EVENT_NEW_NEWS, ("title", "type", "author")),
        }
        for kind, (section, items, pending, event, fields) in kinds.items():
            if section in data.stale:
                continue  # Content of the update before: nothing new to look at.
            key = (lambda i: f"{i['child_id']}:{i['id']}") if kind == "homework" else (lambda i: i["id"])
            seen = self._seen.get(kind)
            self._seen[kind] = {key(item) for item in items}
            if seen is None:
                continue
            for item in items:
                if pending(item) and key(item) not in seen:
                    self._fire(event, {"id": item["id"], **{f: item[f] for f in fields}})

    def _fire(self, event: str, data: dict[str, Any]) -> None:
        data = {"config_entry_id": self.config_entry.entry_id, **data}
        self.hass.bus.async_fire(event, data)
        if self.notify_services:
            self.hass.async_create_task(self._async_notify(event, data), f"{DOMAIN}_notify")

    async def _async_notify(self, event: str, data: dict[str, Any]) -> None:
        """Tell the notify actions chosen in the options, in Home Assistant's language."""
        strings = await async_get_translations(self.hass, self.hass.config.language, "exceptions", [DOMAIN])
        kind = event.removeprefix(f"{DOMAIN}_")

        def text(key: str, **placeholders: Any) -> str:
            message = strings.get(f"component.{DOMAIN}.exceptions.{key}.message", key)
            try:
                return message.format(**placeholders)
            except (KeyError, IndexError, ValueError):
                return message

        title = text(f"notify_{kind}", child=data.get("child") or "")
        parts = (data.get("title"), data.get("subject") or data.get("author"), data.get("due"))
        message = " · ".join(p for p in parts if p)
        for service in self.notify_services:
            target = service.removeprefix("notify.")
            if not self.hass.services.has_service("notify", target):
                _LOGGER.warning("Notify action notify.%s not found", target)
                continue
            try:
                await self.hass.services.async_call(
                    "notify",
                    target,
                    {"title": title, "message": message or title, "data": {"tag": f"{kind}_{data['id']}"}},
                )
            except Exception:  # noqa: BLE001 - a broken notifier must not stop the others
                _LOGGER.exception("Could not notify with notify.%s", target)

    # ── Actions on the portal ───────────────────────────────────────────────────────────────────────────────

    def _parent_id(self) -> str:
        parent_id = (self.data.account.get("parent_id") if self.data else "") or ""
        if not parent_id:
            raise EducartableError("account not read yet")
        return parent_id

    def _find_message(self, message_id: str) -> dict[str, Any]:
        data = self.data
        for message in (*(data.carnet if data else []), *(data.news if data else [])):
            if message["id"] == message_id:
                return message
        for items in data.homework.values() if data else []:
            for item in items:
                if item["id"] == message_id:
                    return item
        raise EducartableError("unknown message")

    async def async_achieve(self, message_id: str, name: str = "") -> None:
        """Do what a message asks (sign with the signer's name, mark as read), as the portal's app does."""
        message = self._find_message(message_id)
        action = message["achievement"]
        if action not in ("sign", "read"):
            raise EducartableError(f"nothing to sign or read on this message ({action or 'none'})")
        if action == "sign" and len(name.strip()) < 3:
            raise EducartableError("the signer's name is too short")
        children = message.get("children") or list(self.data.homework)
        await self.api.achieve(
            self._parent_id(), message_id, action, "Pupil", children, name.strip() if action == "sign" else ""
        )
        # Shown at once; the next update confirms it. New dicts: the old ones are shared with written states.
        self.data = replace(
            self.data,
            carnet=[_achieved(m) if m["id"] == message_id else m for m in self.data.carnet],
            news=[_achieved(m) if m["id"] == message_id else m for m in self.data.news],
        )
        self.async_update_listeners()

    async def async_set_homework_done(self, pupil_id: str, homework_id: str, done: bool) -> None:
        """Tick a homework for one pupil (its recipient entry), or record it done when it asks to be checked."""
        item = (
            next((h for h in self.data.homework.get(pupil_id, []) if h["id"] == homework_id), None)
            if self.data
            else None
        )
        if item is None:
            raise EducartableError("unknown homework")
        if not item["recipient_id"]:
            raise EducartableError("this homework cannot be ticked")
        await self.api.check(self._parent_id(), homework_id, item["recipient_id"], done)
        homework = dict(self.data.homework)
        homework[pupil_id] = [{**h, "done": done} if h["id"] == homework_id else h for h in homework[pupil_id]]
        self.data = replace(self.data, homework=homework)
        self.async_update_listeners()

    async def async_media(self, media_id: str) -> tuple[bytes, str]:
        """An attachment, kept a few minutes within a size budget: a redraw or a second look is instant."""
        now = time.monotonic()
        hit = self._file_cache.get(media_id)
        if hit and now - hit[0] < FILE_CACHE_TTL:
            self._file_cache.move_to_end(media_id)
            return hit[1], hit[2]
        body, content_type = await self.api.media(media_id)
        self._file_cache[media_id] = (now, body, content_type)
        total = sum(len(v[1]) for v in self._file_cache.values())
        while total > FILE_CACHE_BYTES and len(self._file_cache) > 1:
            _, old = self._file_cache.popitem(last=False)
            total -= len(old[1])
        return body, content_type


def _achieved(message: dict[str, Any]) -> dict[str, Any]:
    return {**message, "achieved": True, "to_sign": False, "to_do": False}
