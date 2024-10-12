"""Config flow for buienradar integration."""


import copy
from typing import Any, cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_COUNTRY_CODE, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .const import (
    CONF_DELTA,
    CONF_TIMEFRAME,
    DEFAULT_COUNTRY,
    DEFAULT_DELTA,
    DEFAULT_TIMEFRAME,
    DOMAIN,
    SUPPORTED_COUNTRY_CODES,
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_COUNTRY_CODE, default=DEFAULT_COUNTRY
        ): selector.CountrySelector(
            selector.CountrySelectorConfig(countries=SUPPORTED_COUNTRY_CODES)
        ),
        vol.Optional(CONF_DELTA, default=DEFAULT_DELTA): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="seconds",
            ),
        ),
        vol.Optional(
            CONF_TIMEFRAME, default=DEFAULT_TIMEFRAME
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=5,
                max=120,
                step=5,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="minutes",
            ),
        ),
    }
)


async def _options_suggested_values(handler: SchemaCommonFlowHandler) -> dict[str, Any]:
    parent_handler = cast(SchemaOptionsFlowHandler, handler.parent_handler)
    suggested_values = copy.deepcopy(parent_handler.config_entry.data)
    suggested_values.update(parent_handler.options)
    return suggested_values


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        OPTIONS_SCHEMA, suggested_values=_options_suggested_values
    ),
}


class BuienradarFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for buienradar."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
            }
        )

        if user_input:
            lat = user_input.get(CONF_LATITUDE)
            lon = user_input.get(CONF_LONGITUDE)

            if not lat:
                return self._show_form_with_error(data_schema, "missing_latitude")
            if not lon:
                return self._show_form_with_error(data_schema, "missing_longitude")

            await self.async_set_unique_id(f"{lat}-{lon}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=f"{lat},{lon}", data=user_input)

        return self.async_show_form(step_id="user", data_schema=data_schema, errors={})

    def _show_form_with_error(self, data_schema, error_key: str) -> ConfigFlowResult:
        """Show form with an error."""
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors={"base": error_key}
        )
