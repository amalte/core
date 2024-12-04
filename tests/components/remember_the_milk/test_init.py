"""Tests for the Remember The Milk component."""

from unittest.mock import Mock, mock_open, patch, call, ANY

import homeassistant.components.remember_the_milk as rtm
from homeassistant.components.remember_the_milk import setup
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent


from .const import JSON_STRING, PROFILE, TOKEN


def test_setup_single_account(hass: HomeAssistant) -> None:
    """Test setup with a single valid accounr."""
    config = {
        "remember_the_milk": [
            {
                "name": "TestAccount",
                "api_key": "test_api_key",
                "shared_secret": "test_shared_secret",
            }
        ]
    }

    with (
        patch(
            "homeassistant.components.remember_the_milk.RememberTheMilkConfiguration"
        ) as mock_config_class,
        patch(
            "homeassistant.components.remember_the_milk._create_instance"
        ) as mock_create_instance,
        patch(
            "homeassistant.components.remember_the_milk._register_new_account"
        ) as mock_register_new_account,
        patch(
            "homeassistant.components.remember_the_milk.RememberTheMilkCoordinator"
        ) as mock_coordinator_class,
        patch(
            "homeassistant.components.remember_the_milk.load_platform"
        ) as mock_load_platform,
    ):
        mock_config = Mock()
        mock_config.get_token.return_value = None  # Simulate no token available
        mock_config_class.return_value = mock_config
        mock_coordinator = Mock()
        mock_coordinator_class.return_value = mock_coordinator

        assert rtm.setup(hass, config) is True

        # Verify new account registration was triggered
        mock_register_new_account.assert_called_once()
        mock_create_instance.assert_not_called()  # No existing token, so no instance creation

        # Verify coordinator was created and started
        mock_coordinator_class.assert_called_once_with(
            hass, rtm._LOGGER, "test_api_key", "test_shared_secret", None
        )
        mock_coordinator.rate_limiter.start.assert_called_once()

        # Ensure platform loading was called
        for platform in rtm.PLATFORMS:
            mock_load_platform.assert_any_call(
                hass, platform, rtm.DOMAIN, {"account_name": "TestAccount"}, config
            )


def test_create_instance(hass: HomeAssistant) -> None:
    """Test the _create_instance method."""
    account_name = "TestAccount"
    api_key = "test_api_key"
    shared_secret = "test_shared_secret"
    token = "test_token"

    with (
        patch(
            "homeassistant.components.remember_the_milk.RememberTheMilkEntity"
        ) as mock_entity,
    ):
        mock_component = Mock()  # Mock for the EntityComponent
        stored_rtm_config = Mock()  # Mock configuration

        # Create a mock for the hass.services
        mock_hass_services = Mock()
        hass.services = mock_hass_services

        # Call the _create_instance method
        rtm._create_instance(
            hass,
            account_name,
            api_key,
            shared_secret,
            token,
            stored_rtm_config,
            mock_component,
        )

        # Verify the RememberTheMilkEntity was created
        mock_entity.assert_called_once_with(
            account_name, api_key, shared_secret, token, stored_rtm_config
        )

        # Verify the entity was added to the component
        mock_component.add_entities.assert_called_once_with([mock_entity.return_value])

        # Verify services were registered
        mock_hass_services.register.assert_has_calls(
            [
                call(
                    rtm.DOMAIN,
                    f"{account_name}_create_task",
                    mock_entity.return_value.create_task,
                    schema=rtm.SERVICE_SCHEMA_CREATE_TASK,
                ),
                call(
                    rtm.DOMAIN,
                    f"{account_name}_complete_task",
                    mock_entity.return_value.complete_task,
                    schema=rtm.SERVICE_SCHEMA_COMPLETE_TASK,
                ),
            ]
        )


def test_register_new_account_success(hass: HomeAssistant) -> None:
    """Test _register_new_account with successful token retrieval."""
    account_name = "TestAccount"
    api_key = "test_api_key"
    shared_secret = "test_shared_secret"
    url = "http://auth.url"
    frob = "test_frob"
    token = "test_token"

    with (
        patch("homeassistant.components.remember_the_milk.Rtm") as mock_rtm,
        patch(
            "homeassistant.components.remember_the_milk.configurator"
        ) as mock_configurator,
        patch(
            "homeassistant.components.remember_the_milk._create_instance"
        ) as mock_create_instance,
    ):
        mock_api = Mock()
        mock_api.authenticate_desktop.return_value = (url, frob)
        mock_api.token = token
        mock_api.retrieve_token = Mock()
        mock_rtm.return_value = mock_api

        stored_rtm_config = Mock()
        mock_component = Mock()

        # Call the method
        rtm._register_new_account(
            hass,
            account_name,
            api_key,
            shared_secret,
            stored_rtm_config,
            mock_component,
        )

        # Capture the callback
        args, kwargs = mock_configurator.request_config.call_args
        callback = kwargs["callback"]

        # Simulate the callback execution
        callback([])

        # Verify token retrieval and instance creation
        mock_api.retrieve_token.assert_called_once_with(frob)
        stored_rtm_config.set_token.assert_called_once_with(account_name, token)
        mock_create_instance.assert_called_once_with(
            hass,
            account_name,
            api_key,
            shared_secret,
            token,
            stored_rtm_config,
            mock_component,
        )
        mock_configurator.request_done.assert_called_once()


def test_register_new_account_failure(hass: HomeAssistant) -> None:
    """Test _register_new_account with failed token retrieval."""
    account_name = "TestAccount"
    api_key = "test_api_key"
    shared_secret = "test_shared_secret"
    url = "http://auth.url"
    frob = "test_frob"

    with (
        patch("homeassistant.components.remember_the_milk.Rtm") as mock_rtm,
        patch(
            "homeassistant.components.remember_the_milk.configurator"
        ) as mock_configurator,
    ):
        mock_api = Mock()
        mock_api.authenticate_desktop.return_value = (url, frob)
        mock_api.token = None  # Simulate failed token retrieval
        mock_api.retrieve_token = Mock()
        mock_rtm.return_value = mock_api

        stored_rtm_config = Mock()
        mock_component = Mock()

        # Call the method
        rtm._register_new_account(
            hass,
            account_name,
            api_key,
            shared_secret,
            stored_rtm_config,
            mock_component,
        )

        # Capture the callback and request_id
        args, kwargs = mock_configurator.request_config.call_args
        callback = kwargs["callback"]
        request_id = mock_configurator.request_config.return_value

        # Simulate the callback execution
        callback([])

        # Verify token retrieval and error handling
        mock_api.retrieve_token.assert_called_once_with(frob)
        stored_rtm_config.set_token.assert_not_called()
        mock_configurator.notify_errors.assert_called_once_with(
            hass, request_id, "Failed to register, please try again."
        )


def test_save_config(hass) -> None:
    """Test the save_config method."""
    config_data = {"test_key": "test_value"}
    config_file_path = "/path/to/config/file.json"

    with (
        patch("builtins.open", mock_open(read_data="{}")) as mock_file,
        patch("json.dump") as mock_json_dump,
    ):
        # Create the RememberTheMilkConfiguration object with mocked data
        config = rtm.RememberTheMilkConfiguration(hass)
        config._config_file_path = config_file_path
        config._config = config_data

        # Reset mock calls to isolate the save_config method
        mock_file.reset_mock()

        # Call the save_config method
        config.save_config()

        # Verify the file was opened with the correct path and mode
        mock_file.assert_called_once_with(config_file_path, "w", encoding="utf8")

        # Verify json.dump was called with the correct data and file handle
        mock_json_dump.assert_called_once_with(config_data, mock_file.return_value)


def test_get_token(hass) -> None:
    """Test the get_token method."""
    profile_name = "TestProfile"
    token = "test_token"

    # Create the RememberTheMilkConfiguration object with mocked data
    config = rtm.RememberTheMilkConfiguration(hass)
    config._config = {
        profile_name: {rtm.CONF_TOKEN: token},
        "AnotherProfile": {rtm.CONF_TOKEN: "another_token"},
    }

    # Test when the profile exists
    assert config.get_token(profile_name) == token

    # Test when the profile does not exist
    assert config.get_token("NonExistentProfile") is None


def test_delete_token(hass) -> None:
    """Test the delete_token method."""
    profile_name = "TestProfile"

    with patch.object(
        rtm.RememberTheMilkConfiguration, "save_config"
    ) as mock_save_config:
        # Create the RememberTheMilkConfiguration object with mocked data
        config = rtm.RememberTheMilkConfiguration(hass)
        config._config = {
            profile_name: {"some_key": "some_value"},
            "AnotherProfile": {"some_key": "another_value"},
        }

        # Test deleting an existing profile
        config.delete_token(profile_name)
        assert profile_name not in config._config
        mock_save_config.assert_called_once()

        # Reset mock for the next test
        mock_save_config.reset_mock()

        # Test deleting a non-existent profile
        config.delete_token("NonExistentProfile")
        mock_save_config.assert_called_once()  # save_config should still be called


def test_create_new(hass: HomeAssistant) -> None:
    """Test creating a new config file."""
    with (
        patch("builtins.open", mock_open()),
        patch("os.path.isfile", Mock(return_value=False)),
        patch.object(rtm.RememberTheMilkConfiguration, "save_config"),
    ):
        config = rtm.RememberTheMilkConfiguration(hass)
        config.set_token(PROFILE, TOKEN)
    assert config.get_token(PROFILE) == TOKEN


def test_load_config(hass: HomeAssistant) -> None:
    """Test loading an existing token from the file."""
    with (
        patch("builtins.open", mock_open(read_data=JSON_STRING)),
        patch("os.path.isfile", Mock(return_value=True)),
    ):
        config = rtm.RememberTheMilkConfiguration(hass)
    assert config.get_token(PROFILE) == TOKEN


def test_invalid_data(hass: HomeAssistant) -> None:
    """Test starts with invalid data and should not raise an exception."""
    with (
        patch("builtins.open", mock_open(read_data="random characters")),
        patch("os.path.isfile", Mock(return_value=True)),
    ):
        config = rtm.RememberTheMilkConfiguration(hass)
    assert config is not None


def test_id_map(hass: HomeAssistant) -> None:
    """Test the hass to rtm task is mapping."""
    hass_id = "hass-id-1234"
    list_id = "mylist"
    timeseries_id = "my_timeseries"
    rtm_id = "rtm-id-4567"
    with (
        patch("builtins.open", mock_open()),
        patch("os.path.isfile", Mock(return_value=False)),
        patch.object(rtm.RememberTheMilkConfiguration, "save_config"),
    ):
        config = rtm.RememberTheMilkConfiguration(hass)

        assert config.get_rtm_id(PROFILE, hass_id) is None
        config.set_rtm_id(PROFILE, hass_id, list_id, timeseries_id, rtm_id)
        assert (list_id, timeseries_id, rtm_id) == config.get_rtm_id(PROFILE, hass_id)
        config.delete_rtm_id(PROFILE, hass_id)
        assert config.get_rtm_id(PROFILE, hass_id) is None


def test_load_key_map(hass: HomeAssistant) -> None:
    """Test loading an existing key map from the file."""
    with (
        patch("builtins.open", mock_open(read_data=JSON_STRING)),
        patch("os.path.isfile", Mock(return_value=True)),
    ):
        config = rtm.RememberTheMilkConfiguration(hass)
    assert config.get_rtm_id(PROFILE, "1234") == ("0", "1", "2")
