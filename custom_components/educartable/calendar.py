"""Calendars of an Educartable account: each child's homework on its due date, and the school's events and the
appointments booked for the children."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import EducartableConfigEntry, EducartableCoordinator
from .entity import EducartableEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: EducartableConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([HomeworkCalendar(entry.runtime_data), SchoolEventsCalendar(entry.runtime_data)])


def homework_event(item: dict[str, Any], child: str) -> CalendarEvent | None:
    due = dt_util.parse_date((item.get("due") or "")[:10])
    if due is None:
        return None
    title = item.get("title") or item.get("subject") or "Homework"
    summary = " · ".join(p for p in (child, item.get("subject") if item.get("title") else "", title) if p)
    return CalendarEvent(
        start=due,
        end=due + timedelta(days=1),
        summary=summary,
        description=item.get("text") or None,
        uid=f"homework-{item.get('id')}-{child}",
    )


class EducartableCalendar(EducartableEntity, CalendarEntity):
    """A calendar drawn from the account's data: its events, the current one and those of a time range."""

    def _events(self) -> list[CalendarEvent]:
        data = self.coordinator.data
        if not data:
            return []
        names = {p["id"]: p["firstname"] or p["name"] for p in data.pupils}
        return sorted(self._build(data, names), key=lambda e: e.start_datetime_local)

    def _build(self, data: Any, names: dict[str, str]) -> list[CalendarEvent]:
        raise NotImplementedError

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        return next((e for e in self._events() if e.end_datetime_local > now), None)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [e for e in self._events() if e.start_datetime_local < end_date and e.end_datetime_local > start_date]


class HomeworkCalendar(EducartableCalendar):
    """The homework of every child, as all-day events on their due date."""

    def __init__(self, coordinator: EducartableCoordinator) -> None:
        super().__init__(coordinator, "homework_calendar")

    def _build(self, data: Any, names: dict[str, str]) -> list[CalendarEvent]:
        return [
            e
            for pupil_id, items in data.homework.items()
            for item in items
            if (e := homework_event(item, names.get(pupil_id, "")))
        ]


def school_event(message: dict[str, Any]) -> CalendarEvent | None:
    """An event of the news (an outing, a show…) on its day: all day, the portal gives no length."""
    if message.get("type") != "event":
        return None
    day = dt_util.parse_date((message.get("date") or "")[:10])
    if day is None:
        return None
    return CalendarEvent(
        start=day,
        end=day + timedelta(days=1),
        summary=message.get("title") or "Event",
        description=message.get("text") or None,
        uid=f"event-{message.get('id')}",
    )


def appointment_event(slot: dict[str, Any], title: str, child: str) -> CalendarEvent | None:
    start = dt_util.parse_datetime(slot.get("start") or "")
    if start is None:
        return None
    end = dt_util.parse_datetime(slot.get("end") or "") or start + timedelta(minutes=15)
    return CalendarEvent(
        start=dt_util.as_local(start),
        end=dt_util.as_local(end),
        summary=" · ".join(p for p in (child, title or "Appointment") if p),
        location=slot.get("location") or None,
        uid=f"appointment-{slot.get('id')}",
    )


class SchoolEventsCalendar(EducartableCalendar):
    """The school's events (from the news) and the appointments booked for the children."""

    def __init__(self, coordinator: EducartableCoordinator) -> None:
        super().__init__(coordinator, "events_calendar")

    def _build(self, data: Any, names: dict[str, str]) -> list[CalendarEvent]:
        events = [e for m in data.news if (e := school_event(m))]
        seen = set()
        for a in data.appointments:
            if e := appointment_event(a, a.get("title", ""), names.get(a.get("child_id", ""), "")):
                events.append(e)
                seen.add(a["id"])
        # A slot booked in a message read now but not yet in the appointments list.
        events.extend(
            e
            for m in (*data.carnet, *data.news)
            for slot in m.get("slots") or []
            if slot["booked"]
            and slot["id"] not in seen
            and (e := appointment_event(slot, m.get("title", ""), names.get(slot["child_id"], "")))
        )
        return events
