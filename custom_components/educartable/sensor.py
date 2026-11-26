"""Sensors for Educartable: the family account (liaison book, news, last update) and one homework sensor per pupil."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .config_flow import hide_header, panel_tabs
from .const import ACTIVITIES_KEPT, DOCUMENTS_KEPT, MESSAGES_KEPT, NEWS_KEPT, NOTIFICATIONS_KEPT
from .coordinator import EducartableConfigEntry, EducartableCoordinator
from .entity import EducartableEntity, EducartablePupilEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EducartableConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        CarnetToSignSensor(coordinator),
        NewsSensor(coordinator),
        DocumentsToSignSensor(coordinator),
        ActivitiesSensor(coordinator),
        NotificationsSensor(coordinator),
        NextAppointmentSensor(coordinator),
        LastUpdateSensor(coordinator),
    ]
    known: set[str] = set()

    @callback
    def add_pupils() -> None:
        # A child no longer followed loses its device (and so this entity); followed again, it is added back.
        known.intersection_update(p["id"] for p in coordinator.data.pupils)
        new: list[SensorEntity] = []
        for pupil in coordinator.data.pupils:
            if pupil["id"] not in known:
                known.add(pupil["id"])
                new.append(HomeworkSensor(coordinator, pupil))
        if new:
            async_add_entities(new)

    # The account device first, so the pupils' via_device points to an existing device.
    async_add_entities(entities)
    add_pupils()
    entry.async_on_unload(coordinator.async_add_listener(add_pupils))


class CarnetToSignSensor(EducartableEntity, SensorEntity):
    """Number of liaison-book messages still to sign, across all children."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: EducartableCoordinator) -> None:
        super().__init__(coordinator, "carnet_to_sign")

    @property
    def native_value(self) -> int:
        return sum(1 for m in self.coordinator.data.carnet if m["to_sign"])

    @property
    def extra_state_attributes(self) -> dict:
        return {**self.base_attributes, "messages": self.coordinator.data.carnet[:MESSAGES_KEPT]}


class NewsSensor(EducartableEntity, SensorEntity):
    """Number of recent news / events."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: EducartableCoordinator) -> None:
        super().__init__(coordinator, "news")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.news)

    @property
    def extra_state_attributes(self) -> dict:
        return {**self.base_attributes, "news": self.coordinator.data.news[:NEWS_KEPT]}


class ActivitiesSensor(EducartableEntity, SensorEntity):
    """Number of recent posts of the cahier de vie (the class's life: photos, likes, comments)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: EducartableCoordinator) -> None:
        super().__init__(coordinator, "activities")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.activities)

    @property
    def extra_state_attributes(self) -> dict:
        return {**self.base_attributes, "activities": self.coordinator.data.activities[:ACTIVITIES_KEPT]}


class NotificationsSensor(EducartableEntity, SensorEntity):
    """Number of unread notifications of the portal (new messages, replies, cancelled appointments…)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: EducartableCoordinator) -> None:
        super().__init__(coordinator, "notifications")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.notifications)

    @property
    def extra_state_attributes(self) -> dict:
        return {**self.base_attributes, "notifications": self.coordinator.data.notifications[:NOTIFICATIONS_KEPT]}


class NextAppointmentSensor(EducartableEntity, SensorEntity):
    """When the next appointment booked for a child is; every appointment booked ahead as attributes."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: EducartableCoordinator) -> None:
        super().__init__(coordinator, "next_appointment")

    def _upcoming(self) -> list[dict]:
        now = dt_util.now()
        return [
            a
            for a in self.coordinator.data.appointments
            if (end := dt_util.parse_datetime(a["end"] or a["start"] or "")) is None or end > now
        ]

    @property
    def native_value(self) -> datetime | None:
        nxt = next((a for a in self._upcoming() if a["start"]), None)
        return dt_util.parse_datetime(nxt["start"]) if nxt else None

    @property
    def extra_state_attributes(self) -> dict:
        return {**self.base_attributes, "appointments": self._upcoming()}


class DocumentsToSignSensor(EducartableEntity, SensorEntity):
    """Number of livret documents (notebooks, attestations) still to sign as consulted, across all children."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: EducartableCoordinator) -> None:
        super().__init__(coordinator, "documents_to_sign")

    @property
    def native_value(self) -> int:
        return sum(1 for d in self.coordinator.data.documents if d["to_sign"])

    @property
    def extra_state_attributes(self) -> dict:
        return {**self.base_attributes, "documents": self.coordinator.data.documents[:DOCUMENTS_KEPT]}


class HomeworkSensor(EducartablePupilEntity, SensorEntity):
    """Number of homework items still to do for a pupil."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: EducartableCoordinator, pupil: dict) -> None:
        super().__init__(coordinator, pupil, "homework")

    @property
    def _items(self) -> list[dict]:
        return self.coordinator.data.homework.get(self._pupil_id, [])

    @property
    def native_value(self) -> int:
        return sum(1 for h in self._items if not h["done"])

    @property
    def extra_state_attributes(self) -> dict:
        pupil = next((p for p in self.coordinator.data.pupils if p["id"] == self._pupil_id), {})
        # The card and the panel group the homework of every child: each sensor says whose it is.
        return {
            "config_entry_id": self.coordinator.config_entry.entry_id,
            "child_id": self._pupil_id,
            "child": pupil.get("firstname") or pupil.get("name", ""),
            "homework": self._items[:MESSAGES_KEPT],
        }


class LastUpdateSensor(EducartableEntity, SensorEntity):
    """When the portal was last read, with the children and the options the card and the panel follow."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _unrecorded_attributes = frozenset({"account", "children", "panel_tabs", "hide_header"})

    def __init__(self, coordinator: EducartableCoordinator) -> None:
        super().__init__(coordinator, "last_update")

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.data.updated

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        options = self.coordinator.config_entry.options
        return {
            **self.base_attributes,
            "account": {"name": data.account.get("name", "")},
            "children": data.pupils,
            "panel_tabs": panel_tabs(options),
            "hide_header": hide_header(options),
        }
