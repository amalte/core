"""Support to interact with Remember The Milk."""

import json
import logging
import os

from rtmapi import Rtm
import voluptuous as vol

from homeassistant.components import configurator
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_NAME, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .coordinator import RememberTheMilkCoordinator
from .entity import RememberTheMilkEntity

# httplib2 is a transitive dependency from RtmAPI. If this dependency is not
# set explicitly, the library does not work.
_LOGGER = logging.getLogger(__name__)

# Define the domain for the integration
DOMAIN = "remember_the_milk"
DEFAULT_NAME = DOMAIN

# Define the platforms that this integration supports
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.TODO]

# Define configuration constants
CONF_SHARED_SECRET = "shared_secret"
CONF_ID_MAP = "id_map"
CONF_LIST_ID = "list_id"
CONF_TIMESERIES_ID = "timeseries_id"
CONF_TASK_ID = "task_id"

# Define the schema for Remember The Milk configuration
RTM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_SHARED_SECRET): cv.string,
    }
)

# Define the overall configuration schema for the integration
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [RTM_SCHEMA])}, extra=vol.ALLOW_EXTRA
)

# Define the name of the configuration file
CONFIG_FILE_NAME = ".remember_the_milk.conf"

# Define service names
SERVICE_CREATE_TASK = "create_task"
SERVICE_COMPLETE_TASK = "complete_task"

# Define schemas for the create_task service
SERVICE_SCHEMA_CREATE_TASK = vol.Schema(
    {vol.Required(CONF_NAME): cv.string, vol.Optional(CONF_ID): cv.string}
)

# Define schemas for the complete_task service
SERVICE_SCHEMA_COMPLETE_TASK = vol.Schema({vol.Required(CONF_ID): cv.string})


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Remember the Milk component.

    This function initializes the Remember The Milk integration by setting up
    entity components, handling existing configurations, and registering services.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        config (ConfigType): The configuration dictionary.

    Returns:
        bool: True if setup was successful, False otherwise.

    """
    # Initialize the entity component for Remember The Milk entities
    component = EntityComponent[RememberTheMilkEntity](_LOGGER, DOMAIN, hass)

    # Load stored Remember The Milk configurations (e.g., tokens)
    stored_rtm_config = RememberTheMilkConfiguration(hass)

    # Iterate over each Remember The Milk configuration provided in the config
    for rtm_config in config[DOMAIN]:
        account_name = rtm_config[CONF_NAME]
        _LOGGER.debug("Adding Remember the milk account %s", account_name)
        api_key = rtm_config[CONF_API_KEY]
        shared_secret = rtm_config[CONF_SHARED_SECRET]
        token = stored_rtm_config.get_token(account_name)

        if token:
            # If a token exists for the account, create an instance immediately
            _LOGGER.debug("found token for account %s", account_name)
            _create_instance(
                hass,
                account_name,
                api_key,
                shared_secret,
                token,
                stored_rtm_config,
                component,
            )
        else:
            # If no token exists, initiate the registration process
            _register_new_account(
                hass, account_name, api_key, shared_secret, stored_rtm_config, component
            )

        # Initialize the coordinator for managing data updates
        coordinator = RememberTheMilkCoordinator(
            hass, _LOGGER, api_key, shared_secret, token
        )

        # Start the rate limiter asynchronously
        hass.create_task(coordinator.rate_limiter.start())

        # Store the coordinator in Home Assistant's data registry
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][account_name] = coordinator

        # Load each supported platform (e.g., sensor, todo) for the account
        for platform in PLATFORMS:
            load_platform(
                hass, platform, DOMAIN, {"account_name": account_name}, config
            )

    _LOGGER.debug("Finished adding all Remember the milk accounts")
    return True


def _create_instance(
    hass, account_name, api_key, shared_secret, token, stored_rtm_config, component
):
    """Create and register a Remember The Milk entity instance.

    This function initializes a RememberTheMilkEntity, adds it to the component,
    and registers the associated services for task creation and completion.

    Args:
        hass: The Home Assistant instance.
        account_name (str): The name of the Remember The Milk account.
        api_key (str): The API key for the account.
        shared_secret (str): The shared secret for the account.
        token (str): The access token for the account.
        stored_rtm_config (RememberTheMilkConfiguration): The stored configuration.
        component (EntityComponent): The entity component to add entities to.

    """
    # Initialize the Remember The Milk entity
    entity = RememberTheMilkEntity(
        account_name, api_key, shared_secret, token, stored_rtm_config
    )
    # Add the entity to the Home Assistant component
    component.add_entities([entity])

    # Register the create_task service for this account
    hass.services.register(
        DOMAIN,
        f"{account_name}_create_task",
        entity.create_task,
        schema=SERVICE_SCHEMA_CREATE_TASK,
    )

    # Register the complete_task service for this account
    hass.services.register(
        DOMAIN,
        f"{account_name}_complete_task",
        entity.complete_task,
        schema=SERVICE_SCHEMA_COMPLETE_TASK,
    )


def _register_new_account(
    hass, account_name, api_key, shared_secret, stored_rtm_config, component
):
    """Initiate the registration process for a new Remember The Milk account.

    This function handles the OAuth flow by requesting user authentication and
    retrieving the access token upon successful login.

    Args:
        hass: The Home Assistant instance.
        account_name (str): The name of the Remember The Milk account.
        api_key (str): The API key for the account.
        shared_secret (str): The shared secret for the account.
        stored_rtm_config (RememberTheMilkConfiguration): The stored configuration.
        component (EntityComponent): The entity component to add entities to.

    """
    request_id = None
    # Initialize the RTM API client without a token
    api = Rtm(api_key, shared_secret, "delete", None)
    # Generate the authentication URL and frob (temporary token)
    url, frob = api.authenticate_desktop()
    _LOGGER.debug("Sent authentication request to server")

    def register_account_callback(fields: list[dict[str, str]]) -> None:
        """Callback function to handle account registration after user authentication.

        This function retrieves the access token using the frob, stores it,
        creates the entity instance, and finalizes the configurator request.

        Args:
        fields (list[dict[str, str]]): Fields returned from the configurator.

        """  # noqa: D401
        # Retrieve the access token using the frob
        api.retrieve_token(frob)
        token = api.token
        if token is None:
            # Log an error and notify the user if token retrieval fails
            _LOGGER.error("Failed to register, please try again")
            configurator.notify_errors(
                hass, request_id, "Failed to register, please try again."
            )
            return

        # Store the retrieved token
        stored_rtm_config.set_token(account_name, token)
        _LOGGER.debug("Retrieved new token from server")

        # Create and register the entity instance with the new token
        _create_instance(
            hass,
            account_name,
            api_key,
            shared_secret,
            token,
            stored_rtm_config,
            component,
        )

        # Mark the configurator request as done
        configurator.request_done(hass, request_id)

    # Request user configuration through the Home Assistant configurator
    request_id = configurator.request_config(
        hass,
        f"{DOMAIN} - {account_name}",
        callback=register_account_callback,
        description=(
            "You need to log in to Remember The Milk to"
            "connect your account. \n\n"
            "Step 1: Click on the link 'Remember The Milk login'\n\n"
            "Step 2: Click on 'login completed'"
        ),
        link_name="Remember The Milk login",
        link_url=url,
        submit_caption="login completed",
    )


class RememberTheMilkConfiguration:
    """Internal configuration data for RememberTheMilk class.

    This class handles the storage and retrieval of authentication tokens and
    mappings between Home Assistant task IDs and Remember The Milk task IDs.
    """

    def __init__(self, hass):
        """Create a new instance of RememberTheMilkConfiguration.

        This initializes the configuration by loading existing data from a file
        or creating a new configuration if the file does not exist.

        Args:
            hass (HomeAssistant): The Home Assistant instance.

        """
        # Define the path to the configuration file
        self._config_file_path = hass.config.path(CONFIG_FILE_NAME)
        if not os.path.isfile(self._config_file_path):
            # Initialize an empty configuration if the file does not exist
            self._config = {}
            return
        try:
            _LOGGER.debug("Loading configuration from file: %s", self._config_file_path)
            # Load the existing configuration from the JSON file
            with open(self._config_file_path, encoding="utf8") as config_file:
                self._config = json.load(config_file)
        except ValueError:
            # Log an error and initialize a new configuration if loading fails
            _LOGGER.error(
                "Failed to load configuration file, creating a new one: %s",
                self._config_file_path,
            )
            self._config = {}

    def save_config(self):
        """Write the current configuration to the configuration file.

        This method serializes the configuration dictionary to a JSON file.
        """
        with open(self._config_file_path, "w", encoding="utf8") as config_file:
            json.dump(self._config, config_file)

    def get_token(self, profile_name):
        """Retrieve the authentication token for a given profile.

        Args:
            profile_name (str): The name of the profile.

        Returns:
            str or None: The authentication token if it exists, otherwise None.

        """
        if profile_name in self._config:
            return self._config[profile_name][CONF_TOKEN]
        return None

    def set_token(self, profile_name, token):
        """Store a new authentication token for a given profile.

        Args:
            profile_name (str): The name of the profile.
            token (str): The authentication token to store.

        """
        self._initialize_profile(profile_name)
        self._config[profile_name][CONF_TOKEN] = token
        self.save_config()

    def delete_token(self, profile_name):
        """Delete the authentication token for a given profile.

        This is typically called when the token has expired or needs to be refreshed.

        Args:
            profile_name (str): The name of the profile.

        """
        self._config.pop(profile_name, None)
        self.save_config()

    def _initialize_profile(self, profile_name):
        """Initialize the data structures for a given profile.

        Ensures that the profile exists in the configuration and initializes
        the ID mapping if it does not already exist.

        Args:
            profile_name (str): The name of the profile.

        """
        if profile_name not in self._config:
            self._config[profile_name] = {}
        if CONF_ID_MAP not in self._config[profile_name]:
            self._config[profile_name][CONF_ID_MAP] = {}

    def get_rtm_id(self, profile_name, hass_id):
        """Retrieve the Remember The Milk task IDs for a given Home Assistant task ID.

        Args:
            profile_name (str): The name of the profile.
            hass_id (str): The Home Assistant task ID.

        Returns:
            tuple or None: A tuple containing (list_id, timeseries_id, task_id) if found, otherwise None.

        """
        self._initialize_profile(profile_name)
        ids = self._config[profile_name][CONF_ID_MAP].get(hass_id)
        if ids is None:
            return None
        return ids[CONF_LIST_ID], ids[CONF_TIMESERIES_ID], ids[CONF_TASK_ID]

    def set_rtm_id(self, profile_name, hass_id, list_id, time_series_id, rtm_task_id):
        """Add or update the Remember The Milk task IDs for a given Home Assistant task ID.

        Args:
            profile_name (str): The name of the profile.
            hass_id (str): The Home Assistant task ID.
            list_id (str): The Remember The Milk list ID.
            time_series_id (str): The Remember The Milk timeseries ID.
            rtm_task_id (str): The Remember The Milk task ID.

        """
        self._initialize_profile(profile_name)
        id_tuple = {
            CONF_LIST_ID: list_id,
            CONF_TIMESERIES_ID: time_series_id,
            CONF_TASK_ID: rtm_task_id,
        }
        self._config[profile_name][CONF_ID_MAP][hass_id] = id_tuple
        self.save_config()

    def delete_rtm_id(self, profile_name, hass_id):
        """Delete the Remember The Milk task IDs mapping for a given Home Assistant task ID.

        Args:
            profile_name (str): The name of the profile.
            hass_id (str): The Home Assistant task ID.

        """
        self._initialize_profile(profile_name)
        if hass_id in self._config[profile_name][CONF_ID_MAP]:
            del self._config[profile_name][CONF_ID_MAP][hass_id]
            self.save_config()
