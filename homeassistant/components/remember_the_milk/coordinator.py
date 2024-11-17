"""DataUpdateCoordinator for the Todoist component."""

from datetime import timedelta
import logging
from typing import Any, Final

from rtmapi import Rtm

from homeassistant.components.todo import TodoItemStatus
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .util import run_async

UPDATE_INTERVAL: Final = timedelta(minutes=1)


class RememberTheMilkCoordinator(DataUpdateCoordinator[list[Any]]):
    """Coordinator for updating task data from Remember The Milk."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        api_key: str,
        shared_secret: str,
        token: str,
    ) -> None:
        """Initialize the Remember The Milk coordinator."""
        super().__init__(
            hass,
            logger,
            name="Remember The Milk",
            update_interval=UPDATE_INTERVAL,
        )
        self.api = Rtm(api_key, shared_secret, "delete", token=token)

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch tasks from the Remember The Milk API."""
        try:
            return (await run_async(self.api.rtm.tasks.getList)).tasks
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_get_task_lists(self) -> list[Any]:
        """Return Remember The Milk task lists fetched at most once."""
        return (await run_async(self.api.rtm.lists.getList)).lists

    async def async_get_tasks(self, list_id: str) -> list[dict[str, Any]]:
        """Return tasks from the Remember The Milk API."""
        try:
            task_lists = (
                await run_async(self.api.rtm.tasks.getList(list_id=list_id))
            ).tasks
            # Get the first list of tasks
            return list(task_lists.list)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_create_task(
        self, list_id: str, task_name: str, due: str, description: str
    ) -> None:
        """TODO: Create a new task on Remember The Milk."""
        try:
            result = await run_async(self.api.rtm.timelines.create)
            timeline = result.timeline.value
            await run_async(
                lambda: self.api.rtm.tasks.add(
                    timeline=timeline, name=task_name, parse="1", list_id=list_id
                )
            )
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_delete_task(
        self, list_id: str, taskseries_id: str, task_id: str
    ) -> None:
        """Delete a task on Remember The Milk using taskseries_id and task_id."""
        try:
            result = await run_async(self.api.rtm.timelines.create)
            timeline = result.timeline.value
            await run_async(
                lambda: self.api.rtm.tasks.delete(
                    timeline=timeline,
                    list_id=list_id,
                    taskseries_id=taskseries_id,
                    task_id=task_id,
                )
            )
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_update_task(
        self,
        list_id: str,
        name: str,
        taskseries_id: str,
        task_id: str,
        due: str,
        has_due_time: str,
        status: str,
    ) -> None:
        """Update name, due date, and/or task completed status of a task on Remember The Milk."""
        try:
            result = await run_async(self.api.rtm.timelines.create)
            timeline = result.timeline.value
            complete_action = (
                self.api.rtm.tasks.complete
                if status == TodoItemStatus.COMPLETED
                else self.api.rtm.tasks.uncomplete
            )
            # Update due date of task.
            await run_async(
                lambda: self.api.rtm.tasks.setDueDate(
                    timeline=timeline,
                    list_id=list_id,
                    taskseries_id=taskseries_id,
                    task_id=task_id,
                    due=due,
                    has_due_time=has_due_time,
                )
            )
            # Update name of task.
            await run_async(
                lambda: self.api.rtm.tasks.setName(
                    timeline=timeline,
                    list_id=list_id,
                    taskseries_id=taskseries_id,
                    task_id=task_id,
                    name=name,
                )
            )
            # Update completed status of task.
            await run_async(
                lambda: complete_action(
                    timeline=timeline,
                    list_id=list_id,
                    taskseries_id=taskseries_id,
                    task_id=task_id,
                )
            )

        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
