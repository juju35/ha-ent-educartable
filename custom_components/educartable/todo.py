"""One to-do list per child: their homework within the window. Ticking one marks it done in the portal."""

from __future__ import annotations

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity, TodoListEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import EducartableError
from .const import DOMAIN
from .coordinator import EducartableConfigEntry, EducartableCoordinator
from .entity import EducartablePupilEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: EducartableConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_pupils() -> None:
        new = [HomeworkTodo(coordinator, p) for p in coordinator.data.pupils if p["id"] not in known]
        known.update(p["id"] for p in coordinator.data.pupils)
        if new:
            async_add_entities(new)

    add_pupils()
    entry.async_on_unload(coordinator.async_add_listener(add_pupils))


class HomeworkTodo(EducartablePupilEntity, TodoListEntity):
    """A child's homework. Only the done box can change, as in the portal, and only for homework it can tick."""

    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM

    def __init__(self, coordinator: EducartableCoordinator, pupil: dict) -> None:
        super().__init__(coordinator, pupil, "homework_list")

    @property
    def todo_items(self) -> list[TodoItem]:
        items = self.coordinator.data.homework.get(self._pupil_id, []) if self.coordinator.data else []
        return [
            TodoItem(
                uid=item["id"],
                summary=" · ".join(p for p in (item["subject"], item["title"]) if p) or "—",
                status=TodoItemStatus.COMPLETED if item["done"] else TodoItemStatus.NEEDS_ACTION,
                due=dt_util.parse_date((item["due"] or "")[:10]),
                description=item["text"] or None,
            )
            for item in items
        ]

    async def async_update_todo_item(self, item: TodoItem) -> None:
        if item.uid is None:
            return
        try:
            await self.coordinator.async_set_homework_done(
                self._pupil_id, item.uid, item.status == TodoItemStatus.COMPLETED
            )
        except EducartableError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="action_failed", translation_placeholders={"error": str(err)}
            ) from err
