"""Coordinator for Remember The Milk integration."""

from datetime import datetime, timedelta
import logging
from typing import Any, Final
from zoneinfo import ZoneInfo

from rtmapi import Rtm

from homeassistant.components.todo import TodoItemStatus
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .notifications import RememberTheMilkNotifications
from .util import RateLimiter, get_time_range, run_async

# Define the interval at which data should be updated (every 1 minute)
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
        """Initialize the Remember The Milk coordinator.

        Args:
            hass (HomeAssistant): The Home Assistant instance.
            logger (logging.Logger): Logger for logging messages.
            api_key (str): API key for Remember The Milk.
            shared_secret (str): Shared secret for Remember The Milk API.
            token (str): Access token for Remember The Milk API.

        """
        # Initialize the parent DataUpdateCoordinator with the Home Assistant instance, logger, name, and update interval
        super().__init__(
            hass,
            logger,
            name="Remember The Milk",
            update_interval=UPDATE_INTERVAL,
        )
        # Set the timezone based on Home Assistant's configuration
        self.timezone = ZoneInfo(hass.config.time_zone)
        # Initialize notifications handler for Remember The Milk
        self.notifications = RememberTheMilkNotifications(hass)
        # Initialize the Remember The Milk API client with the provided credentials
        self.api = Rtm(api_key, shared_secret, "delete", token=token)
        # Initialize a rate limiter to limit API requests (3 requests per second)
        self.rate_limiter = RateLimiter(rate=0.3)
        # Flag to indicate if the coordinator has been initialized
        self.initialized = False

    async def async_setup_rate_limiter(self):
        """Start the rate limiter."""
        await self.rate_limiter.start()

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch tasks from the Remember The Milk API.

        This method is called periodically based on the update interval.

        Returns:
            list[dict[str, Any]]: A list of task data dictionaries.

        Raises:
            UpdateFailed: If there is an error communicating with the API.

        """
        try:
            # Fetch the list of tasks asynchronously with rate limiting
            data = (
                await run_async(self.rate_limiter, self.api.rtm.tasks.getList)
            ).tasks
            # Update notifications based on the fetched data
            await self.notifications.update_notifications(data)
        except Exception as err:
            # Raise an UpdateFailed exception if an error occurs
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            # Return the fetched task data
            return data

    async def async_get_task_lists(self) -> list[Any]:
        """Return Remember The Milk task lists fetched at most once.

        This method fetches the task lists from the API, ensuring that
        the operation respects the rate limiter.

        Returns:
            list[Any]: A list of task lists.

        Raises:
            UpdateFailed: If there is an error communicating with the API.

        """
        try:
            # Fetch the list of task lists asynchronously with rate limiting
            return (
                await run_async(self.rate_limiter, self.api.rtm.lists.getList)
            ).lists
        except Exception as err:
            # Raise an UpdateFailed exception if an error occurs
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_get_tasks(self, list_id: str) -> list[Any]:
        """Return tasks from the Remember The Milk API.

        Args:
            list_id (str): The ID of the task list to fetch tasks from.

        Returns:
            list[Any]: A list of tasks within the specified list.

        Raises:
            UpdateFailed: If there is an error communicating with the API.
        """
        try:
            # Fetch the list of tasks for the specified list_id asynchronously with rate limiting
            task_lists = (
                await run_async(
                    self.rate_limiter,
                    lambda: self.api.rtm.tasks.getList(list_id=list_id),
                )
            ).tasks
            # Extract the first list of tasks from the fetched data
            task_list = task_lists.list
        except Exception as err:
            # Raise an UpdateFailed exception if an error occurs
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            # Return the list of tasks
            return task_list

    async def async_create_task(
        self, list_id: str, task_name: str, due: str, description: str
    ) -> None:
        """Create a new task on Remember The Milk.

        Args:
            list_id (str): The ID of the list to add the task to.
            task_name (str): The name of the task.
            due (str): The due date of the task in ISO format.
            description (str): The description of the task.

        Raises:
            UpdateFailed: If there is an error communicating with the API.

        """
        try:
            # Create a new timeline entry asynchronously with rate limiting
            result = await run_async(self.rate_limiter, self.api.rtm.timelines.create)
            timeline = result.timeline.value
            # Add the new task to the specified list with the given details
            await run_async(
                self.rate_limiter,
                lambda: self.api.rtm.tasks.add(
                    timeline=timeline, name=task_name, parse="1", list_id=list_id
                ),
            )
        except Exception as err:
            # Raise an UpdateFailed exception if an error occurs
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_run_rtm_method(self, request, payload) -> Any:
        """Run a request to the Remember The Milk API.

        This is a generic method to execute any RTM API method by specifying
        the request string and payload.

        Args:
            request (str): The API method to call, e.g., "rtm.tasks.getList".
            payload (dict): The parameters to pass to the API method.

        Returns:
            Any: The result of the API method call.

        Raises:
            UpdateFailed: If there is an error communicating with the API.

        """
        try:
            # Create a new timeline entry asynchronously with rate limiting
            result = await run_async(self.rate_limiter, self.api.rtm.timelines.create)
            timeline = result.timeline.value
            # Split the request string to access the appropriate API method
            lib, module, method = request.split(".")
            request_method = getattr(getattr(getattr(self.api, lib), module), method)
            # Execute the API method with the timeline and provided payload
            return await run_async(
                self.rate_limiter, lambda: request_method(timeline=timeline, **payload)
            )
        except Exception as err:
            # Raise an UpdateFailed exception if an error occurs
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def get_statistics(
        self, details_range: str = "day", trend_range: str = "week"
    ) -> dict[str, int]:
        """Return statistics of tasks for the details and trend range.

        This method calculates summaries, details, and trends of tasks based
        on the specified time ranges.

        Args:
            details_range (str, optional): The range for detailed statistics ("day" or "week"). Defaults to "day".
            trend_range (str, optional): The range for trend statistics ("week" or "month"). Defaults to "week".

        Returns:
            dict[str, int]: A dictionary containing summary, details, and trend statistics.

        """
        if self.data is None:
            # If no data is available, return an empty dictionary
            return {}

        # Initialize counters and dictionaries for statistics
        total_tasks = 0
        today_tasks = 0
        completed_tasks = 0
        details = {}
        trend = {}

        # Get the current date and time in the user's timezone
        today = datetime.now(self.timezone)

        # Determine the start and end times for the details range
        if details_range == "day":
            details_start, details_end = get_time_range(today, "day")
        elif details_range == "week":
            details_start, details_end = get_time_range(today, "week")
        else:
            details_start, details_end = None, None

        # Determine the start and end times for the trend range and set the index range
        if trend_range == "week":
            trend_start, trend_end = get_time_range(today, "week")
            trend_index_range = 7
        elif trend_range == "month":
            trend_start, trend_end = get_time_range(today, "month")
            trend_index_range = trend_end.day
        else:
            trend_start, trend_end = None, None
            trend_index_range = 0

        # Iterate through each task list in the data
        for task_list in self.data:
            for taskseries in task_list:
                # Check if the task is completed
                is_completed = taskseries.task.completed

                # Increment the total task counter
                total_tasks += 1
                # Increment the completed task counter if the task is completed
                if is_completed:
                    completed_tasks += 1

                # Determine the due time of the task, converting to the user's timezone
                if taskseries.task.due:
                    due_time = datetime.fromisoformat(taskseries.task.due).astimezone(
                        self.timezone
                    )
                else:
                    due_time = datetime.fromisoformat(taskseries.task.added).astimezone(
                        self.timezone
                    )

                # Increment today's task counter if the task is due today
                if due_time.date() == today.date():
                    today_tasks += 1

                # Update details statistics if the task falls within the details range
                if (
                    details_start
                    and details_end
                    and details_start <= due_time <= details_end
                ):
                    details["total"] = details.get("total", 0) + 1
                    if is_completed:
                        details["completed"] = details.get("completed", 0) + 1

                # Update trend statistics if the task falls within the trend range
                if trend_start and trend_end and trend_start <= due_time <= trend_end:
                    date = due_time.date()
                    if date not in trend:
                        trend[date] = {"total": 0, "completed": 0}
                    trend[date]["total"] += 1
                    if is_completed:
                        trend[date]["completed"] += 1

        # Normalize the trend dictionary to have a continuous index range
        for i in range(trend_index_range):
            date = (trend_start + timedelta(days=i)).date()
            if date not in trend:
                trend[i] = {"total": 0, "completed": 0}
            else:
                trend[i] = trend.pop(date)

        # Return the compiled statistics
        return {
            "summary": {
                "total_tasks": total_tasks,
                "today_tasks": today_tasks,
                "completed_tasks": completed_tasks,
            },
            "details": details,
            "trend": trend,
        }

    async def async_delete_task(
        self, list_id: str, taskseries_id: str, task_id: str
    ) -> None:
        """Delete a task on Remember The Milk using taskseries_id and task_id.

        Args:
            list_id (str): The ID of the list containing the task.
            taskseries_id (str): The ID of the task series.
            task_id (str): The ID of the specific task to delete.

        Raises:
            UpdateFailed: If there is an error communicating with the API.

        """
        try:
            # Create a new timeline entry asynchronously with rate limiting
            result = await run_async(self.rate_limiter, self.api.rtm.timelines.create)
            timeline = result.timeline.value
            # Delete the specified task using the API
            await run_async(
                self.rate_limiter,
                lambda: self.api.rtm.tasks.delete(
                    timeline=timeline,
                    list_id=list_id,
                    taskseries_id=taskseries_id,
                    task_id=task_id,
                ),
            )
        except Exception as err:
            # Raise an UpdateFailed exception if an error occurs
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
        """Update name, due date, and/or task completed status of a task on Remember The Milk.

        Args:
            list_id (str): The ID of the list containing the task.
            name (str): The new name for the task.
            taskseries_id (str): The ID of the task series.
            task_id (str): The ID of the specific task to update.
            due (str): The new due date for the task in ISO format.
            has_due_time (str): Indicates if the task has a due time.
            status (str): The new status of the task (e.g., completed or needs action).

        Raises:
            UpdateFailed: If there is an error communicating with the API.
            ValueError: If the old task is not found in the current data.

        """
        try:
            # Create a new timeline entry asynchronously with rate limiting
            result = await run_async(self.rate_limiter, self.api.rtm.timelines.create)
            # Find the existing task in the current data
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
                # Raise an error if the old task is not found
                raise ValueError(f"Old task with ID {taskseries_id} not found")

            # Determine what changes need to be made
            change_name = old_task.name != name
            change_due_date = old_task.task.due != due
            old_complete_status = (
                TodoItemStatus.COMPLETED
                if old_task.task.completed
                else TodoItemStatus.NEEDS_ACTION,
            )
            change_complete_status = old_complete_status != status

            # Get the timeline value for API operations
            timeline = result.timeline.value
            # Determine the appropriate action for completing or uncompleting the task
            complete_action = (
                self.api.rtm.tasks.complete
                if status == TodoItemStatus.COMPLETED
                else self.api.rtm.tasks.uncomplete
            )
            # Update the task name if it has changed
            if change_name:
                await run_async(
                    self.rate_limiter,
                    lambda: self.api.rtm.tasks.setName(
                        timeline=timeline,
                        list_id=list_id,
                        taskseries_id=taskseries_id,
                        task_id=task_id,
                        name=name,
                    ),
                )
            # Update the task due date if it has changed
            if change_due_date:
                await run_async(
                    self.rate_limiter,
                    lambda: self.api.rtm.tasks.setDueDate(
                        timeline=timeline,
                        list_id=list_id,
                        taskseries_id=taskseries_id,
                        task_id=task_id,
                        due=due,
                        has_due_time=has_due_time,
                    ),
                )
            # Update the task's completion status if it has changed
            if change_complete_status:
                await run_async(
                    self.rate_limiter,
                    lambda: complete_action(
                        timeline=timeline,
                        list_id=list_id,
                        taskseries_id=taskseries_id,
                        task_id=task_id,
                    ),
                )

        except Exception as err:
            # Raise an UpdateFailed exception if an error occurs
            raise UpdateFailed(f"Error communicating with API: {err}") from err
