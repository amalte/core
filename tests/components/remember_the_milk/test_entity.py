# tests/components/remember_the_milk/test_entity.py

"""Tests for the Remember The Milk Entity."""

import logging
from unittest.mock import Mock, patch

import pytest
from rtmapi import RtmRequestFailedException

from homeassistant.components.remember_the_milk.entity import RememberTheMilkEntity
from homeassistant.core import HomeAssistant, ServiceCall

# Constants (assuming TEST_LIST_ID is defined elsewhere)
TEST_LIST_ID = "test_list_id"


@pytest.fixture
def mock_hass():
    """Fixture to create a mock HomeAssistant instance with necessary attributes."""
    hass = Mock(spec=HomeAssistant)
    hass.services = Mock()
    return hass


@pytest.fixture
def mock_rtm_config():
    """Fixture to create a mock RtmConfig instance."""
    rtm_config = Mock()
    rtm_config.get_rtm_id.return_value = None
    rtm_config.set_rtm_id.return_value = None
    rtm_config.delete_rtm_id.return_value = None
    rtm_config.delete_token.return_value = None
    return rtm_config


@pytest.fixture
def mock_rtm_api():
    """Fixture to create a mock Rtm API instance."""
    rtm_api = Mock()
    rtm_api.token_valid.return_value = True

    # Mock the rtm.timelines.create() method
    rtm_api.rtm.timelines.create.return_value = Mock(timeline=Mock(value="timeline_id"))

    # Mock the rtm.tasks.add() method
    rtm_api.rtm.tasks.add.return_value = Mock(
        list=Mock(
            id="list_id", taskseries=Mock(id="taskseries_id", task=Mock(id="task_id"))
        )
    )

    # Mock the rtm.tasks.setName() method
    rtm_api.rtm.tasks.setName.return_value = None

    # Mock the rtm.tasks.complete() method
    rtm_api.rtm.tasks.complete.return_value = None

    return rtm_api


@pytest.fixture
def entity(mock_hass, mock_rtm_config, mock_rtm_api):
    """Fixture to create an instance of RememberTheMilkEntity."""
    name = "Test Account"
    api_key = "test_api_key"
    shared_secret = "test_shared_secret"
    token = "test_token"
    rtm_config = mock_rtm_config

    with patch(
        "homeassistant.components.remember_the_milk.entity.Rtm",
        return_value=mock_rtm_api,
    ):
        entity = RememberTheMilkEntity(name, api_key, shared_secret, token, rtm_config)
    return entity


def create_service_call(service, data):
    """Helper function to create a mock ServiceCall."""
    service_call = Mock(spec=ServiceCall)
    service_call.data = data
    return service_call


def test_entity_initialization_token_valid(entity, mock_rtm_api, mock_rtm_config):
    """Test initialization when the token is valid."""
    assert entity._token_valid is True
    mock_rtm_api.token_valid.assert_called_once()
    mock_rtm_config.delete_token.assert_not_called()


def test_entity_initialization_token_invalid(mock_hass, mock_rtm_config, mock_rtm_api):
    """Test initialization when the token is invalid."""
    mock_rtm_api.token_valid.return_value = False

    name = "Invalid Token Account"
    api_key = "test_api_key"
    shared_secret = "test_shared_secret"
    token = "invalid_token"

    with patch(
        "homeassistant.components.remember_the_milk.entity.Rtm",
        return_value=mock_rtm_api,
    ):
        entity = RememberTheMilkEntity(
            name, api_key, shared_secret, token, mock_rtm_config
        )

    assert entity._token_valid is False
    mock_rtm_api.token_valid.assert_called_once()
    mock_rtm_config.delete_token.assert_called_once_with(name)


def test_create_task_success_new(entity, mock_rtm_api, mock_rtm_config, caplog):
    """Test creating a new task successfully when no existing RTM ID is present."""
    service_data = {"name": "New Task"}
    service_call = create_service_call("create_task", service_data)

    with caplog.at_level(logging.DEBUG):
        entity.create_task(service_call)

    # Verify that timelines.create() was called
    mock_rtm_api.rtm.timelines.create.assert_called_once()

    # Verify that tasks.add() was called with correct parameters
    mock_rtm_api.rtm.tasks.add.assert_called_once_with(
        timeline="timeline_id",
        name="New Task",
        parse="1",
    )

    # Verify that set_rtm_id was called to store the new task's RTM IDs
    mock_rtm_config.set_rtm_id.assert_called_once_with(
        entity._name,
        service_data.get("id"),
        "list_id",
        "taskseries_id",
        "task_id",
    )

    # Verify logging
    assert "Created new task 'New Task' in account Test Account" in caplog.text


def test_create_task_success_update(entity, mock_rtm_api, mock_rtm_config, caplog):
    """Test updating an existing task successfully when RTM ID is present."""
    # Setup existing RTM ID
    mock_rtm_config.get_rtm_id.return_value = ("list_id", "taskseries_id", "task_id")

    service_data = {"name": "Updated Task", "id": "hass_task_id"}
    service_call = create_service_call("create_task", service_data)

    with caplog.at_level(logging.DEBUG):
        entity.create_task(service_call)

    # Verify that timelines.create() was called
    mock_rtm_api.rtm.timelines.create.assert_called_once()

    # Verify that tasks.setName() was called with correct parameters
    mock_rtm_api.rtm.tasks.setName.assert_called_once_with(
        name="Updated Task",
        list_id="list_id",
        taskseries_id="taskseries_id",
        task_id="task_id",
        timeline="timeline_id",
    )

    # Verify that set_rtm_id was not called again since it's an update
    mock_rtm_config.set_rtm_id.assert_not_called()

    # Verify logging
    assert (
        "Updated task with id 'hass_task_id' in account Test Account to name Updated Task"
        in caplog.text
    )


def test_create_task_failure_rtm_exception(
    entity, mock_rtm_api, mock_rtm_config, caplog
):
    """Test creating a task when RtmRequestFailedException is raised."""
    # Instantiate the exception with three arguments
    mock_rtm_api.rtm.tasks.add.side_effect = RtmRequestFailedException(
        "GET", 500, "Internal Server Error"
    )

    service_data = {"name": "Task with API Error"}
    service_call = create_service_call("create_task", service_data)

    with caplog.at_level(logging.ERROR):
        entity.create_task(service_call)

    # Verify that error was logged with the correct message
    expected_log_message = (
        "Error creating new Remember The Milk task for account Test Account: "
        "Request GET failed. Status: 500, reason: Internal Server Error."
    )
    assert expected_log_message in caplog.text

    # Verify that set_rtm_id was not called due to failure
    mock_rtm_config.set_rtm_id.assert_not_called()


def test_complete_task_success(entity, mock_rtm_api, mock_rtm_config, caplog):
    """Test completing a task successfully."""
    # Setup existing RTM ID
    mock_rtm_config.get_rtm_id.return_value = ("list_id", "taskseries_id", "task_id")

    service_data = {"id": "hass_task_id"}
    service_call = create_service_call("complete_task", service_data)

    # Mock timelines.create() for completion
    mock_rtm_api.rtm.timelines.create.return_value = Mock(
        timeline=Mock(value="completion_timeline_id")
    )

    with caplog.at_level(logging.DEBUG):
        entity.complete_task(service_call)

    # Verify that timelines.create() was called
    mock_rtm_api.rtm.timelines.create.assert_called_once()

    # Verify that tasks.complete() was called with correct parameters
    mock_rtm_api.rtm.tasks.complete.assert_called_once_with(
        list_id="list_id",
        taskseries_id="taskseries_id",
        task_id="task_id",
        timeline="completion_timeline_id",
    )

    # Verify that delete_rtm_id was called to remove the completed task's RTM IDs
    mock_rtm_config.delete_rtm_id.assert_called_once_with(entity._name, "hass_task_id")

    # Verify logging
    assert "Completed task with id hass_task_id in account Test Account" in caplog.text


def test_complete_task_failure_nonexistent_task(
    entity, mock_rtm_api, mock_rtm_config, caplog
):
    """Test completing a task that does not exist."""
    # No RTM ID found
    mock_rtm_config.get_rtm_id.return_value = None

    service_data = {"id": "nonexistent_task_id"}
    service_call = create_service_call("complete_task", service_data)

    with caplog.at_level(logging.ERROR):
        entity.complete_task(service_call)

    # Verify that error was logged
    assert (
        "Could not find task with ID nonexistent_task_id in account Test Account. So task could not be closed"
        in caplog.text
    )

    # Verify that tasks.complete() was not called
    mock_rtm_api.rtm.tasks.complete.assert_not_called()

    # Verify that delete_rtm_id was not called
    mock_rtm_config.delete_rtm_id.assert_not_called()


def test_complete_task_failure_rtm_exception(
    entity, mock_rtm_api, mock_rtm_config, caplog
):
    """Test completing a task when RtmRequestFailedException is raised."""
    # Setup existing RTM ID
    mock_rtm_config.get_rtm_id.return_value = ("list_id", "taskseries_id", "task_id")

    # Instantiate the exception with three arguments
    mock_rtm_api.rtm.tasks.complete.side_effect = RtmRequestFailedException(
        "POST", 502, "Bad Gateway"
    )

    service_data = {"id": "hass_task_id"}
    service_call = create_service_call("complete_task", service_data)

    with caplog.at_level(logging.ERROR):
        entity.complete_task(service_call)

    # Verify that error was logged with the correct message
    expected_log_message = (
        "Error completing task with ID hass_task_id for account Test Account: "
        "Request POST failed. Status: 502, reason: Bad Gateway."
    )
    assert expected_log_message in caplog.text

    # Verify that delete_rtm_id was not called due to failure
    mock_rtm_config.delete_rtm_id.assert_not_called()


def test_entity_name_property(entity):
    """Test the name property of the entity."""
    assert entity.name == "Test Account"


def test_entity_state_property_token_valid(entity):
    """Test the state property when the token is valid."""
    assert entity.state == "ok"


def test_entity_state_property_token_invalid(mock_rtm_config, mock_rtm_api):
    """Test the state property when the token is invalid."""
    mock_rtm_api.token_valid.return_value = False
    name = "Invalid Token Account"
    api_key = "test_api_key"
    shared_secret = "test_shared_secret"
    token = "invalid_token"

    with patch(
        "homeassistant.components.remember_the_milk.entity.Rtm",
        return_value=mock_rtm_api,
    ):
        entity = RememberTheMilkEntity(
            name, api_key, shared_secret, token, mock_rtm_config
        )

    assert entity.state == "API token invalid"
