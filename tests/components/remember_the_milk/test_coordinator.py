# tests/components/remember_the_milk/test_coordinator.py

"""Tests for the Remember The Milk Coordinator."""

from datetime import datetime, timedelta, timezone
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.remember_the_milk.coordinator import (
    RememberTheMilkCoordinator,
)
from homeassistant.components.remember_the_milk.notifications import (
    RememberTheMilkNotifications,
)
from homeassistant.components.todo import TodoItemStatus
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.mark.asyncio
async def test_coordinator_initialization_and_setup_rate_limiter():
    """Initialize coordinator and start rate limiter."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "Europe/Stockholm"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm") as mock_rtm,
        patch(
            "homeassistant.components.remember_the_milk.coordinator.RateLimiter"
        ) as mock_rate_limiter_cls,
    ):
        mock_rate_limiter = mock_rate_limiter_cls.return_value
        mock_rate_limiter.start = AsyncMock()

        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=logging.getLogger(__name__),
            api_key="test_api_key",
            shared_secret="test_shared_secret",
            token="test_token",
        )

        assert str(coordinator.timezone) == "Europe/Stockholm"
        assert isinstance(coordinator.notifications, RememberTheMilkNotifications)
        assert coordinator.api is mock_rtm.return_value
        assert coordinator.rate_limiter == mock_rate_limiter
        assert not coordinator.initialized

        await coordinator.async_setup_rate_limiter()
        mock_rate_limiter.start.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_update_data_success():
    """Return fetched task data on a successful API call."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    mock_task_data = [{"id": "task1", "name": "Task One"}]
    mock_result = MagicMock()
    mock_result.tasks = mock_task_data

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
        patch(
            "homeassistant.components.remember_the_milk.coordinator.run_async",
            return_value=mock_result,
        ),
        patch(
            "homeassistant.components.remember_the_milk.coordinator.RememberTheMilkNotifications.update_notifications",
            new_callable=AsyncMock,
        ) as mock_update_notifications,
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=logging.getLogger(__name__),
            api_key="test_api_key",
            shared_secret="test_shared_secret",
            token="test_token",
        )

        data = await coordinator._async_update_data()

    mock_update_notifications.assert_awaited_once_with(mock_task_data)
    assert data == mock_task_data


@pytest.mark.asyncio
async def test_async_update_data_failure():
    """Raise UpdateFailed when API call fails."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
        patch(
            "homeassistant.components.remember_the_milk.coordinator.run_async",
            side_effect=Exception("API error"),
        ),
        patch(
            "homeassistant.components.remember_the_milk.coordinator.RememberTheMilkNotifications.update_notifications",
            new_callable=AsyncMock,
        ),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=logging.getLogger(__name__),
            api_key="test_api_key",
            shared_secret="test_shared_secret",
            token="test_token",
        )

        with pytest.raises(UpdateFailed) as exc_info:
            await coordinator._async_update_data()

    assert "Error communicating with API: API error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_async_create_task_with_duplicate():
    """Raise ValueError if a duplicate task name exists."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
        patch(
            "homeassistant.components.remember_the_milk.coordinator.run_async",
            new_callable=AsyncMock,
        ) as mock_run_async,
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="test_api_key",
            shared_secret="test_shared_secret",
            token="test_token",
        )

        existing_task_name = "Existing Task"
        existing_task = MagicMock()
        existing_task.name = existing_task_name
        coordinator.async_get_tasks = AsyncMock(return_value=[existing_task])

        timeline_result = MagicMock()
        timeline_result.timeline.value = "fake_timeline"
        mock_run_async.return_value = timeline_result

        with pytest.raises(ValueError) as excinfo:
            await coordinator.async_create_task(
                list_id="test_list_id",
                task_name=existing_task_name,
                due="2024-12-31T23:59:59Z",
                description="A test description",
            )

        assert "already exists in this list" in str(excinfo.value)


@pytest.mark.asyncio
async def test_check_duplicate_lists():
    """Check for duplicate lists under various conditions."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="test_api_key",
            shared_secret="test_shared_secret",
            token="test_token",
        )

    coordinator.data = None
    coordinator.async_get_task_lists = AsyncMock(return_value=None)
    result = await coordinator._check_duplicate_lists("list1", "ts1", "New Task", "add")
    assert result == []

    fake_task_list_1 = MagicMock()
    fake_task_list_1.id = "list1"
    fake_task_list_1.name = "Personal"

    fake_task_list_2 = MagicMock()
    fake_task_list_2.id = "list2"
    fake_task_list_2.name = "Work"

    task_series_a = MagicMock()
    task_series_a.id = "tsA"
    task_series_a.name = "Task A"
    task_series_a.task.completed = False
    task_series_a.task.due = None
    task_series_a.task.added = "2024-12-31T23:59:59Z"

    task_series_b = MagicMock()
    task_series_b.id = "tsB"
    task_series_b.name = "Task B"
    task_series_b.task.completed = False
    task_series_b.task.due = None
    task_series_b.task.added = "2024-12-31T23:59:59Z"

    task_series_c = MagicMock()
    task_series_c.id = "tsC"
    task_series_c.name = "Task C"
    task_series_c.task.completed = False
    task_series_c.task.due = None
    task_series_c.task.added = "2024-12-31T23:59:59Z"

    task_series_d = MagicMock()
    task_series_d.id = "tsD"
    task_series_d.name = "Task D"
    task_series_d.task.completed = False
    task_series_d.task.due = None
    task_series_d.task.added = "2024-12-31T23:59:59Z"

    coordinator.data = [
        type(
            "MockList",
            (object,),
            {
                "id": "list1",
                "__iter__": lambda self: iter([task_series_a, task_series_b]),
            },
        )(),
        type(
            "MockList",
            (object,),
            {
                "id": "list2",
                "__iter__": lambda self: iter([task_series_c, task_series_d]),
            },
        )(),
    ]

    coordinator.async_get_task_lists = AsyncMock(
        return_value=[fake_task_list_1, fake_task_list_2]
    )

    result = await coordinator._check_duplicate_lists("list1", "", "Task X", "add")
    assert result == []

    result = await coordinator._check_duplicate_lists(
        "list1", "tsB", "Task C", "update"
    )
    assert result == []

    result = await coordinator._check_duplicate_lists("list1", "tsB", "", "delete")
    assert result == []

    task_series_c.name = "Task A"
    task_series_d.name = "Task D"
    result = await coordinator._check_duplicate_lists(
        "list1", "tsB", "Task D", "update"
    )
    assert len(result) == 1
    assert "Work" in result


@pytest.mark.asyncio
async def test_async_create_task_no_duplicate():
    """Create a task without triggering a duplicate error."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch(
            "homeassistant.components.remember_the_milk.coordinator.RateLimiter"
        ) as mock_rate_limiter,
    ):
        mock_rate_limiter_inst = mock_rate_limiter.return_value
        mock_rate_limiter_inst.start = AsyncMock()
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="test_api_key",
            shared_secret="test_shared_secret",
            token="test_token",
        )
        await coordinator.async_setup_rate_limiter()

    existing_task = MagicMock()
    existing_task.name = "Some Other Task"
    coordinator.async_get_tasks = AsyncMock(return_value=[existing_task])

    timeline_result = MagicMock()
    timeline_result.timeline.value = "fake_timeline"
    add_result = MagicMock()

    async def mock_run_async(rate_limiter, func, *args, **kwargs):
        if "timelines.create" in str(func) or (
            callable(func) and "timelines.create" in str(func)
        ):
            return timeline_result
        if "tasks.add" in str(func) or (callable(func) and "tasks.add" in str(func)):
            return add_result
        return MagicMock()

    with patch(
        "homeassistant.components.remember_the_milk.coordinator.run_async",
        new=mock_run_async,
    ):
        try:
            await coordinator.async_create_task(
                list_id="test_list_id",
                task_name="Unique New Task",
                due="2024-12-31T23:59:59Z",
                description="Test Description",
            )
        except ValueError as e:
            pytest.fail(f"Unexpected ValueError raised: {e}")
        except UpdateFailed as e:
            pytest.fail(f"Unexpected UpdateFailed raised: {e}")


@pytest.mark.asyncio
async def test_check_duplicate_task_no_list():
    """Return empty string if the task list does not exist."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="test_api_key",
            shared_secret="test_shared_secret",
            token="test_token",
        )

    coordinator.async_get_tasks = AsyncMock(return_value=None)
    result = await coordinator._check_duplicate_task("some_list_id", "NonExistent Task")
    assert result == ""


@pytest.mark.asyncio
async def test_check_duplicate_lists_empty_after_operation():
    """Return empty when target_tasks becomes empty after operation."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="test_api_key",
            shared_secret="test_shared_secret",
            token="test_token",
        )

    fake_task_list = MagicMock()
    fake_task_list.id = "list1"
    fake_task_list.name = "Test List"

    single_task = MagicMock()
    single_task.id = "ts1"
    single_task.name = "Unique Task"
    single_task.task.completed = False
    single_task.task.due = None
    single_task.task.added = "2024-12-31T23:59:59Z"

    coordinator.data = [
        type(
            "MockList",
            (object,),
            {"id": "list1", "__iter__": lambda self_it: iter([single_task])},
        )()
    ]

    coordinator.async_get_task_lists = AsyncMock(return_value=[fake_task_list])
    result = await coordinator._check_duplicate_lists("list1", "ts1", "", "delete")
    assert result == []


@pytest.mark.asyncio
async def test_get_statistics_various_ranges():
    """Compute statistics with various details and trend ranges."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    coordinator = RememberTheMilkCoordinator(
        hass=hass,
        logger=MagicMock(),
        api_key="test_api_key",
        shared_secret="test_shared_secret",
        token="test_token",
    )

    coordinator.data = None
    stats = coordinator.get_statistics()
    assert stats == {}

    base_today = datetime.now(timezone.utc).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    today_str = base_today.isoformat()
    tomorrow_str = (base_today + timedelta(days=1)).isoformat()
    yesterday_str = (base_today - timedelta(days=1)).isoformat()
    no_due_added = (base_today - timedelta(days=2)).isoformat()

    def make_task_series(name, due=None, completed=False, added=None):
        task_series = MagicMock()
        task_series.name = name
        task_series.task.completed = completed
        task_series.task.due = due
        task_series.task.added = (
            added if added else datetime.now(timezone.utc).isoformat()
        )
        return task_series

    list1 = type(
        "MockList1",
        (object,),
        {
            "id": "list1",
            "__iter__": lambda self: iter(
                [
                    make_task_series("Today Task 1", due=today_str, completed=False),
                    make_task_series("Today Task 2", due=today_str, completed=True),
                ]
            ),
        },
    )()

    list2 = type(
        "MockList2",
        (object,),
        {
            "id": "list2",
            "__iter__": lambda self: iter(
                [
                    make_task_series(
                        "Yesterday Task", due=yesterday_str, completed=False
                    ),
                    make_task_series(
                        "Tomorrow Task", due=tomorrow_str, completed=False
                    ),
                    make_task_series(
                        "No Due Task", due=None, completed=False, added=no_due_added
                    ),
                ]
            ),
        },
    )()

    coordinator.data = [list1, list2]

    stats = coordinator.get_statistics(details_range="day", trend_range="week")
    assert stats["summary"]["today_tasks"] == 2
    assert stats["summary"]["completed_tasks"] == 1
    assert stats["details"]["total"] == 2
    assert stats["details"]["completed"] == 1
    assert "trend" in stats
    assert len(stats["trend"]) > 0

    stats = coordinator.get_statistics(details_range="week", trend_range="month")
    assert "summary" in stats
    assert "details" in stats
    assert "trend" in stats

    stats = coordinator.get_statistics(details_range="invalid", trend_range="invalid")
    assert "summary" in stats


@pytest.mark.asyncio
async def test_async_update_task_no_changes():
    """Do not call API methods when no task changes are made."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="test_api_key",
            shared_secret="test_shared_secret",
            token="test_token",
        )

    existing_task = MagicMock()
    existing_task.id = "ts_existing"
    existing_task.name = "Original Task Name"
    existing_task.task.completed = False
    existing_task.task.due = "2025-01-01T12:00:00Z"

    coordinator.data = [
        type(
            "MockList",
            (object,),
            {"id": "list1", "__iter__": lambda self: iter([existing_task])},
        )()
    ]

    timeline_mock = MagicMock()
    timeline_mock.timeline.value = "fake_timeline"
    with patch(
        "homeassistant.components.remember_the_milk.coordinator.run_async",
        new_callable=AsyncMock,
    ) as mock_run_async:

        async def run_async_side_effect(rate, func, *args, **kwargs):
            if "timelines.create" in str(func) or (
                callable(func) and "timelines.create" in str(func)
            ):
                return timeline_mock
            return MagicMock()

        mock_run_async.side_effect = run_async_side_effect

        await coordinator.async_update_task(
            list_id="list1",
            name="Original Task Name",
            taskseries_id="ts_existing",
            task_id="task_id",
            due="2025-01-01T12:00:00Z",
            has_due_time="1",
            status=TodoItemStatus.NEEDS_ACTION,
        )

        calls = [call[0][1] for call in mock_run_async.call_args_list]
        assert all("setName" not in str(c) for c in calls)
        assert all("setDueDate" not in str(c) for c in calls)
        assert all("complete" not in str(c) for c in calls)
        assert all("uncomplete" not in str(c) for c in calls)


@pytest.mark.asyncio
async def test_async_run_rtm_method_no_duplicates():
    """Execute RTM method without duplicates."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="key",
            shared_secret="secret",
            token="token",
        )

    coordinator._check_duplicate_lists = AsyncMock(return_value=[])

    timeline_mock = MagicMock()
    timeline_mock.timeline.value = "fake_timeline"

    async def run_async_side_effect(rate_limiter, func, *args, **kwargs):
        if "timelines.create" in str(func):
            return timeline_mock
        return MagicMock()

    with patch(
        "homeassistant.components.remember_the_milk.coordinator.run_async",
        side_effect=run_async_side_effect,
    ):
        request = "rtm.tasks.add"
        payload = {"list_id": "list1", "taskseries_id": "ts1", "name": "New Task"}
        result = await coordinator.async_run_rtm_method(request, payload)
        assert result is not None


@pytest.mark.asyncio
async def test_async_run_rtm_method_with_duplicates():
    """Raise ValueError when duplicates are detected in RTM method."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="key",
            shared_secret="secret",
            token="token",
        )

    coordinator._check_duplicate_lists = AsyncMock(return_value=["Duplicate List"])

    timeline_mock = MagicMock()
    timeline_mock.timeline.value = "fake_timeline"

    async def run_async_side_effect(rate_limiter, func, *args, **kwargs):
        if "timelines.create" in str(func):
            return timeline_mock
        return MagicMock()

    with patch(
        "homeassistant.components.remember_the_milk.coordinator.run_async",
        side_effect=run_async_side_effect,
    ):
        request = "rtm.tasks.add"
        payload = {"list_id": "list1", "taskseries_id": "ts1", "name": "Existing Task"}
        with pytest.raises(ValueError) as excinfo:
            await coordinator.async_run_rtm_method(request, payload)
        assert "Tasks will be same" in str(excinfo.value)


@pytest.mark.asyncio
async def test_async_run_rtm_method_api_failure():
    """Raise UpdateFailed if RTM method call fails."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm") as mock_rtm,
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="key",
            shared_secret="secret",
            token="token",
        )

    coordinator._check_duplicate_lists = AsyncMock(return_value=[])

    timeline_mock = MagicMock()
    timeline_mock.timeline.value = "fake_timeline"
    mock_request_method = AsyncMock(side_effect=Exception("API error"))
    mock_rtm.return_value.rtm.tasks.setName = mock_request_method

    async def run_async_side_effect(rate_limiter, func, *args, **kwargs):
        if "timelines.create" in str(func):
            return timeline_mock
        return await func()

    with patch(
        "homeassistant.components.remember_the_milk.coordinator.run_async",
        side_effect=run_async_side_effect,
    ):
        request = "rtm.tasks.setName"
        payload = {"list_id": "list1", "taskseries_id": "ts1", "name": "New Name"}
        with pytest.raises(UpdateFailed) as excinfo:
            await coordinator.async_run_rtm_method(request, payload)
        assert "Error communicating with API: API error" in str(excinfo.value)


@pytest.mark.asyncio
async def test_async_delete_task_no_duplicates():
    """Delete a task successfully when no duplicates."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="key",
            shared_secret="secret",
            token="token",
        )

    coordinator._check_duplicate_lists = AsyncMock(return_value=[])

    timeline_mock = MagicMock()
    timeline_mock.timeline.value = "fake_timeline"

    async def run_async_side_effect(rate_limiter, func, *args, **kwargs):
        if "timelines.create" in str(func):
            return timeline_mock
        return MagicMock()

    with patch(
        "homeassistant.components.remember_the_milk.coordinator.run_async",
        side_effect=run_async_side_effect,
    ):
        await coordinator.async_delete_task("list1", "ts1", "task_id")


@pytest.mark.asyncio
async def test_async_delete_task_duplicates_found():
    """Raise ValueError when duplicates are found during task deletion."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="key",
            shared_secret="secret",
            token="token",
        )

    coordinator._check_duplicate_lists = AsyncMock(return_value=["Duplicate List"])

    with pytest.raises(ValueError) as excinfo:
        await coordinator.async_delete_task("list1", "ts1", "task_id")
    assert "Tasks will be same" in str(excinfo.value)


@pytest.mark.asyncio
async def test_async_delete_task_api_failure():
    """Raise UpdateFailed if task deletion API call fails."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="key",
            shared_secret="secret",
            token="token",
        )

    coordinator._check_duplicate_lists = AsyncMock(return_value=[])

    timeline_mock = MagicMock()
    timeline_mock.timeline.value = "fake_timeline"

    async def run_async_side_effect(rate_limiter, func, *args, **kwargs):
        if "timelines.create" in str(func):
            return timeline_mock
        raise Exception("API delete error")

    with patch(
        "homeassistant.components.remember_the_milk.coordinator.run_async",
        side_effect=run_async_side_effect,
    ):
        with pytest.raises(UpdateFailed) as excinfo:
            await coordinator.async_delete_task("list1", "ts1", "task_id")
        assert "Error communicating with API: API delete error" in str(excinfo.value)


@pytest.mark.asyncio
async def test_async_get_tasks_success():
    """Return tasks successfully from the API."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="key",
            shared_secret="secret",
            token="token",
        )

    mock_tasks = MagicMock()
    mock_tasks.tasks.list = ["task1", "task2"]

    async def run_async_side_effect(rate_limiter, func, *args, **kwargs):
        return mock_tasks

    with patch(
        "homeassistant.components.remember_the_milk.coordinator.run_async",
        side_effect=run_async_side_effect,
    ):
        result = await coordinator.async_get_tasks("list1")
        assert result == ["task1", "task2"]


@pytest.mark.asyncio
async def test_async_get_tasks_failure():
    """Raise UpdateFailed if fetching tasks fails."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="key",
            shared_secret="secret",
            token="token",
        )

    async def run_async_side_effect(rate_limiter, func, *args, **kwargs):
        raise Exception("API error")

    with patch(
        "homeassistant.components.remember_the_milk.coordinator.run_async",
        side_effect=run_async_side_effect,
    ):
        with pytest.raises(UpdateFailed) as excinfo:
            await coordinator.async_get_tasks("list1")
        assert "Error communicating with API: API error" in str(excinfo.value)


@pytest.mark.asyncio
async def test_async_update_task_generic_exception():
    """Raise UpdateFailed on a generic exception during task update."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="test_api_key",
            shared_secret="test_shared_secret",
            token="test_token",
        )

    existing_task = MagicMock()
    existing_task.id = "ts_existing"
    existing_task.name = "Task"
    existing_task.task.completed = False
    existing_task.task.due = "2025-01-01T12:00:00Z"

    coordinator.data = [
        type(
            "MockList",
            (object,),
            {"id": "list1", "__iter__": lambda self: iter([existing_task])},
        )()
    ]

    coordinator._check_duplicate_lists = AsyncMock(return_value=[])

    with patch(
        "homeassistant.components.remember_the_milk.coordinator.run_async",
        new_callable=AsyncMock,
    ) as mock_run_async:

        async def run_async_side_effect(rate, func, *args, **kwargs):
            if "timelines.create" in str(func):
                timeline_mock = MagicMock()
                timeline_mock.timeline.value = "fake_timeline"
                return timeline_mock
            raise Exception("Generic API error")

        mock_run_async.side_effect = run_async_side_effect

        with pytest.raises(UpdateFailed) as excinfo:
            await coordinator.async_update_task(
                list_id="list1",
                name="Task",
                taskseries_id="ts_existing",
                task_id="task_id",
                due="2025-01-02T12:00:00Z",
                has_due_time="1",
                status=TodoItemStatus.NEEDS_ACTION,
            )

        assert "Error communicating with API: Generic API error" in str(excinfo.value)


@pytest.mark.asyncio
async def test_async_get_task_lists_failure():
    """Raise UpdateFailed if fetching task lists fails."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="key",
            shared_secret="secret",
            token="token",
        )

    async def run_async_side_effect(rate_limiter, func, *args, **kwargs):
        raise Exception("Generic API error for get_task_lists")

    with patch(
        "homeassistant.components.remember_the_milk.coordinator.run_async",
        side_effect=run_async_side_effect,
    ):
        with pytest.raises(UpdateFailed) as excinfo:
            await coordinator.async_get_task_lists()
        assert (
            "Error communicating with API: Generic API error for get_task_lists"
            in str(excinfo.value)
        )


@pytest.mark.asyncio
async def test_async_create_task_api_failure():
    """Raise UpdateFailed if creating task fails due to API error."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="test_api_key",
            shared_secret="test_shared_secret",
            token="test_token",
        )

    timeline_mock = MagicMock()
    timeline_mock.timeline.value = "fake_timeline"

    async def run_async_side_effect(rate, func, *args, **kwargs):
        if "timelines.create" in str(func):
            return timeline_mock
        raise Exception("API error on tasks.add")

    with patch(
        "homeassistant.components.remember_the_milk.coordinator.run_async",
        side_effect=run_async_side_effect,
    ):
        with pytest.raises(UpdateFailed) as excinfo:
            await coordinator.async_create_task(
                list_id="list1",
                task_name="New Task",
                due="2024-12-31T23:59:59Z",
                description="A test task",
            )
        assert "Error communicating with API: API error on tasks.add" in str(
            excinfo.value
        )


@pytest.mark.asyncio
async def test_async_create_task_duplicate_lists():
    """Raise ValueError if creating a task makes lists identical."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock(time_zone="UTC")

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="test_api_key",
            shared_secret="test_shared_secret",
            token="test_token",
        )

    coordinator._check_duplicate_task = AsyncMock(return_value="")
    coordinator._check_duplicate_lists = AsyncMock(return_value=["Duplicate List"])

    timeline_mock = MagicMock()
    timeline_mock.timeline.value = "fake_timeline"

    async def run_async_side_effect(*args, **kwargs):
        if "timelines.create" in str(args[1]) or (
            callable(args[1]) and "timelines.create" in str(args[1])
        ):
            return timeline_mock
        return MagicMock()

    with patch(
        "homeassistant.components.remember_the_milk.coordinator.run_async",
        side_effect=run_async_side_effect,
    ):
        with pytest.raises(ValueError) as excinfo:
            await coordinator.async_create_task(
                list_id="list1",
                task_name="New Task",
                due="2024-12-31T23:59:59Z",
                description="Test description",
            )
        assert "Tasks will be same" in str(excinfo.value)


@pytest.mark.asyncio
async def test_async_update_task_make_changes():
    """Call run_async to update the task when changes are made in async_update_task."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock(time_zone="UTC")

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="test_api_key",
            shared_secret="test_shared_secret",
            token="test_token",
        )

    existing_task = MagicMock()
    existing_task.id = "ts_existing"
    existing_task.name = "Old Name"
    existing_task.task.completed = False
    existing_task.task.due = "2025-01-01T12:00:00Z"

    coordinator.data = [
        type(
            "MockList",
            (object,),
            {"id": "list1", "__iter__": lambda self: iter([existing_task])},
        )()
    ]

    coordinator._check_duplicate_lists = AsyncMock(return_value=[])

    timeline_mock = MagicMock()
    timeline_mock.timeline.value = "fake_timeline"

    async def run_async_side_effect(*args, **kwargs):
        if "timelines.create" in str(args[1]) or (
            callable(args[1]) and "timelines.create" in str(args[1])
        ):
            return timeline_mock
        if "tasks.setDueDate" in str(args[1]):
            return MagicMock()

    with patch(
        "homeassistant.components.remember_the_milk.coordinator.run_async",
        side_effect=run_async_side_effect,
    ):
        await coordinator.async_update_task(
            list_id="list1",
            name="Old Name",
            taskseries_id="ts_existing",
            task_id="task_id",
            due="2025-01-02T12:00:00Z",
            has_due_time="1",
            status=TodoItemStatus.NEEDS_ACTION,
        )


@pytest.mark.asyncio
async def test_async_update_task_duplicate_task_name():
    """Raise ValueError if the updated task name already exists."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock(time_zone="UTC")

    with (
        patch("homeassistant.components.remember_the_milk.coordinator.Rtm"),
        patch("homeassistant.components.remember_the_milk.coordinator.RateLimiter"),
    ):
        coordinator = RememberTheMilkCoordinator(
            hass=hass,
            logger=MagicMock(),
            api_key="test_api_key",
            shared_secret="test_shared_secret",
            token="test_token",
        )

    old_task = MagicMock()
    old_task.id = "ts_existing"
    old_task.name = "Original Task"
    old_task.task.completed = False
    old_task.task.due = "2025-01-01T12:00:00Z"

    duplicate_task = MagicMock()
    duplicate_task.id = "ts_duplicate"
    duplicate_task.name = "Duplicate Name"
    duplicate_task.task.completed = False
    duplicate_task.task.due = "2025-01-02T12:00:00Z"

    coordinator.data = [
        type(
            "MockList",
            (object,),
            {"id": "list1", "__iter__": lambda self: iter([old_task, duplicate_task])},
        )()
    ]

    coordinator._check_duplicate_lists = AsyncMock(return_value=[])

    coordinator.async_get_tasks = AsyncMock(return_value=[old_task, duplicate_task])
    coordinator._check_duplicate_task = AsyncMock(return_value="Duplicate Name")

    timeline_mock = MagicMock()
    timeline_mock.timeline.value = "fake_timeline"

    async def run_async_side_effect(*args, **kwargs):
        if "timelines.create" in str(args[1]) or (
            callable(args[1]) and "timelines.create" in str(args[1])
        ):
            return timeline_mock
        return MagicMock()

    with patch(
        "homeassistant.components.remember_the_milk.coordinator.run_async",
        side_effect=run_async_side_effect,
    ):
        with pytest.raises(ValueError) as excinfo:
            await coordinator.async_update_task(
                list_id="list1",
                name="Duplicate Name",
                taskseries_id="ts_existing",
                task_id="task_id",
                due="2025-01-01T12:00:00Z",
                has_due_time="1",
                status=TodoItemStatus.NEEDS_ACTION,
            )
        assert "already exists in this list" in str(excinfo.value)
