"""Data update coordinator for Educartable."""

from __future__ import annotations

import html
import json
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
    ACTIVITIES_KEPT,
    APPOINTMENT_DAYS,
    CONF_HOMEWORK_DAYS,
    CONF_NOTIFY,
    CONF_SCAN_INTERVAL,
    DEFAULT_HOMEWORK_DAYS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_NEW_ACTIVITY,
    EVENT_NEW_DOCUMENT,
    EVENT_NEW_HOMEWORK,
    EVENT_NEW_MESSAGE,
    EVENT_NEW_NEWS,
    MESSAGES_KEPT,
    MIN_SCAN_INTERVAL,
    NEWS_KEPT,
    NOTIFICATIONS_KEPT,
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
    # The pupils' livret: notebooks and attestations, signed as consulted.
    documents: list[dict[str, Any]] = field(default_factory=list)
    # The cahier de vie, the portal's unread notifications and the appointments booked ahead.
    activities: list[dict[str, Any]] = field(default_factory=list)
    notifications: list[dict[str, Any]] = field(default_factory=list)
    appointments: list[dict[str, Any]] = field(default_factory=list)
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
        # A new message goes to the child's classroom; the teacher can pause them for a while.
        "classroom_id": _str(raw.get("classroom_id") or classroom.get("id")),
        "writable": raw.get("writable") is not False,
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


def _links(raw: dict[str, Any]) -> list[dict[str, str]]:
    """Web links attached to a message (a video, a site): only http(s) addresses are kept."""
    out = []
    for link in raw.get("links") or []:
        url = _str(link.get("url")) if isinstance(link, dict) else ""
        if url.startswith(("https://", "http://")):
            out.append({"url": url, "title": _str(link.get("title")) or url, "type": _str(link.get("type"))})
    return out


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
        "links": _links(raw),
        # An archived message (a past school year) is read only.
        "archived": bool(raw.get("archived")),
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


def _json(value: Any) -> Any:
    """A field the portal sends either as JSON text or already decoded."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return value


# A survey or a list of slots is cut to this: enough for any school form, small enough for the state machine.
SURVEY_QUESTIONS_KEPT = 20
SLOTS_KEPT = 40


def _survey(raw: dict[str, Any]) -> dict[str, Any] | None:
    """A message's survey: its questions and options, and the children already answered for (with what)."""
    survey = _json(raw.get("survey"))
    if not isinstance(survey, dict) or not isinstance(survey.get("content"), list):
        return None
    questions = []
    for q in survey["content"][:SURVEY_QUESTIONS_KEPT]:
        if not isinstance(q, dict) or q.get("value") is None:
            continue
        options = [
            {"id": _str(o.get("value")), "label": _str(o.get("label"))}
            for o in q.get("options") or []
            if isinstance(o, dict) and o.get("value") is not None
        ]
        if options:
            questions.append(
                {
                    "id": _str(q["value"]),
                    "label": _str(q.get("label")),
                    "multiple": bool(q.get("multiple")),
                    "options": options,
                }
            )
    if not questions:
        return None
    answers: dict[str, dict[str, list[str]]] = {}
    for answer in raw.get("form_answers") or []:
        if not isinstance(answer, dict) or answer.get("pupil_id") is None:
            continue
        chosen = _json(answer.get("answers"))
        answers[_str(answer["pupil_id"])] = (
            {_str(k): [_str(v) for v in vals] for k, vals in chosen.items() if isinstance(vals, list)}
            if isinstance(chosen, dict)
            else {}
        )
    return {
        "deadline": _iso(survey.get("deadline")),
        "anonymous": bool(survey.get("anonymous")),
        # One answer per child: another parent may already have given it.
        "one_per_child": bool(survey.get("uniqByPupil")),
        "questions": questions,
        "answers": answers,
    }


def _slots(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Appointment slots of a message: the free ones, and the ones booked for the family's children."""
    slots = []
    for slot in raw.get("meetings") or []:
        if not isinstance(slot, dict) or slot.get("id") is None:
            continue
        status = _str(slot.get("status")).upper()
        registrations = [r for r in slot.get("registrations") or [] if isinstance(r, dict)]
        if status == "FREE":
            child = ""
        elif status == "BOOKED" and registrations:
            child = _str(registrations[0].get("pupil_id"))
        else:
            continue  # Booked by another family: not offered.
        slots.append(
            {
                "id": _str(slot["id"]),
                "start": _iso(slot.get("start")),
                "end": _iso(slot.get("stop") or slot.get("end")),
                "location": _str(slot.get("location")),
                "booked": status == "BOOKED",
                "child_id": child,
            }
        )
    slots.sort(key=lambda x: x["start"] or "")
    booked = [x for x in slots if x["booked"]]
    return booked + [x for x in slots if not x["booked"]][: max(0, SLOTS_KEPT - len(booked))]


def _message(raw: dict[str, Any]) -> dict[str, Any]:
    item = _common(raw)
    recipients = raw.get("recipients") or []
    return {
        **item,
        # An event is shown on its own day; the other messages on the day they were published.
        "date": _iso(
            (raw.get("date") if raw.get("type") == "event" else None)
            or raw.get("visibility")
            or raw.get("date")
            or raw.get("created")
        ),
        "children": _children(raw),
        # The child is expected at the parent meeting too.
        "presence": bool(raw.get("pupil_present")),
        # Liaison book: still to sign when it asks for a signature that nobody gave yet.
        "to_sign": item["achievement"] == "sign" and not item["achieved"],
        "to_do": bool(item["achievement"]) and not item["achieved"],
        # A private conversation with the teacher is open on it (the portal's own flag), and how long it is.
        "commentable": bool(raw.get("commentable")) and not raw.get("archived"),
        "comments": int(raw.get("comments_count") or 0),
        "survey": _survey(raw),
        "slots": _slots(raw),
        # A message to the parents of a classroom without recipients is achieved by the parent, not the pupils.
        "parent_scope": raw.get("scope_model") == "Classroom" and not recipients,
    }


def _activity(raw: dict[str, Any]) -> dict[str, Any]:
    """A post of the cahier de vie: its text and photos, its likes (the family's own one too) and its conversation."""
    item = _common(raw)
    return {
        **item,
        "date": _iso(raw.get("date") or raw.get("visibility") or raw.get("created")),
        "children": _children(raw),
        "likes": int(raw.get("likes_count") or 0),
        # The family's like: its id, needed to take it back.
        "like_id": _str(raw.get("liked")) if raw.get("liked") else "",
        "commentable": bool(raw.get("commentable")) and not raw.get("archived"),
        "comments": int(raw.get("comments_count") or 0),
    }


def _epoch_iso(value: Any) -> str | None:
    """A time the portal gives in seconds (notification payloads), or as text."""
    if isinstance(value, (int, float)) and value > 0:
        return dt_util.utc_from_timestamp(value).isoformat()
    return _iso(value)


def _notification(raw: dict[str, Any]) -> dict[str, Any]:
    """A notification of the portal: what it is about, its text, and for a cancelled appointment when it was."""
    payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
    author = payload.get("author") if isinstance(payload.get("author"), dict) else {}
    return {
        "id": _str(raw.get("id")),
        "type": _str(raw.get("type")).replace(".parents", ""),
        "subject": _str(payload.get("subject_type")),
        "subject_id": _str(payload.get("subject_id")),
        "text": plain_text(payload.get("content")),
        "author": " ".join(p for p in (_str(author.get("firstname")), _str(author.get("name"))) if p),
        "start": _epoch_iso(payload.get("start")),
        "end": _epoch_iso(payload.get("stop")),
        "date": _iso(raw.get("created")),
    }


def _for_family(raw: dict[str, Any]) -> bool:
    """An unread notification of the family app (the portal's own filter)."""
    app = _str(raw.get("app")).strip().lower()
    return not raw.get("read") and (app in ("educartablefamily", "family") or ".parents" in _str(raw.get("type")))


def _appointment(raw: dict[str, Any]) -> dict[str, Any]:
    """A slot booked for a child, with the message it belongs to."""
    message = raw.get("message") if isinstance(raw.get("message"), dict) else {}
    registrations = [r for r in raw.get("registrations") or [] if isinstance(r, dict)]
    return {
        "id": _str(raw.get("id")),
        "start": _iso(raw.get("start")),
        "end": _iso(raw.get("stop") or raw.get("end")),
        "location": _str(raw.get("location")),
        "child_id": _str(registrations[0].get("pupil_id")) if registrations else "",
        "message_id": _str(message.get("id")),
        "title": _str(message.get("title")),
    }


def _document(raw: dict[str, Any], kind: str) -> dict[str, Any]:
    """A notebook (livret) or an attestation of a pupil; the file's hashes stay in the coordinator."""
    when = _str(raw.get("date") or raw.get("created"))
    year = _str(raw.get("year")) or when[:4]
    title = _str(raw.get("title")) if kind == "notebook" else _str(raw.get("type"))
    signed = bool(raw.get("signatures"))
    # The portal only asks for the livrets from 2019 on to be signed.
    old = kind == "notebook" and year[:4].isdigit() and int(year[:4]) < 2019
    return {
        "id": f"{kind}:{_str(raw.get('id'))}",
        "kind": kind,
        "title": title or ("Livret" if kind == "notebook" else "Attestation"),
        "type": _str(raw.get("type")) if kind == "notebook" else "",
        "year": year,
        "date": _iso(raw.get("date") or raw.get("created")),
        "child_id": _str(raw.get("pupil_id")),
        "signed": signed,
        "to_sign": not signed and not old,
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
        # Where each livret document's PDF is (ids and hashes the attributes do not carry).
        self._document_files: dict[str, tuple[str, ...]] = {}

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
            account={
                "parent_id": parent_id,
                "name": _str(info.get("name") or info.get("firstname")),
                # Who "me" is in a conversation: the comments carry the writer's user id.
                "user_ids": sorted({_str(info.get(k)) for k in ("id", "user_id") if info.get(k) is not None}),
            },
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
        await self._read_documents(parent_id, data, previous)
        data.activities = await self._optional(
            "activities", lambda: self.api.activities(parent_id, ACTIVITIES_KEPT), _activity, data, previous
        )
        data.notifications = await self._optional(
            "notifications",
            lambda: self._unread(parent_id),
            _notification,
            data,
            previous,
        )
        stop = (today + timedelta(days=APPOINTMENT_DAYS)).isoformat()
        data.appointments = await self._optional(
            "appointments", lambda: self.api.next_appointments(start, stop), _appointment, data, previous
        )
        data.appointments.sort(key=lambda a: a["start"] or "")
        # The first names of the children a message concerns, for the card, the panel and the events.
        names = {p["id"]: p["firstname"] or p["name"] for p in data.pupils}
        for message in (*data.carnet, *data.news):
            message["child"] = " · ".join(names[c] for c in message["children"] if c in names)
            # A slot booked for a child of another family is not one to show.
            message["slots"] = [s for s in message["slots"] if not s["booked"] or s["child_id"] in names]
        for document in data.documents:
            document["child"] = names.get(document["child_id"], "")
        for activity in data.activities:
            activity["child"] = " · ".join(names[c] for c in activity["children"] if c in names)
        for appointment in data.appointments:
            appointment["child"] = names.get(appointment["child_id"], "")
        self._fire_new(data)
        return data

    async def _unread(self, parent_id: str) -> list[dict[str, Any]]:
        return [n for n in await self.api.notifications(parent_id) if isinstance(n, dict) and _for_family(n)][
            :NOTIFICATIONS_KEPT
        ]

    async def _optional(
        self, kind: str, read: Any, parse: Any, data: EducartableData, previous: EducartableData
    ) -> list[dict[str, Any]]:
        """A part not every school has: its error shows nothing, a portal outage keeps what was read before."""
        try:
            raws = await read()
        except EducartableUnavailableError:
            data.stale.append(kind)
            return list(getattr(previous, kind))
        except EducartableError as err:
            _LOGGER.debug("No %s on this account: %s", kind, err)
            return []
        return [parse(r) for r in raws if isinstance(r, dict) and r.get("id") is not None]

    async def _read_documents(self, parent_id: str, data: EducartableData, previous: EducartableData) -> None:
        """The livret: notebooks, then attestations. A school without it answers with an error: nothing to show."""
        documents: list[dict[str, Any]] = []
        files: dict[str, tuple[str, ...]] = {}
        try:
            for kind, read in (("notebook", self.api.notebooks), ("attestation", self.api.attestations)):
                try:
                    raws = await read(parent_id)
                except EducartableUnavailableError:
                    raise
                except EducartableError as err:
                    _LOGGER.debug("No %s list on this account: %s", kind, err)
                    continue
                for raw in raws:
                    if not isinstance(raw, dict) or raw.get("id") is None:
                        continue
                    document = _document(raw, kind)
                    file = raw.get("file") if isinstance(raw.get("file"), dict) else {}
                    if kind == "notebook" and file.get("id") is not None and file.get("direct_hash"):
                        files[document["id"]] = ("notebook", _str(file["id"]), _str(file["direct_hash"]))
                    elif kind == "attestation" and raw.get("hash"):
                        files[document["id"]] = ("attestation", _str(raw["id"]), _str(raw["hash"]))
                    document["file"] = document["id"] in files
                    documents.append(document)
        except EducartableUnavailableError:
            data.documents, _ = previous.documents, data.stale.append("documents")
            return
        # Still to sign first, then the newest.
        documents.sort(key=lambda d: d["date"] or d["year"] or "", reverse=True)
        documents.sort(key=lambda d: not d["to_sign"])
        data.documents = documents
        self._document_files = files

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
            "activity": (
                "activities",
                data.activities,
                lambda _: True,
                EVENT_NEW_ACTIVITY,
                ("title", "author", "child"),
            ),
            "document": (
                "documents",
                data.documents,
                lambda d: d["to_sign"],
                EVENT_NEW_DOCUMENT,
                ("child_id", "child", "title", "kind", "year"),
            ),
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
        parts = (data.get("title"), data.get("subject") or data.get("author") or data.get("year"), data.get("due"))
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
        for message in (
            *(data.carnet if data else []),
            *(data.news if data else []),
            *(data.activities if data else []),
        ):
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

    def _patch_messages(self, message_id: str, change: dict[str, Any]) -> None:
        """Show an action at once (the next update confirms it); new dicts, the old ones are shared with states."""
        self.data = replace(
            self.data,
            carnet=[{**m, **change} if m["id"] == message_id else m for m in self.data.carnet],
            news=[{**m, **change} if m["id"] == message_id else m for m in self.data.news],
            activities=[{**m, **change} if m["id"] == message_id else m for m in self.data.activities],
        )
        self.async_update_listeners()

    def _children_of(self, message: dict[str, Any]) -> list[str]:
        known = [p["id"] for p in self.data.pupils]
        return [c for c in message.get("children") or [] if c in known] or known

    async def async_comments(self, message_id: str) -> list[dict[str, Any]]:
        """The private conversation of a message, as the card and the panel show it."""
        message = self._find_message(message_id)
        mine = set(self.data.account.get("user_ids") or [])
        out = []
        for raw in await self.api.comments(self._parent_id(), message["id"]):
            if not isinstance(raw, dict) or raw.get("id") is None:
                continue
            deleted = bool(raw.get("deleted"))
            text = "" if deleted else plain_text(raw.get("body"))
            out.append(
                {
                    "id": _str(raw["id"]),
                    "author": _author(raw),
                    "mine": _str(raw.get("user_id")) in mine,
                    "text": "" if text == "Pièce(s) jointe(s) :" else text,
                    "date": _iso(raw.get("created") or raw.get("modified")),
                    "deleted": deleted,
                    "medias": _medias(raw),
                }
            )
        return out

    async def async_reply(self, message_id: str, text: str) -> None:
        """Write to the teacher in a message's conversation; a reply it asks for is then recorded as given."""
        message = self._find_message(message_id)
        text = text.strip()
        if not text:
            raise EducartableError("the reply is empty")
        if not message.get("commentable") and message.get("achievement") != "comment":
            raise EducartableError("this message takes no reply")
        parent_id = self._parent_id()
        first = next(iter(await self.api.comments(parent_id, message_id)), None)
        await self.api.comment(parent_id, message_id, text, _str(first.get("id")) if isinstance(first, dict) else None)
        change: dict[str, Any] = {"comments": message.get("comments", 0) + 1}
        if message.get("achievement") == "comment" and not message.get("achieved"):
            model, keys = (
                ("Parent", [parent_id]) if message.get("parent_scope") else ("Pupil", self._children_of(message))
            )
            await self.api.achieve(parent_id, message_id, "comment", model, keys)
            change |= {"achieved": True, "to_do": False}
        self._patch_messages(message_id, change)

    async def async_write(self, children: list[str], title: str, body: str) -> None:
        """A new message to the teacher: one per classroom of the chosen children, as the portal's app sends it."""
        title, body = title.strip(), body.strip()
        if not title or not body:
            raise EducartableError("a message needs a title and a text")
        pupils = {p["id"]: p for p in self.data.pupils}
        chosen = [c for c in dict.fromkeys(children) if c in pupils]
        if not chosen or len(chosen) != len(set(children)):
            raise EducartableError("unknown child")
        if paused := [pupils[c]["firstname"] or c for c in chosen if not pupils[c]["writable"]]:
            raise EducartableError(f"the teacher paused messages for {', '.join(paused)}")
        by_classroom: dict[str, list[str]] = {}
        for child in chosen:
            by_classroom.setdefault(pupils[child]["classroom_id"], []).append(child)
        parent_id = self._parent_id()
        for group in by_classroom.values():
            await self.api.write_message(parent_id, group, title, body)
        await self.async_request_refresh()

    async def async_answer_survey(
        self, message_id: str, answers: dict[str, list[str]], children: list[str] | None = None
    ) -> None:
        """Answer a survey for children of the message (all of them by default); an answer given before is replaced."""
        message = self._find_message(message_id)
        survey = message.get("survey")
        if not survey:
            raise EducartableError("this message has no survey")
        # Open until the end of its deadline day, as the portal says ("ends on … at midnight").
        deadline = _due(survey.get("deadline"))
        if deadline and deadline < dt_util.now().date():
            raise EducartableError("the survey is closed")
        clean: dict[str, list[str]] = {}
        for question in survey["questions"]:
            picked = [str(o) for o in answers.get(question["id"], [])]
            allowed = {o["id"] for o in question["options"]}
            if not picked or any(o not in allowed for o in picked):
                raise EducartableError(f"no valid answer to “{question['label']}”")
            if len(picked) > 1 and not question["multiple"]:
                raise EducartableError(f"one answer only to “{question['label']}”")
            clean[question["id"]] = list(dict.fromkeys(picked))
        targets = self._children_of(message)
        if children:
            if any(c not in targets for c in children):
                raise EducartableError("this child is not concerned by the survey")
            targets = list(dict.fromkeys(children))
        for child in targets:
            if child in survey["answers"]:
                await self.api.delete_survey_answer(message_id, child)
            await self.api.answer_survey(message_id, child, clean)
        answered = {**survey["answers"], **dict.fromkeys(targets, clean)}
        change: dict[str, Any] = {"survey": {**survey, "answers": answered}}
        if message.get("achievement") == "survey":
            change |= {"achieved": True, "to_do": False}
        self._patch_messages(message_id, change)

    def _find_slot(self, slot_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        for message in (*(self.data.carnet if self.data else []), *(self.data.news if self.data else [])):
            for slot in message.get("slots") or []:
                if slot["id"] == slot_id:
                    return message, slot
        raise EducartableError("unknown appointment slot")

    async def async_book(self, slot_id: str, child_id: str = "") -> None:
        """Book a free appointment slot for a child of the message (the only one when there is one)."""
        message, slot = self._find_slot(slot_id)
        if slot["booked"]:
            raise EducartableError("this slot is already booked")
        concerned = self._children_of(message)
        booked = {s["child_id"] for s in message["slots"] if s["booked"]}
        free = [c for c in concerned if c not in booked]
        if child_id:
            if child_id not in concerned:
                raise EducartableError("this child is not concerned by the appointment")
            if child_id in booked:
                raise EducartableError("an appointment is already booked for this child")
        elif len(free) == 1:
            child_id = free[0]
        else:
            raise EducartableError("name the child the appointment is for")
        await self.api.book(slot_id, child_id)
        slots = [{**s, "booked": True, "child_id": child_id} if s["id"] == slot_id else s for s in message["slots"]]
        change: dict[str, Any] = {"slots": slots}
        if message.get("achievement") == "book" and set(concerned) <= booked | {child_id}:
            change |= {"achieved": True, "to_do": False}
        self._patch_messages(message["id"], change)

    async def async_cancel_booking(self, slot_id: str) -> None:
        """Cancel an appointment booked for one of the children."""
        message, slot = self._find_slot(slot_id)
        if not slot["booked"]:
            raise EducartableError("this slot is not booked")
        await self.api.cancel_booking(slot_id)
        slots = [{**s, "booked": False, "child_id": ""} if s["id"] == slot_id else s for s in message["slots"]]
        self._patch_messages(message["id"], {"slots": slots})
        await self.async_request_refresh()

    async def async_sign_document(self, document_id: str, name: str) -> None:
        """Sign a notebook or an attestation of the livret as consulted, with the signer's name."""
        document = next((d for d in self.data.documents if d["id"] == document_id), None) if self.data else None
        if document is None:
            raise EducartableError("unknown document")
        if len(name.strip()) < 3:
            raise EducartableError("the signer's name is too short")
        await self.api.sign_document(self._parent_id(), document["kind"], document_id.split(":", 1)[1], name.strip())
        documents = [
            {**d, "signed": True, "to_sign": False} if d["id"] == document_id else d for d in self.data.documents
        ]
        self.data = replace(self.data, documents=documents)
        self.async_update_listeners()

    async def async_like(self, activity_id: str, liked: bool = True) -> None:
        """Like a post of the cahier de vie, or take the like back."""
        activity = next((a for a in self.data.activities if a["id"] == activity_id), None) if self.data else None
        if activity is None:
            raise EducartableError("unknown post")
        if liked == bool(activity["like_id"]):
            return
        parent_id = self._parent_id()
        if liked:
            like_id = await self.api.like(parent_id, activity_id)
            self._patch_messages(activity_id, {"like_id": like_id or "?", "likes": activity["likes"] + 1})
            if not like_id:
                await self.async_request_refresh()  # The portal did not say which like it is: read it back.
            return
        if activity["like_id"] == "?":
            raise EducartableError("the like is still being recorded, try again in a moment")
        await self.api.unlike(parent_id, activity["like_id"])
        self._patch_messages(activity_id, {"like_id": "", "likes": max(0, activity["likes"] - 1)})

    async def async_read_notifications(self, notification_id: str = "") -> None:
        """Mark one notification of the portal as read, or all of them."""
        parent_id = self._parent_id()
        if notification_id:
            if not any(n["id"] == notification_id for n in self.data.notifications):
                raise EducartableError("unknown notification")
            await self.api.read_notification(parent_id, notification_id)
            left = [n for n in self.data.notifications if n["id"] != notification_id]
        else:
            await self.api.read_all_notifications(parent_id)
            left = []
        self.data = replace(self.data, notifications=left)
        self.async_update_listeners()

    async def async_delete_comment(self, message_id: str, comment_id: str) -> None:
        """Delete one of the family's own comments in a message's conversation."""
        comments = await self.async_comments(message_id)
        comment = next((c for c in comments if c["id"] == comment_id), None)
        if comment is None or not comment["mine"]:
            raise EducartableError("only your own comments can be deleted")
        if not comment["deleted"]:
            await self.api.delete_comment(self._parent_id(), comment_id)

    async def async_document_file(self, document_id: str) -> tuple[bytes, str]:
        """A livret document's PDF, from the location read with the list (never one given by the browser)."""
        where = self._document_files.get(document_id)
        if where is None:
            raise EducartableError("no file for this document")
        kind, file_id, file_hash = where
        read = self.api.notebook_file if kind == "notebook" else self.api.attestation_file
        return await self._cached(f"doc:{document_id}", lambda: read(file_id, file_hash))

    async def async_media(self, media_id: str) -> tuple[bytes, str]:
        """An attachment, kept a few minutes within a size budget: a redraw or a second look is instant."""
        return await self._cached(media_id, lambda: self.api.media(media_id))

    async def _cached(self, key: str, fetch: Any) -> tuple[bytes, str]:
        now = time.monotonic()
        hit = self._file_cache.get(key)
        if hit and now - hit[0] < FILE_CACHE_TTL:
            self._file_cache.move_to_end(key)
            return hit[1], hit[2]
        body, content_type = await fetch()
        self._file_cache[key] = (now, body, content_type)
        total = sum(len(v[1]) for v in self._file_cache.values())
        while total > FILE_CACHE_BYTES and len(self._file_cache) > 1:
            _, old = self._file_cache.popitem(last=False)
            total -= len(old[1])
        return body, content_type


def _achieved(message: dict[str, Any]) -> dict[str, Any]:
    return {**message, "achieved": True, "to_sign": False, "to_do": False}
