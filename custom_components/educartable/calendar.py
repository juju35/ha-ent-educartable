"""Homework calendar of an Educartable account: each child's homework on its due date."""

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
    async_add_entities([HomeworkCalendar(entry.runtime_data)])


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


class HomeworkCalendar(EducartableEntity, CalendarEntity):
    """The homework of every child, as all-day events on their due date."""

    def __init__(self, coordinator: EducartableCoordinator) -> None:
        super().__init__(coordinator, "homework_calendar")

    def _events(self) -> list[CalendarEvent]:
        data = self.coordinator.data
        if not data:
            return []
        names = {p["id"]: p["firstname"] or p["name"] for p in data.pupils}
        events = [
            e
            for pupil_id, items in data.homework.items()
            for item in items
            if (e := homework_event(item, names.get(pupil_id, "")))
        ]
        return sorted(events, key=lambda e: e.start_datetime_local)

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        return next((e for e in self._events() if e.end_datetime_local > now), None)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [e for e in self._events() if e.start_datetime_local < end_date and e.end_datetime_local > start_date]
