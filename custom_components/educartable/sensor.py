"""Sensors for Educartable: the family account and one device per pupil."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MESSAGES_KEPT, NEWS_KEPT
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
    ]
    known: set[str] = set()

    @callback
    def add_pupils() -> None:
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
        return {"homework": self._items[:MESSAGES_KEPT]}
