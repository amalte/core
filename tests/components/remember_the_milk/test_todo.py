from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, ANY

import pytest

from homeassistant.components.todo import TodoItem, TodoItemStatus
from homeassistant.components.remember_the_milk.todo import (
    RememberTheMilkTodoListEntity,
    async_setup_platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity


def test_initialization(todo_entity):
    """Test initialization of RememberTheMilkTodoListEntity."""
    assert todo_entity.account_name == "test_account"
    assert todo_entity.list_id == "test_list_id"


@pytest.mark.asyncio
async def test_async_setup_platform_no_discovery_info():
    """Test setup platform with no discovery info."""
    async_add_entities = AsyncMock()
    hass = MagicMock()

    await async_setup_platform(hass, None, async_add_entities, discovery_info=None)

    async_add_entities.assert_not_called()


@pytest.mark.asyncio
async def test_async_setup_platform_no_account_name(caplog):
    """Test setup platform with no account name in discovery info."""
    async_add_entities = AsyncMock()
    hass = MagicMock()

    await async_setup_platform(
        hass,
        None,
        async_add_entities,
        discovery_info={},
    )

    assert "No account name found in discovery_info" in caplog.text
    async_add_entities.assert_not_called()


@pytest.mark.asyncio
async def test_async_setup_platform_valid_setup():
    """Test setup platform with valid setup."""
    async_add_entities = AsyncMock()
    hass = MagicMock()
    mock_coordinator = AsyncMock()
    hass.data = {
        "remember_the_milk": {
            "test_account": mock_coordinator,
        }
    }

    mock_task_list_1 = MagicMock(id="list1", name="List 1")
    mock_task_list_2 = MagicMock(id="list2", name="List 2")
    mock_coordinator.async_get_task_lists.return_value = [
        mock_task_list_1,
        mock_task_list_2,
    ]

    with patch(
        "homeassistant.components.remember_the_milk.todo.RememberTheMilkTodoListEntity"
    ) as mock_entity:
        mock_entity.side_effect = (
            lambda coordinator, account_name, list_id, list_name: f"Entity({list_id})"
        )

        await async_setup_platform(
            hass,
            None,
            async_add_entities,
            discovery_info={"account_name": "test_account"},
        )

        mock_coordinator.async_get_task_lists.assert_called_once()
        async_add_entities.assert_called_once_with(
            ["Entity(list1)", "Entity(list2)"], True
        )


@pytest.mark.asyncio
async def test_async_setup_platform_no_coordinator(caplog):
    """Test setup platform with no coordinator found."""
    async_add_entities = AsyncMock()
    hass = MagicMock()
    hass.data = {"remember_the_milk": {}}

    await async_setup_platform(
        hass,
        None,
        async_add_entities,
        discovery_info={"account_name": "test_account"},
    )

    assert "No coordinator found for account test_account" in caplog.text
    async_add_entities.assert_not_called()


@pytest.fixture
def coordinator_mock():
    """Fixture to create a mock RememberTheMilkCoordinator."""
    mock_coordinator = AsyncMock()
    mock_coordinator.data = None  # Default to no data
    return mock_coordinator


@pytest.fixture
def todo_entity(coordinator_mock):
    """Fixture to create a RememberTheMilkTodoListEntity instance."""
    return RememberTheMilkTodoListEntity(
        coordinator=coordinator_mock,
        account_name="test_account",
        list_id="test_list_id",
        list_name="Test List",
    )


@pytest.mark.asyncio
async def test_todo_items_empty(todo_entity):
    """Test todo_items when there is no data."""
    assert todo_entity.todo_items == []


@pytest.mark.asyncio
async def test_todo_items_with_data(todo_entity, coordinator_mock):
    """Test todo_items with valid data."""
    mock_task = MagicMock()
    mock_task.id = "task1"
    mock_task.completed = False
    mock_task.due = datetime.now()
    mock_task.added = datetime.now() - timedelta(days=1)

    # Mocking the expected structure of taskseries.notes
    mock_note = MagicMock()
    mock_note.value = "Description"

    mock_taskseries = MagicMock()
    mock_taskseries.id = "series1"
    mock_taskseries.name = "Task Name"
    mock_taskseries.task = mock_task
    mock_taskseries.notes = mock_note  # Each note directly has a `value`

    mock_task_list = MagicMock()
    mock_task_list.id = "test_list_id"
    mock_task_list.__iter__.return_value = [mock_taskseries]

    coordinator_mock.data = [mock_task_list]

    todo_items = todo_entity.todo_items
    assert len(todo_items) == 1
    assert todo_items[0].summary == "Task Name"
    assert todo_items[0].description == ""
    assert todo_items[0].status == TodoItemStatus.NEEDS_ACTION


@pytest.mark.asyncio
async def test_async_create_todo_item(todo_entity, coordinator_mock):
    """Test creating a todo item."""
    todo_item = TodoItem(
        summary="New Task",
        uid="",
        status=TodoItemStatus.NEEDS_ACTION,
        due=datetime.now(),
        description="Task Description",
    )

    coordinator_mock.async_create_task = AsyncMock()
    coordinator_mock.async_refresh = AsyncMock()

    await todo_entity.async_create_todo_item(todo_item)

    coordinator_mock.async_create_task.assert_called_once_with(
        "test_list_id", "New Task", todo_item.due, "Task Description"
    )
    coordinator_mock.async_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_async_delete_todo_items(todo_entity, coordinator_mock):
    """Test deleting todo items."""
    coordinator_mock.async_delete_task = AsyncMock()
    coordinator_mock.async_refresh = AsyncMock()

    uids = ["series1_task1", "series2_task2"]

    await todo_entity.async_delete_todo_items(uids)

    coordinator_mock.async_delete_task.assert_any_call(
        "test_list_id", "series1", "task1"
    )
    coordinator_mock.async_delete_task.assert_any_call(
        "test_list_id", "series2", "task2"
    )
    coordinator_mock.async_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_async_update_todo_item(todo_entity, coordinator_mock):
    """Test updating a todo item."""
    todo_item = TodoItem(
        summary="Updated Task",
        uid="series1_task1",
        status=TodoItemStatus.COMPLETED,
        due=datetime.now(),
        description="Updated Description",
    )

    coordinator_mock.async_update_task = AsyncMock()
    coordinator_mock.async_refresh = AsyncMock()

    await todo_entity.async_update_todo_item(todo_item)

    coordinator_mock.async_update_task.assert_called_once()
    coordinator_mock.async_refresh.assert_called_once()
