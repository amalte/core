# tests/components/remember_the_milk/test_notifications.py

"""Tests for the Remember The Milk Notifications."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.components.remember_the_milk.notifications import (
    RememberTheMilkNotifications,
)
from rtmapi import RtmIterableObject


@pytest.fixture
def mock_hass():
    """Fixture to create a mock HomeAssistant instance with config.time_zone."""
    # Create a Mock for the 'config' attribute
    config_mock = Mock()
    config_mock.time_zone = "UTC"

    # Create the main HomeAssistant Mock
    hass = Mock(spec=HomeAssistant)
    hass.config = config_mock  # Assign the 'config' Mock to 'hass.config'
    hass.services = AsyncMock()

    return hass


@pytest.fixture
def mock_rtm_iterable_object():
    """Fixture to create a mock RtmIterableObject."""
    mock_obj = MagicMock(spec=RtmIterableObject)
    mock_obj.__iter__ = Mock(return_value=iter([]))
    return mock_obj


@pytest.fixture
def notifications(mock_hass):
    """Fixture to create an instance of RememberTheMilkNotifications."""
    return RememberTheMilkNotifications(mock_hass)


def create_taskseries(task_id, name, due, completed=False):
    """Helper function to create a mock taskseries object."""
    task = Mock()
    task.id = task_id
    task.completed = completed
    if due is not None:
        task.due = due.isoformat()
        task.added = (due - timedelta(days=1)).isoformat()
    else:
        task.due = None
        task.added = None

    # Create a mock note object with 'value'
    note = Mock()
    note.value = f"Description for {name}"

    # Create a MagicMock for notes that has both 'note' attribute and is iterable
    notes_mock = MagicMock()
    notes_mock.note = note
    notes_mock.__iter__.return_value = iter([note])

    taskseries = Mock()
    taskseries.task = task
    taskseries.name = name
    taskseries.notes = notes_mock

    return taskseries


@pytest.mark.asyncio
async def test_get_due_date_tasks(notifications, mock_rtm_iterable_object):
    """Test that _get_due_date_tasks returns only tasks with due dates and not completed."""
    # Create mock taskseries
    task1 = create_taskseries(
        task_id="1",
        name="Task 1",
        due=datetime.now(tz=ZoneInfo("UTC")) + timedelta(hours=2),
        completed=False,
    )
    task2 = create_taskseries(
        task_id="2",
        name="Task 2",
        due=datetime.now(tz=ZoneInfo("UTC")) + timedelta(hours=3),
        completed=True,
    )
    task3 = create_taskseries(
        task_id="3",
        name="Task 3",
        due=None,  # No due date
        completed=False,
    )
    task4 = create_taskseries(
        task_id="4",
        name="Task 4",
        due=datetime.now(tz=ZoneInfo("UTC")) + timedelta(hours=4),
        completed=False,
    )

    # Mock data: Two task lists containing tasks
    mock_rtm_iterable_object.__iter__.return_value = iter(
        [
            Mock(__iter__=Mock(return_value=iter([task1, task2]))),
            Mock(__iter__=Mock(return_value=iter([task3, task4]))),
        ]
    )

    # Call the method
    due_tasks = notifications._get_due_date_tasks(mock_rtm_iterable_object)

    # Assertions
    assert len(due_tasks) == 2
    assert due_tasks[0].task.id == "1"
    assert due_tasks[1].task.id == "4"


@pytest.mark.asyncio
async def test_update_notifications_sends_due_notifications(
    notifications, mock_hass, mock_rtm_iterable_object
):
    """Test that update_notifications sends notifications for due tasks within the offset."""
    current_time = datetime.now(tz=ZoneInfo("UTC"))

    # Create mock taskseries due within the notification offset (1 hour)
    task1_due = current_time + timedelta(minutes=30)
    task1 = create_taskseries(
        task_id="1",
        name="Task 1",
        due=task1_due,
        completed=False,
    )

    # Create mock taskseries due outside the notification offset
    task2_due = current_time + timedelta(hours=2)
    task2 = create_taskseries(
        task_id="2",
        name="Task 2",
        due=task2_due,
        completed=False,
    )

    # Mock data: One task list with two tasks
    mock_rtm_iterable_object.__iter__.return_value = iter(
        [
            Mock(__iter__=Mock(return_value=iter([task1, task2]))),
        ]
    )

    # Mock datetime.now to return current_time
    with patch(
        "homeassistant.components.remember_the_milk.notifications.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = current_time
        # Ensure fromisoformat returns a timezone-aware datetime
        mock_datetime.fromisoformat.side_effect = lambda s: datetime.fromisoformat(
            s
        ).replace(tzinfo=ZoneInfo("UTC"))

        await notifications.update_notifications(mock_rtm_iterable_object)

    # Verify that a notification was sent for task1
    mock_hass.services.async_call.assert_awaited_once_with(
        "persistent_notification",
        "create",
        {
            "message": f"Reminder: Task 'Task 1' is due soon! \n Due: {task1_due.strftime('%d %B %H:%M')}",
            "title": "Task Reminder",
            "notification_id": "task_reminder_Task_1",
        },
    )

    # Verify that task1's ID is added to _notifications_sent
    assert "1" in notifications._notifications_sent

    # Verify that no notification was sent for task2
    assert "2" not in notifications._notifications_sent


@pytest.mark.asyncio
async def test_update_notifications_avoids_duplicate_notifications(
    notifications, mock_hass, mock_rtm_iterable_object
):
    """Test that update_notifications does not send duplicate notifications for the same task."""
    current_time = datetime.now(tz=ZoneInfo("UTC"))

    # Create mock taskseries due within the notification offset (1 hour)
    task1_due = current_time + timedelta(minutes=30)
    task1 = create_taskseries(
        task_id="1",
        name="Task 1",
        due=task1_due,
        completed=False,
    )

    # Add task1 to _notifications_sent to simulate that a notification was already sent
    notifications._notifications_sent.add("1")

    # Mock data: One task list with task1
    mock_rtm_iterable_object.__iter__.return_value = iter(
        [
            Mock(__iter__=Mock(return_value=iter([task1]))),
        ]
    )

    # Mock datetime.now to return current_time
    with patch(
        "homeassistant.components.remember_the_milk.notifications.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = current_time
        # Ensure fromisoformat returns a timezone-aware datetime
        mock_datetime.fromisoformat.side_effect = lambda s: datetime.fromisoformat(
            s
        ).replace(tzinfo=ZoneInfo("UTC"))

        await notifications.update_notifications(mock_rtm_iterable_object)

    # Verify that async_call was not called since notification was already sent
    mock_hass.services.async_call.assert_not_called()

    # Verify that _notifications_sent still contains task1's ID
    assert "1" in notifications._notifications_sent


@pytest.mark.asyncio
async def test_update_notifications_with_past_due_tasks(
    notifications, mock_hass, mock_rtm_iterable_object
):
    """Test that update_notifications does not send notifications for tasks already past due."""
    current_time = datetime.now(tz=ZoneInfo("UTC"))

    # Create mock taskseries due in the past
    task1_due = current_time - timedelta(minutes=10)
    task1 = create_taskseries(
        task_id="1",
        name="Task 1",
        due=task1_due,
        completed=False,
    )

    # Mock data: One task list with task1
    mock_rtm_iterable_object.__iter__.return_value = iter(
        [
            Mock(__iter__=Mock(return_value=iter([task1]))),
        ]
    )

    # Mock datetime.now to return current_time
    with patch(
        "homeassistant.components.remember_the_milk.notifications.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = current_time
        # Ensure fromisoformat returns a timezone-aware datetime
        mock_datetime.fromisoformat.side_effect = lambda s: datetime.fromisoformat(
            s
        ).replace(tzinfo=ZoneInfo("UTC"))

        await notifications.update_notifications(mock_rtm_iterable_object)

    # Verify that no notification was sent
    mock_hass.services.async_call.assert_not_called()

    # Verify that task1's ID is not added to _notifications_sent
    assert "1" not in notifications._notifications_sent


@pytest.mark.asyncio
async def test_create_persistent_notification_success(notifications, mock_hass):
    """Test that create_persistent_notification successfully calls the notification service."""
    task_name = "Task 1"
    due_date = datetime(2024, 12, 31, 15, 30, tzinfo=ZoneInfo("UTC"))

    await notifications.create_persistent_notification(task_name, due_date)

    # Verify that async_call was called with correct parameters
    mock_hass.services.async_call.assert_awaited_once_with(
        "persistent_notification",
        "create",
        {
            "message": f"Reminder: Task '{task_name}' is due soon! \n Due: {due_date.strftime('%d %B %H:%M')}",
            "title": "Task Reminder",
            "notification_id": f"task_reminder_{task_name.replace(' ', '_')}",
        },
    )


@pytest.mark.asyncio
async def test_create_persistent_notification_failure(notifications, mock_hass):
    """Test that create_persistent_notification raises an exception when service call fails."""
    task_name = "Task 1"
    due_date = datetime(2024, 12, 31, 15, 30, tzinfo=ZoneInfo("UTC"))

    # Configure the mock to raise an exception
    mock_hass.services.async_call.side_effect = Exception("Service call failed")

    with pytest.raises(Exception) as exc_info:
        await notifications.create_persistent_notification(task_name, due_date)

    assert (
        f"Failed to send notification for task '{task_name}': Service call failed"
        in str(exc_info.value)
    )

    # Verify that async_call was attempted
    mock_hass.services.async_call.assert_awaited_once_with(
        "persistent_notification",
        "create",
        {
            "message": f"Reminder: Task '{task_name}' is due soon! \n Due: {due_date.strftime('%d %B %H:%M')}",
            "title": "Task Reminder",
            "notification_id": f"task_reminder_{task_name.replace(' ', '_')}",
        },
    )


@pytest.mark.asyncio
async def test_update_notifications_with_no_tasks(
    notifications, mock_hass, mock_rtm_iterable_object
):
    """Test that update_notifications does not send notifications when there are no tasks."""
    # Mock data with no tasks
    mock_rtm_iterable_object.__iter__.return_value = iter([])

    # Mock datetime.now to return current_time
    current_time = datetime.now(tz=ZoneInfo("UTC"))
    with patch(
        "homeassistant.components.remember_the_milk.notifications.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = current_time
        # Ensure fromisoformat returns a timezone-aware datetime
        mock_datetime.fromisoformat.side_effect = lambda s: datetime.fromisoformat(
            s
        ).replace(tzinfo=ZoneInfo("UTC"))

        await notifications.update_notifications(mock_rtm_iterable_object)

    # Verify that no notification was sent
    mock_hass.services.async_call.assert_not_called()

    # Verify that _notifications_sent remains empty
    assert len(notifications._notifications_sent) == 0
