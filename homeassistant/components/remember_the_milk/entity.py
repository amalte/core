"""Support to interact with Remember The Milk."""

import logging

from rtmapi import Rtm, RtmRequestFailedException

from homeassistant.const import CONF_ID, CONF_NAME, STATE_OK
from homeassistant.core import ServiceCall
from homeassistant.helpers.entity import Entity

# Initialize the logger for this module
_LOGGER = logging.getLogger(__name__)


class RememberTheMilkEntity(Entity):
    """Representation of an interface to Remember The Milk."""

    def __init__(self, name, api_key, shared_secret, token, rtm_config):
        """Create a new instance of the Remember The Milk entity.

        Args:
            name (str): The name of the Remember The Milk account.
            api_key (str): The API key for the RTM account.
            shared_secret (str): The shared secret for the RTM API.
            token (str): The authentication token for the RTM account.
            rtm_config (RememberTheMilkConfiguration): Configuration handler for RTM.

        """
        self._name = name
        self._api_key = api_key
        self._shared_secret = shared_secret
        self._token = token
        self._rtm_config = rtm_config
        # Initialize the RTM API client with the provided credentials
        self._rtm_api = Rtm(api_key, shared_secret, "delete", token)
        # Variable to track the validity of the token
        self._token_valid = None
        # Check if the token is valid upon initialization
        self._check_token()
        _LOGGER.debug("Instance created for account %s", self._name)

    def _check_token(self):
        """Check if the API token is still valid.

        If the token is invalid, remove it from the configuration to trigger
        a new authentication process.

        Returns:
            bool: True if the token is valid, False otherwise.

        """
        # Validate the token using the RTM API client
        valid = self._rtm_api.token_valid()
        if not valid:
            # Log an error and remove the invalid token from the configuration
            _LOGGER.error(
                "Token for account %s is invalid. You need to register again!",
                self.name,
            )
            self._rtm_config.delete_token(self._name)
            self._token_valid = False
        else:
            self._token_valid = True
        return self._token_valid

    def create_task(self, call: ServiceCall) -> None:
        """Create a new task on Remember The Milk.

        This service allows users to create a new task with optional tags and due dates
        using smart syntax (e.g., "my task #some_tag ^today").

        Args:
            call (ServiceCall): The service call containing the task details.

        """
        try:
            # Extract the task name from the service call data
            task_name = call.data[CONF_NAME]
            # Optionally extract the Home Assistant task ID if provided
            hass_id = call.data.get(CONF_ID)
            rtm_id = None
            if hass_id is not None:
                # Retrieve the corresponding RTM task IDs from the configuration
                rtm_id = self._rtm_config.get_rtm_id(self._name, hass_id)
            # Create a new timeline entry for the task
            result = self._rtm_api.rtm.timelines.create()
            timeline = result.timeline.value

            if hass_id is None or rtm_id is None:
                # If no Home Assistant ID is provided or RTM ID is not found, add a new task
                result = self._rtm_api.rtm.tasks.add(
                    timeline=timeline, name=task_name, parse="1"
                )
                _LOGGER.debug(
                    "Created new task '%s' in account %s", task_name, self.name
                )
                # Store the mapping between Home Assistant ID and RTM task IDs
                self._rtm_config.set_rtm_id(
                    self._name,
                    hass_id,
                    result.list.id,
                    result.list.taskseries.id,
                    result.list.taskseries.task.id,
                )
            else:
                # If RTM IDs are found, update the existing task's name
                self._rtm_api.rtm.tasks.setName(
                    name=task_name,
                    list_id=rtm_id[0],
                    taskseries_id=rtm_id[1],
                    task_id=rtm_id[2],
                    timeline=timeline,
                )
                _LOGGER.debug(
                    "Updated task with id '%s' in account %s to name %s",
                    hass_id,
                    self.name,
                    task_name,
                )
        except RtmRequestFailedException as rtm_exception:
            # Log any exceptions that occur during the task creation process
            _LOGGER.error(
                "Error creating new Remember The Milk task for account %s: %s",
                self._name,
                rtm_exception,
            )

    def complete_task(self, call: ServiceCall) -> None:
        """Complete a task that was previously created by this component.

        This service marks a specified task as completed in Remember The Milk.

        Args:
            call (ServiceCall): The service call containing the task ID to complete.

        """
        # Extract the Home Assistant task ID from the service call data
        hass_id = call.data[CONF_ID]
        # Retrieve the corresponding RTM task IDs from the configuration
        rtm_id = self._rtm_config.get_rtm_id(self._name, hass_id)
        if rtm_id is None:
            # Log an error if the RTM task IDs are not found
            _LOGGER.error(
                (
                    "Could not find task with ID %s in account %s. "
                    "So task could not be closed"
                ),
                hass_id,
                self._name,
            )
            return
        try:
            # Create a new timeline entry for completing the task
            result = self._rtm_api.rtm.timelines.create()
            timeline = result.timeline.value
            # Mark the task as complete using the RTM API
            self._rtm_api.rtm.tasks.complete(
                list_id=rtm_id[0],
                taskseries_id=rtm_id[1],
                task_id=rtm_id[2],
                timeline=timeline,
            )
            # Remove the task ID mapping from the configuration as it's completed
            self._rtm_config.delete_rtm_id(self._name, hass_id)
            _LOGGER.debug(
                "Completed task with id %s in account %s", hass_id, self._name
            )
        except RtmRequestFailedException as rtm_exception:
            # Log any exceptions that occur during the task completion process
            _LOGGER.error(
                "Error completing task with ID %s for account %s: %s",
                hass_id,
                self._name,
                rtm_exception,
            )

    @property
    def name(self):
        """Return the name of the device.

        This property provides the name of the Remember The Milk account associated
        with this entity.

        Returns:
            str: The name of the account.

        """
        return self._name

    @property
    def state(self):
        """Return the state of the device.

        The state reflects whether the API token is valid. If the token is invalid,
        the state indicates an issue; otherwise, it shows as OK.

        Returns:
            str: The state of the entity ("API token invalid" or STATE_OK).

        """
        if not self._token_valid:
            return "API token invalid"
        return STATE_OK
