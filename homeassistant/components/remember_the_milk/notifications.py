from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.event import async_track_point_in_time
from datetime import datetime, timedelta, UTC
from rtmapi import RtmIterableObject

class RememberTheMilkNotifications():
    """Notifications for sending reminders that tasks are due for Remember The Milk."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the RememberTheMilkNotifications class."""
        self.hass = hass
        self._notification_offset = timedelta(hours=1) # Time gap before sending notification.
        self._notifications_sent = set() # Contains task ids to keep track of notifications sent.
    
    async def update_notifications(self, data: RtmIterableObject):
        """Sends notification reminders on home assistant for tasks with due date in the notification offset time."""
        tasks_due_list = self._get_due_date_tasks(data)
        # Remove any stale notifications (tasks being removed etc.).
        active_tasks = {taskseries.task.id for taskseries in tasks_due_list}
        self._notifications_sent.intersection_update(active_tasks)

        curr_time = datetime.now()
        
        for taskseries in tasks_due_list:
            # Skip iteration if already sent notification for this task.
            if taskseries.task.id in self._notifications_sent:
                continue

            notify_time = datetime.fromisoformat(taskseries.task.due).replace(tzinfo=None) + timedelta(hours=1)

            # Skip iteration if due date is in the past.
            if curr_time > notify_time:
                continue
            # Send notification if in the notification time window.
            elif notify_time > curr_time > (notify_time - self._notification_offset): 
                self._notifications_sent.add(taskseries.task.id)
                await self.create_persistent_notification(taskseries.name, notify_time.replace(second=0))

    def _get_due_date_tasks(self, data: RtmIterableObject) -> list:
        """Get and return a list of all tasks with due dates."""
        due_list = []
        for task_list in data:
            for taskseries in task_list:
                if taskseries.task.due:
                    due_list.append(taskseries)
            
        return due_list

    async def create_persistent_notification(self, task_name: str, due_date: datetime):
        """Create a persistent notification for a task."""
        try: 
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": f"Reminder: Task '{task_name}' is due soon! \n Due: {due_date.strftime("%d %B %H:%M")}",
                    "title": "Task Reminder",
                    "notification_id": f"task_reminder_{task_name.replace(' ', '_')}",
                },
            )
        except Exception as e:
            raise Exception(f"Failed to send notification for task '{task_name}': {e}") 
