from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from rtmapi import RtmIterableObject

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_point_in_time


class RememberTheMilkNotifications:
    """Notifications for sending reminders that tasks are due for Remember The Milk."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the RememberTheMilkNotifications class.

        Args:
            hass (HomeAssistant): The Home Assistant instance.

        """
        self.hass = hass
        # Time gap before sending notification for tasks due.
        self._notification_offset = timedelta(hours=1)
        # Set to track task IDs for which notifications have been sent.
        self._notifications_sent = set()
        # Retrieve the timezone configured in Home Assistant.
        self.timezone = ZoneInfo(hass.config.time_zone)

    async def update_notifications(self, data: RtmIterableObject):
        """Send notification reminders for tasks with due dates in the notification offset time.

        Args:
            data (RtmIterableObject): A collection of task lists from Remember The Milk.

        """
        # Retrieve tasks with due dates from the data.
        tasks_due_list = self._get_due_date_tasks(data)
        # Keep only notifications for tasks that are still active.
        active_tasks = {taskseries.task.id for taskseries in tasks_due_list}
        self._notifications_sent.intersection_update(active_tasks)

        # Get the current time in the configured timezone.
        curr_time = datetime.now(self.timezone)

        for taskseries in tasks_due_list:
            # Skip if a notification for this task has already been sent.
            if taskseries.task.id in self._notifications_sent:
                continue

            # Convert the task's due date to the correct timezone.
            notify_time = datetime.fromisoformat(taskseries.task.due).astimezone(
                self.timezone
            )

            # Skip tasks that are overdue.
            if curr_time > notify_time:
                continue

            # Send a notification if the task is within the notification time window.
            if notify_time > curr_time > (notify_time - self._notification_offset):
                self._notifications_sent.add(taskseries.task.id)
                await self.create_persistent_notification(
                    taskseries.name, notify_time.replace(second=0)
                )

    def _get_due_date_tasks(self, data: RtmIterableObject) -> list:
        """Retrieve a list of tasks that have due dates and are not completed.

        Args:
            data (RtmIterableObject): A collection of task lists from Remember The Milk.

        Returns:
            list: A list of task series with due dates.

        """
        due_list = []
        for task_list in data:
            for taskseries in task_list:
                # Include tasks that have a due date and are not completed.
                if taskseries.task.due and not taskseries.task.completed:
                    due_list.append(taskseries)  # noqa: PERF401
        return due_list

    async def create_persistent_notification(self, task_name: str, due_date: datetime):
        """Create a persistent notification for a specific task.

        Args:
            task_name (str): The name of the task.
            due_date (datetime): The due date and time of the task.

        Raises:
            Exception: If the notification fails to send.

        """
        try:
            # Use the Home Assistant service to create a persistent notification.
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": f"Reminder: Task '{task_name}' is due soon! \n Due: {due_date.strftime('%d %B %H:%M')}",
                    "title": "Task Reminder",
                    "notification_id": f"task_reminder_{task_name.replace(' ', '_')}",
                },
            )
        except Exception as e:  # noqa: BLE001
            # Raise an exception if notification fails.
            raise Exception(f"Failed to send notification for task '{task_name}': {e}")  # noqa: TRY002
