"""A todo platform for Todoist."""

from datetime import UTC, datetime
import logging

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import DiscoveryInfoType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import RememberTheMilkCoordinator

DOMAIN = "remember_the_milk"
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Remember the Milk Todo platform."""
    if discovery_info is None:
        return

    account_name = discovery_info.get("account_name")
    if account_name is None:
        _LOGGER.error("No account name found in discovery_info")
        return

    coordinator: RememberTheMilkCoordinator = hass.data[DOMAIN].get(account_name)
    if coordinator is None:
        _LOGGER.error("No coordinator found for account %s", account_name)
        return

    task_lists = await coordinator.async_get_task_lists()

    todo_entities = [
        RememberTheMilkTodoListEntity(
            coordinator, account_name, task_list.id, task_list.name
        )
        for task_list in task_lists
    ]

    async_add_entities(todo_entities, True)


class RememberTheMilkTodoListEntity(
    CoordinatorEntity[RememberTheMilkCoordinator], TodoListEntity
):
    """A Remember The Milk TodoListEntity."""

    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM
    )

    def __init__(
        self,
        coordinator: RememberTheMilkCoordinator,
        account_name: str,
        list_id: str,
        list_name: str,
    ) -> None:
        """Initialize RtmTodoListEntity."""
        super().__init__(coordinator)
        self.account_name = account_name
        self.list_id = list_id
        self._attr_name = list_name
        self._attr_unique_id = f"{account_name}-{list_id}"

    @property
    def todo_items(self) -> list[TodoItem]:
        """Return the current set of To-do items."""
        if self.coordinator.data is None:
            return None
        for task_list in self.coordinator.data:
            if task_list.id != self.list_id:
                continue
            todo_items = [
                [
                    taskseries.task.added,
                    TodoItem(
                        summary=taskseries.name,
                        uid=taskseries.id + "_" + taskseries.task.id,
                        status=TodoItemStatus.COMPLETED
                        if taskseries.task.completed
                        else TodoItemStatus.NEEDS_ACTION,
                        due=taskseries.task.due,
                        description=taskseries.notes.note.value
                        if len(list(taskseries.notes)) > 0
                        else "",
                    ),
                ]
                for taskseries in task_list
            ]
            # Sort by added time
            todo_items.sort(key=lambda x: x[0])
            return [item[1] for item in todo_items]
        return []

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a new To-do item."""
        await self.coordinator.async_create_task(
            self.list_id, item.summary, item.due, item.description
        )
        await self.coordinator.async_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete specified To-do items, each represented by a combined ID (uid) in the format 'taskseries_id_task_id'."""
        for uid in uids:
            try:
                taskseries_id, task_id = uid.split("_", 1)
                await self.coordinator.async_delete_task(
                    self.list_id, taskseries_id, task_id
                )
            except ValueError:
                continue

        await self.coordinator.async_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update specified To-do item, can update name, due date, and task completed."""
        taskseries_id, task_id = item.uid.split("_", 1)
        has_due_time = "1" if isinstance(item.due, datetime) else "0"
        due_iso = ""
        # Convert due time from date to UTC and ISO 8601 format.
        if item.due:
            due_date = datetime.fromisoformat(str(item.due))
            due_iso = due_date.astimezone(UTC).isoformat()

        await self.coordinator.async_update_task(
            self.list_id,
            item.summary,
            taskseries_id,
            task_id,
            due_iso,
            has_due_time,
            item.status,
        )
        await self.coordinator.async_refresh()
