"""Coordinator for Remember The Milk integration."""

from datetime import datetime, timedelta
import logging
from typing import Any, Final

from rtmapi import Rtm

from homeassistant.components.todo import TodoItemStatus
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .notifications import RememberTheMilkNotifications
from .util import get_time_range, run_async

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
        self.notifications = RememberTheMilkNotifications(hass)
        self.api = Rtm(api_key, shared_secret, "delete", token=token)

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch tasks from the Remember The Milk API."""
        try:
            data = (await run_async(self.api.rtm.tasks.getList)).tasks
            await self.notifications.update_notifications(data)
            return data

        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_get_task_lists(self) -> list[Any]:
        """Return Remember The Milk task lists fetched at most once."""
        try:
            return (await run_async(self.api.rtm.lists.getList)).lists
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_get_tasks(self, list_id: str) -> list[Any]:
        """Return tasks from the Remember The Milk API."""
        try:
            task_lists = (
                await run_async(self.api.rtm.tasks.getList(list_id=list_id))
            ).tasks
            # Get the first list of tasks
            task_list = task_lists.list
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            return task_list

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

    async def async_run_rtm_method(self, request, payload) -> Any:
        """Run a request to the Remember The Milk API."""
        try:
            result = await run_async(self.api.rtm.timelines.create)
            timeline = result.timeline.value
            # The request parameter may be in format "rtm.tasks.getList".
            lib, module, method = request.split(".")
            request = getattr(getattr(getattr(self.api, lib), module), method)
            # Combine the timeline parameter with the other parameters.
            return await run_async(lambda: request(timeline=timeline, **payload))
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def get_statistics(
        self, details_range: str = "day", trend_range: str = "week"
    ) -> dict[str, int]:
        """Return statistics of tasks for the details and trend range."""
        if self.data is None:
            return {}
        today_tasks = 0
        completed_tasks = 0
        details = {}
        trend = {}

        today = datetime.now()

        if details_range == "day":
            details_start, details_end = get_time_range(today, "day")
        elif details_range == "week":
            details_start, details_end = get_time_range(today, "week")
        else:
            details_start, details_end = None, None

        if trend_range == "week":
            trend_start, trend_end = get_time_range(today, "week")
            trend_index_range = 7
        elif trend_range == "month":
            trend_start, trend_end = get_time_range(today, "month")
            trend_index_range = trend_end.day
        else:
            trend_start, trend_end = None, None
            trend_index_range = 0

        for task_list in self.data:
            for taskseries in task_list:
                has_due_time = taskseries.task.has_due_time
                is_completed = taskseries.task.completed

                # Count the number of all completed tasks.
                if is_completed:
                    completed_tasks += 1

                if has_due_time and has_due_time == "1":
                    due_time = datetime.strptime(
                        taskseries.task.due, "%Y-%m-%dT%H:%M:%SZ"
                    )
                else:
                    due_time = datetime.strptime(
                        taskseries.task.added, "%Y-%m-%dT%H:%M:%SZ"
                    )

                # Count the number of today's tasks.
                if due_time.date() == datetime.now().date():
                    today_tasks += 1

                # Count the number of tasks and completed tasks for the details range.
                if (
                    details_start
                    and details_end
                    and details_start <= due_time <= details_end
                ):
                    details["total"] = details.get("total", 0) + 1
                    if is_completed:
                        details["completed"] = details.get("completed", 0) + 1

                # Count the number of tasks and completed tasks for the trend range.
                if trend_start and trend_end and trend_start <= due_time <= trend_end:
                    date = due_time.date()
                    if date not in trend:
                        trend[date] = {"total": 0, "completed": 0}
                    trend[date]["total"] += 1
                    if is_completed:
                        trend[date]["completed"] += 1

        # Make the trend have index from 0 to 6 or 0 to 29, based on the time range.
        for i in range(trend_index_range):
            date = (trend_start + timedelta(days=i)).date()
            if date not in trend:
                trend[i] = {"total": 0, "completed": 0}
            else:
                trend[i] = trend.pop(date)

        return {
            "summary": {"today_tasks": today_tasks, "completed_tasks": completed_tasks},
            "details": details,
            "trend": trend,
        }

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
            # Find the old task to see what updates should be made.
            old_task = next(
                (
                    taskseries
                    for task_list in self.data
                    if task_list.id == list_id
                    for taskseries in task_list
                    if taskseries.id == taskseries_id
                ),
                None,
            )
            if not old_task:
                raise ValueError(f"Old task with ID {taskseries_id} not found")

            # Updates that should be made to the new task.
            change_name = old_task.name != name
            change_due_date = old_task.task.due != due
            old_complete_status = (
                TodoItemStatus.COMPLETED
                if old_task.task.completed
                else TodoItemStatus.NEEDS_ACTION,
            )
            change_complete_status = old_complete_status != status

            timeline = result.timeline.value
            complete_action = (
                self.api.rtm.tasks.complete
                if status == TodoItemStatus.COMPLETED
                else self.api.rtm.tasks.uncomplete
            )
            # Update name of task.
            if change_name:
                await run_async(
                    lambda: self.api.rtm.tasks.setName(
                        timeline=timeline,
                        list_id=list_id,
                        taskseries_id=taskseries_id,
                        task_id=task_id,
                        name=name,
                    )
                )
            # Update due date of task.
            if change_due_date:
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
            # Update completed status of task.
            if change_complete_status:
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
