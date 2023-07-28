"""Config flow for SlxChargingController integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import (
    HomeAssistant,
    callback,
    State,
    async_get_hass,
    ServiceRegistry,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry, device_registry
from homeassistant.helpers.service import async_get_all_descriptions

from homeassistant.helpers.selector import (
    BooleanSelector,
    FileSelector,
    FileSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from collections import OrderedDict


from homeassistant.const import (
    CONF_SCAN_INTERVAL,
)

from .slxopenevse import SLXOpenEVSE

from .const import (
    CONF_CHARGE_TARGET,
    DEFAULT_CHARGE_TARGET,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    CONF_BATTERY_CAPACITY,
    DEFAULT_BATTERY_CAPACITY,
    CONF_EVSE_SESSION_ENERGY,
    CONF_EVSE_PLUG_CONNECTED,
    CONF_CAR_SOC_LEVEL,
    CONF_CAR_SOC_UPDATE_TIME,
)

import json

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCAN_INTERVAL): int,
        vol.Required(CONF_CHARGE_TARGET): int,
    }
)

# class PlaceholderHub:
#     """Placeholder class to make tests pass.
#     TODO Remove this placeholder class and replace with things from your PyPI package.
#     """
#     def __init__(self, host: str) -> None:
#         """Initialize."""
#         self.host = host
#     async def authenticate(self, username: str, password: str) -> bool:
#         """Test if we can authenticate with the host."""
#         return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.
    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # TODO we can calidate data provided by a user.
    # This makes sense in case of e.g. connection, but not necessarily useful here.

    # TODO check if it makes sense to return values. Maybe it should be modified input data instead
    # Return info that you want to store in the config entry.
    return {"title": "SLX Charging Controller", "extra field": "can I add extra text"}


BATTERY_SELECTOR = vol.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=10, max=100)),
    vol.Coerce(int),
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SlxChargingController."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        if user_input is None:
            _LOGGER.debug("Returning the form")
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            _LOGGER.debug("I will wait to validate input")
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            _LOGGER.debug("System is ready for optional flow")
            return self.async_create_entry(title=info["title"], data=user_input)

        _LOGGER.debug("Empty user input let me display the form")
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SlxChargerOptionFlowHander(config_entry)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class SlxChargerOptionFlowHander(config_entries.OptionsFlow):
    """Handes an optoin flow configuration"""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry
        _LOGGER.info("Entered Option Flow __init__")
        # https://developers.home-assistant.io/blog/2022/08/24/globally_accessible_hass/
        self.hass = async_get_hass()

        list_of_energy = self.__find_entities_of_unit(self.hass, {"kWh", "Wh"})
        list_of_percent = self.__find_entities_of_unit(self.hass, {"%"})
        list_of_plugs = self.__find_entities_of_device_type(
            self.hass, "binary_sensor", {"plug"}
        )
        list_of_timestamps = self.__find_entities_of_device_type(
            self.hass, "sensor", {"timestamp"}
        )

        # build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[
            vol.Required(
                CONF_BATTERY_CAPACITY,
                default=self.config_entry.options.get(
                    CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY
                ),
            )
        ] = BATTERY_SELECTOR

        current_car_soc_level = self.config_entry.options.get(CONF_CAR_SOC_LEVEL, "")
        fields[
            vol.Required(
                CONF_CAR_SOC_LEVEL,
                default=current_car_soc_level,
                description={"suggested_value": current_car_soc_level},
            )
        ] = self.__build_selector(list_of_percent)

        current_car_soc_update_time = self.config_entry.options.get(
            CONF_CAR_SOC_UPDATE_TIME, ""
        )
        fields[
            vol.Required(
                CONF_CAR_SOC_UPDATE_TIME,
                default=current_car_soc_update_time,
                description={"suggested_value": current_car_soc_update_time},
            )
        ] = self.__build_selector(list_of_timestamps)

        current_evse_energy = self.config_entry.options.get(
            CONF_EVSE_SESSION_ENERGY, ""
        )
        fields[
            vol.Required(
                CONF_EVSE_SESSION_ENERGY,
                default=current_evse_energy,
                description={"suggested_value": current_evse_energy},
            )
        ] = self.__build_selector(list_of_energy)

        current_evse_plug_connected = self.config_entry.options.get(
            CONF_EVSE_PLUG_CONNECTED, ""
        )
        fields[
            vol.Required(
                CONF_EVSE_PLUG_CONNECTED,
                default=current_evse_plug_connected,
                description={"suggested_value": current_evse_plug_connected},
            )
        ] = self.__build_selector(list_of_plugs)

        ## TODO replace with SLXOpenEVSE call for checking entities.
        SLXOpenEVSE.check_all_entities(self.hass)
        self.schema = vol.Schema(fields)

    async def async_step_init(self, user_input=None) -> FlowResult:
        # Probably needed for service setup.
        # descriptions = await async_get_all_descriptions(self.hass)

        # if user_input is not None:
        #     return self.async_create_entry(
        #         title=self.config_entry.title, data=user_input
        #     )

        if user_input is not None:
            return self.async_show_menu(
                step_id="init",
                menu_options={
                    "openevse": "Option OpenEVSE",
                    "confirm": "Confirm the config",
                },  # those are becoming steps which are function methods! So I don't need to handle everything in one method!
            )
        else:
            return self.async_show_menu(
                step_id="init",
                menu_options={
                    "openevse": "Option OpenEVSE",
                },  # those are becoming steps which are function methods! So I don't need to handle everything in one method!
            )
        # return self.async_show_form(step_id="init", data_schema=self.schema)

    async def async_step_openevse(self, user_input=None) -> FlowResult:
        return self.async_show_form(
            step_id="init", data_schema=self.schema
        )  # step_id includes next step!

    async def async_step_confirm(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=self.config_entry.title, data=user_input
            )

    def __find_entities_of_unit(
        self, hass: HomeAssistant, units: set(str)
    ) -> dict[str, Any]:
        """Finds HA entities with specitic unit of measurement"""
        output_dict = {}
        for state in hass.states.async_all():
            entity_id = state.entity_id
            if "unit_of_measurement" in state.attributes:
                unit = state.attributes["unit_of_measurement"]
                friendly_name = "noname"
                if "friendly_name" in state.attributes:
                    friendly_name = state.attributes["friendly_name"]
                if unit in units:
                    output_dict[entity_id] = (
                        friendly_name + "[" + unit + "](" + entity_id + ")"
                    )
        return output_dict

    def __find_entities_of_device_type(
        self, hass: HomeAssistant, domain: str, dev_classes: set(str)
    ) -> dict[str, Any]:
        """Finds HA entities with specific unit of measurement"""
        output_dict = {}
        for state in hass.states.async_all():
            entity_id = state.entity_id
            if entity_id.startswith(domain):
                if "device_class" in state.attributes:
                    dev_class = state.attributes["device_class"]
                    if dev_class in dev_classes:
                        friendly_name = "noname_plug"
                        if "friendly_name" in state.attributes:
                            friendly_name = state.attributes["friendly_name"]
                        output_dict[entity_id] = friendly_name + "(" + entity_id + ")"
        return output_dict

    def __build_selector(self, listEntities: dict[str, Any]) -> SelectSelector:
        # https://www.home-assistant.io/docs/blueprint/selectors/#select-selector
        options_list = []
        for key, value in listEntities.items():
            options_list.append(SelectOptionDict(value=key, label=value))
        built_selector = SelectSelector(
            SelectSelectorConfig(
                options=options_list,
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
        return built_selector
