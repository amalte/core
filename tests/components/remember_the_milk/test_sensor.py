"""Tests for the Remember The Milk sensor platform."""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from homeassistant.components.remember_the_milk.sensor import (
    SERVICE_RTM_METHOD,
    SERVICE_UPDATE_TASK_LIST,
    RememberTheMilkSensor,
    async_setup_platform,
)
from homeassistant.core import HomeAssistant

# Define constants for testing
DOMAIN = "remember_the_milk"
TEST_ACCOUNT_NAME = "TestAccount"
TEST_LIST_ID = "test_list_id"
JSON_PAYLOAD = json.dumps({"key": "value"})


@pytest.fixture
def mock_coordinator():
    """Fixture to mock RememberTheMilkCoordinator."""
    coordinator = Mock()
    coordinator.async_get_task_lists = AsyncMock()
    coordinator.get_statistics = Mock(return_value={"completed": 1, "pending": 2})
    coordinator.async_run_rtm_method = AsyncMock()
    coordinator.async_refresh = AsyncMock()
    return coordinator


@pytest.fixture
def mock_add_entities():
    """Fixture to mock async_add_entities callback."""
    return Mock()


def mock_notes(value: str) -> MagicMock:
    """Helper function to mock the notes attribute."""
    notes_mock = MagicMock()
    notes_mock.__len__.return_value = 1
    notes_mock.__iter__.return_value = iter([MagicMock(note=MagicMock(value=value))])
    notes_mock.note = MagicMock(value=value)
    return notes_mock


@pytest.fixture
async def setup_platform_fixture(
    hass: HomeAssistant, mock_coordinator, mock_add_entities
):
    """Set up the sensor platform for testing."""
    with patch(
        "homeassistant.components.remember_the_milk.sensor.RememberTheMilkCoordinator",
        return_value=mock_coordinator,
    ):
        # Initialize hass.data[DOMAIN] with the account_name and mock_coordinator
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][TEST_ACCOUNT_NAME] = mock_coordinator

        # Define TEST_TASK_LIST as iterable
        TEST_TASK_LIST = MagicMock(id=TEST_LIST_ID)
        TEST_TASK_LIST.name = "Test List"  # Set name as string

        # Define TEST_TASKSERIES with correct mocking
        TEST_TASKSERIES = Mock(
            id="taskseries1",
            name="Test Task",  # Set name directly as string
            task=Mock(
                id="task1",
                completed=False,
                due="2024-12-31",
                added="2024-01-01",
            ),
            notes=mock_notes("Test Description"),  # Use helper function
        )
        # Assign the 'note' attribute with a 'value'

        TEST_TASK_LIST.__iter__.return_value = iter([TEST_TASKSERIES])

        # Set the coordinator's data to include the TEST_TASK_LIST
        mock_coordinator.async_get_task_lists.return_value = [TEST_TASK_LIST]
        mock_coordinator.data = [TEST_TASK_LIST]

        discovery_info = {"account_name": TEST_ACCOUNT_NAME}
        await async_setup_platform(
            hass,
            {},
            mock_add_entities,
            discovery_info,
        )
        await hass.async_block_till_done()


async def test_async_setup_platform(
    hass: HomeAssistant, mock_coordinator, mock_add_entities
):
    """Test that the platform sets up correctly and adds a sensor entity."""
    with (
        patch(
            "homeassistant.components.remember_the_milk.sensor.RememberTheMilkCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.remember_the_milk.sensor.RememberTheMilkSensor",
            autospec=True,  # Ensure methods are preserved
        ) as mock_sensor_class,
    ):
        # Initialize hass.data[DOMAIN]
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][TEST_ACCOUNT_NAME] = mock_coordinator

        discovery_info = {"account_name": TEST_ACCOUNT_NAME}

        await async_setup_platform(
            hass,
            {},
            mock_add_entities,
            discovery_info,
        )

        # Check that the sensor entity was added
        mock_sensor_class.assert_called_once_with(mock_coordinator)
        sensor_instance = mock_sensor_class.return_value
        sensor_instance.hass = hass  # Ensure hass is set on the sensor
        sensor_instance.entity_id = "sensor.remember_the_milk_test"  # Assign entity_id

        mock_add_entities.assert_called_once_with([sensor_instance], True)

        # Check that services are registered
        assert hass.services.has_service("remember_the_milk", SERVICE_UPDATE_TASK_LIST)
        assert hass.services.has_service("remember_the_milk", SERVICE_RTM_METHOD)


async def test_handle_update_task_list_service(
    hass: HomeAssistant, mock_coordinator, mock_add_entities
):
    """Test the 'update_task_list' service call."""
    with (
        patch(
            "homeassistant.components.remember_the_milk.sensor.RememberTheMilkCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.remember_the_milk.sensor.RememberTheMilkSensor",
            autospec=True,  # Ensure methods are preserved
        ) as mock_sensor_class,
    ):
        # Initialize hass.data[DOMAIN]
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][TEST_ACCOUNT_NAME] = mock_coordinator

        # Define TEST_TASK_LIST as iterable
        TEST_TASK_LIST = MagicMock(id=TEST_LIST_ID)
        TEST_TASK_LIST.name = "Test List"  # Set name as string

        # Define TEST_TASKSERIES with correct mocking
        TEST_TASKSERIES = Mock(
            id="taskseries1",
            name="Test Task",  # Set name directly as string
            task=Mock(
                id="task1",
                completed=False,
                due="2024-12-31",
                added="2024-01-01",
            ),
            notes=mock_notes("Test Description"),  # Use helper function
        )

        TEST_TASK_LIST.__iter__.return_value = iter([TEST_TASKSERIES])

        # Set the coordinator's data to include the TEST_TASK_LIST
        mock_coordinator.async_get_task_lists.return_value = [TEST_TASK_LIST]
        mock_coordinator.data = [TEST_TASK_LIST]

        discovery_info = {"account_name": TEST_ACCOUNT_NAME}
        await async_setup_platform(
            hass,
            {},
            mock_add_entities,
            discovery_info,
        )

        # Get the sensor instance
        sensor_instance = mock_sensor_class.return_value
        sensor_instance.hass = hass  # Ensure hass is set on the sensor
        sensor_instance.entity_id = "sensor.remember_the_milk_test"  # Assign entity_id

        # Call the service
        await hass.services.async_call(
            "remember_the_milk",
            SERVICE_UPDATE_TASK_LIST,
            {"list_id": TEST_LIST_ID},
            blocking=True,
        )

        # Verify that update_state was called with the correct list_id
        sensor_instance.update_state.assert_called_once_with(TEST_LIST_ID)


async def test_handle_rtm_method_service(
    hass: HomeAssistant, mock_coordinator, mock_add_entities
):
    """Test the 'rtm_method' service call."""
    with (
        patch(
            "homeassistant.components.remember_the_milk.sensor.RememberTheMilkCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.remember_the_milk.sensor.RememberTheMilkSensor",
            autospec=True,  # Ensure methods are preserved
        ) as mock_sensor_class,
    ):
        # Initialize hass.data[DOMAIN]
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][TEST_ACCOUNT_NAME] = mock_coordinator

        # Define TEST_TASK_LIST as iterable
        TEST_TASK_LIST = MagicMock(id=TEST_LIST_ID)
        TEST_TASK_LIST.name = "Test List"  # Set name as string

        # Define TEST_TASKSERIES with correct mocking
        TEST_TASKSERIES = Mock(
            id="taskseries1",
            name="Test Task",  # Set name directly as string
            task=Mock(
                id="task1",
                completed=False,
                due="2024-12-31",
                added="2024-01-01",
            ),
            notes=mock_notes("Test Description"),  # Use helper function
        )

        TEST_TASK_LIST.__iter__.return_value = iter([TEST_TASKSERIES])

        # Set the coordinator's data to include the TEST_TASK_LIST
        mock_coordinator.async_get_task_lists.return_value = [TEST_TASK_LIST]
        mock_coordinator.data = [TEST_TASK_LIST]

        discovery_info = {"account_name": TEST_ACCOUNT_NAME}
        await async_setup_platform(
            hass,
            {},
            mock_add_entities,
            discovery_info,
        )

        # Get the sensor instance
        sensor_instance = mock_sensor_class.return_value
        sensor_instance.hass = hass  # Ensure hass is set on the sensor
        sensor_instance.entity_id = "sensor.remember_the_milk_test"  # Assign entity_id

        # Call the service with refresh=True
        await hass.services.async_call(
            "remember_the_milk",
            SERVICE_RTM_METHOD,
            {
                "method": "test_method",
                "payload": JSON_PAYLOAD,
                "refresh": True,
            },
            blocking=True,
        )

        # Verify that async_run_rtm_method was called with correct arguments
        mock_coordinator.async_run_rtm_method.assert_awaited_with(
            "test_method", {"key": "value"}
        )

        # Verify that async_refresh was called
        mock_coordinator.async_refresh.assert_awaited()

        # Reset mocks for next service call
        mock_coordinator.async_run_rtm_method.reset_mock()
        mock_coordinator.async_refresh.reset_mock()

        # Call the service with refresh=False
        await hass.services.async_call(
            "remember_the_milk",
            SERVICE_RTM_METHOD,
            {
                "method": "test_method_2",
                "payload": JSON_PAYLOAD,
                "refresh": False,
            },
            blocking=True,
        )

        # Verify that async_run_rtm_method was called again with new arguments
        mock_coordinator.async_run_rtm_method.assert_awaited_with(
            "test_method_2", {"key": "value"}
        )

        # Verify that async_refresh was not called again
        mock_coordinator.async_refresh.assert_not_awaited()


async def test_remember_the_milk_sensor_async_update_missing_task_list(
    hass: HomeAssistant, mock_coordinator, mock_add_entities
):
    """Test async_update when the task_list_id is missing from coordinator data."""
    # Define a different task list
    non_existent_task_list = MagicMock(id="another_list_id")
    non_existent_task_list.name = "Non Existent List"  # Set name as string

    # Define non-existent task series
    non_existent_taskseries = Mock(
        id="taskseries3",
        name="Non Existent Task",  # Set name directly as string
        task=Mock(
            id="task3",
            completed=False,
            due="2024-10-10",
            added="2024-03-01",
        ),
        notes=mock_notes("Non Existent Description"),  # Use helper function
    )

    non_existent_task_list.__iter__.return_value = iter([non_existent_taskseries])

    # Set the coordinator's data to include only the non-existent task list
    mock_coordinator.async_get_task_lists.return_value = [non_existent_task_list]
    mock_coordinator.data = [non_existent_task_list]

    # Instantiate the sensor
    sensor = RememberTheMilkSensor(mock_coordinator)
    sensor.hass = hass  # Set the hass attribute
    sensor.entity_id = "sensor.remember_the_milk_test"  # Assign entity_id

    # Update state with a non-existent list ID
    sensor.update_state("non_existent_list_id")  # List ID not in coordinator.data
    await hass.async_block_till_done()  # Allow scheduled updates to run

    # Run async_update
    await sensor.async_update()

    # Since the list_id is not present, state should default to the first available list
    assert sensor.state == "another_list_id"
    assert sensor.extra_state_attributes["task_lists"] == [
        {"id": "another_list_id", "name": "Non Existent List"}
    ]
    assert sensor.extra_state_attributes["items"] == []
    assert sensor.extra_state_attributes["statistics"] == {"completed": 1, "pending": 2}


@pytest.mark.asyncio
async def test_no_account_name_in_discovery_info(
    hass: HomeAssistant, mock_add_entities
):
    """Test that async_setup_platform logs an error and returns if no account name is provided."""
    with patch(
        "homeassistant.components.remember_the_milk.sensor._LOGGER"
    ) as mock_logger:
        # No 'account_name' in discovery_info
        discovery_info = {}
        await async_setup_platform(hass, {}, mock_add_entities, discovery_info)

        # Verify that the error message was logged
        mock_logger.error.assert_any_call("No account name found in discovery_info")
        # No entities should be added
        mock_add_entities.assert_not_called()


@pytest.mark.asyncio
async def test_no_coordinator_found_for_account(hass: HomeAssistant, mock_add_entities):
    """Test that async_setup_platform logs an error and returns if no coordinator is found."""
    # Set up hass.data[DOMAIN] but no coordinator for the given account_name
    hass.data.setdefault(DOMAIN, {})
    # Provide a discovery_info with an account_name that doesn't exist
    discovery_info = {"account_name": "NonExistentAccount"}

    with patch(
        "homeassistant.components.remember_the_milk.sensor._LOGGER"
    ) as mock_logger:
        await async_setup_platform(hass, {}, mock_add_entities, discovery_info)

        # Verify that the error message was logged
        mock_logger.error.assert_any_call(
            "No coordinator found for account %s", "NonExistentAccount"
        )
        # No entities should be added
        mock_add_entities.assert_not_called()


@pytest.mark.asyncio
async def test_service_update_task_list_missing_list_id(
    hass: HomeAssistant, mock_coordinator, mock_add_entities
):
    """Test calling the update_task_list service with empty list_id to trigger the error log."""
    hass.data.setdefault(DOMAIN, {TEST_ACCOUNT_NAME: mock_coordinator})
    discovery_info = {"account_name": TEST_ACCOUNT_NAME}
    await async_setup_platform(hass, {}, mock_add_entities, discovery_info)

    with patch(
        "homeassistant.components.remember_the_milk.sensor._LOGGER"
    ) as mock_logger:
        # Call the SERVICE_UPDATE_TASK_LIST with an empty string for list_id
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_TASK_LIST,
            {"list_id": ""},  # empty string passes schema but triggers if not list_id:
            blocking=True,
        )

        mock_logger.error.assert_any_call("Service call missing 'list_id' parameter")


@pytest.mark.asyncio
async def test_service_rtm_method_missing_parameters(
    hass: HomeAssistant, mock_coordinator, mock_add_entities
):
    """Test calling the rtm_method service with empty method or payload to trigger the error log."""
    hass.data.setdefault(DOMAIN, {TEST_ACCOUNT_NAME: mock_coordinator})
    discovery_info = {"account_name": TEST_ACCOUNT_NAME}
    await async_setup_platform(hass, {}, mock_add_entities, discovery_info)

    with patch(
        "homeassistant.components.remember_the_milk.sensor._LOGGER"
    ) as mock_logger:
        # Call the SERVICE_RTM_METHOD with a method but empty payload
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RTM_METHOD,
            {
                "method": "some_method",
                "payload": "",  # empty string passes schema but fails if not payload:
            },
            blocking=True,
        )
        mock_logger.error.assert_any_call(
            "Service call missing 'method' or 'payload' parameter"
        )

    with patch(
        "homeassistant.components.remember_the_milk.sensor._LOGGER"
    ) as mock_logger:
        # Call the SERVICE_RTM_METHOD with a payload but empty method
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RTM_METHOD,
            {
                "method": "",  # empty string
                "payload": JSON_PAYLOAD,
            },
            blocking=True,
        )
        mock_logger.error.assert_any_call(
            "Service call missing 'method' or 'payload' parameter"
        )
