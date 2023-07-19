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
    # TODO validate the data can be used to set up a connection.
    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data["username"], data["password"]
    # )
    #   _LOGGER.error(data[CONF_SCAN_INTERVAL])
    #   _LOGGER.error(data[CONF_CHARGE_TARGET])
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

        list_of_energy = self.find_entities_of_unit(self.hass, {"kWh", "Wh"})
        list_of_percent = self.find_entities_of_unit(self.hass, {"%"})
        list_of_plugs = self.find_entities_of_device_type(
            self.hass, "binary_sensor", {"plug"}
        )
        list_of_timestamps = self.find_entities_of_device_type(
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
        ] = self.build_selector(list_of_percent)

        current_car_soc_update_time = self.config_entry.options.get(
            CONF_CAR_SOC_UPDATE_TIME, ""
        )
        fields[
            vol.Required(
                CONF_CAR_SOC_UPDATE_TIME,
                default=current_car_soc_update_time,
                description={"suggested_value": current_car_soc_update_time},
            )
        ] = self.build_selector(list_of_timestamps)

        current_evse_energy = self.config_entry.options.get(
            CONF_EVSE_SESSION_ENERGY, ""
        )
        fields[
            vol.Required(
                CONF_EVSE_SESSION_ENERGY,
                default=current_evse_energy,
                description={"suggested_value": current_evse_energy},
            )
        ] = self.build_selector(list_of_energy)

        current_evse_plug_connected = self.config_entry.options.get(
            CONF_EVSE_PLUG_CONNECTED, ""
        )
        fields[
            vol.Required(
                CONF_EVSE_PLUG_CONNECTED,
                default=current_evse_plug_connected,
                description={"suggested_value": current_evse_plug_connected},
            )
        ] = self.build_selector(list_of_plugs)

        ## TODO replace with SLXOpenEVSE call for checking entities.
        SLXOpenEVSE.check_all_entities(self.hass)
        self.schema = vol.Schema(fields)

    async def async_step_init(self, user_input=None) -> FlowResult:
        """controls step of configuration"""

        # Key: kia_uvo
        #     "force_update": {
        #     "name": "",
        #     "description": "Force your vehicle to update its data. All vehicles on the same account as the vehicle selected will be updated.",
        #     "fields": {
        #         "device_id": {
        #             "name": "Vehicle",
        #             "description": "Target vehicle",
        #             "required": false,
        #             "selector": {
        #                 "device": {
        #                     "integration": "kia_uvo"
        #                 }
        #             }
        #         }
        #     }
        # },
        descriptions = await async_get_all_descriptions(self.hass)
        my_integration: str = "kia_uvo"

        # if my_integration in descriptions:
        #     json_string = json.dumps(descriptions[my_integration])
        #     _LOGGER.debug(json_string)

        # LOGGING ALL SERVICES
        # _LOGGER.debug(descriptions)
        # for key in descriptions:
        #     _LOGGER.warning("Key: %s", key)
        #     json_string = json.dumps(descriptions[key])
        #     _LOGGER.debug(json_string)

        if user_input is not None:
            return self.async_create_entry(
                title=self.config_entry.title, data=user_input
            )
        return self.async_show_form(step_id="init", data_schema=self.schema)

    def find_entities_of_unit(
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

    def find_entities_of_device_type(
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

    def build_selector(self, listEntities: dict[str, Any]) -> SelectSelector:
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
