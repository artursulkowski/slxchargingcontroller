"""Config flow for SlxChargingController integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Union

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

        # if user_input is None:
        #     _LOGGER.debug("Returning the form")
        #     return self.async_show_form(
        #         step_id="user", data_schema=STEP_USER_DATA_SCHEMA
        #     )

        # errors = {}

        # try:
        #     _LOGGER.debug("I will wait to validate input")
        #     info = await validate_input(self.hass, user_input)
        # except CannotConnect:
        #     errors["base"] = "cannot_connect"
        # except InvalidAuth:
        #     errors["base"] = "invalid_auth"
        # except Exception:  # pylint: disable=broad-except
        #     _LOGGER.exception("Unexpected exception")
        #     errors["base"] = "unknown"
        # else:
        #     _LOGGER.debug("System is ready for optional flow")
        #     return self.async_create_entry(title=info["title"], data=user_input)

        # _LOGGER.debug("Empty user input let me display the form")
        # return self.async_show_form(
        #     step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        # )
        return await SLXConfigFlow.config_flow(self, None, "user", "Title", user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        return SlxChargerOptionFlowHander(config_entry)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class SlxChargerOptionFlowHander(config_entries.OptionsFlow):
    """Handes an optoin flow configuration"""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
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

        if user_input is None:
            return await SLXConfigFlow.config_flow(
                self, self.config_entry, "init", "Title", user_input
            )
        else:
            return await SLXConfigFlow.config_flow(
                self, self.config_entry, "init", "Title2", user_input
            )

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


######   NEW  CLASS FOR HANDLING FLOW ############


class SLXConfigHelper:
    @staticmethod
    def find_entities_of_unit(hass: HomeAssistant, units: set(str)) -> dict[str, Any]:
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

    @staticmethod
    def find_entities_of_device_type(
        hass: HomeAssistant, domain: str, dev_classes: set(str)
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

    @staticmethod
    def build_selector(listEntities: dict[str, Any]) -> SelectSelector:
        # https://www.home-assistant.io/docs/blueprint/selectors/#select-selector
        options_list = []
        for key, value in listEntities.items():
            options_list.append(SelectOptionDict(value=key, label=value))
        built_selector = SelectSelector(
            SelectSelectorConfig(
                options=options_list,
                custom_value=False,
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
        return built_selector


class SLXConfigFlow:
    config_step: str | None = None
    combined_user_input: dict[str, Any] = {}

    @staticmethod
    def _get_schema_charger(
        hass: HomeAssistant,
        user_input: Optional[Dict[str, Any]],
        # default_dict: Dict[str, Any],
        config_entry: config_entries.ConfigEntry | None,
        # pylint: disable-next=unused-argument
        entry_id: str = None,
    ) -> vol.Schema:
        list_openevse: dict[str, Any] = {}

        if SLXOpenEVSE.check_all_entities(hass):
            device_id = SLXOpenEVSE.openevse_id
            device_name = SLXOpenEVSE.openevse_name
            list_openevse[f"openevse.{device_id}"] = f"OpenEVSE: {device_name}"

        # list_openevse: dict[str, Any] = {"openevse.deviceID": "OpenEVSE ID"}
        list_options: dict[str, Any] = list_openevse
        list_options["manual"] = "Manual Configuraton"

        CONF_CHARGER_TYPE = "evse_charger_type"

        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[
            vol.Required(
                CONF_CHARGER_TYPE,
                default="default value",
                description={"suggested_value": "suggested value"},
            )
        ] = SLXConfigHelper.build_selector(list_options)
        return vol.Schema(fields)

    # def _get_schema_chargermanual(
    #     hass: HomeAssistant,
    #     user_input: Optional[Dict[str, Any]],
    #     default_dict: dict[str, Any],
    #     # pylint: disable-next=unused-argument
    #     entry_id: str = None,
    # ) -> vol.Schema:
    #     CONF_CHARGER_VALUE = "evse_charger_value"
    #     list_options: dict[str, Any] = {}
    #     list_options["value_a"] = "Manual Value A"
    #     list_options["value_b"] = "Manual Value B"
    #     fields: OrderedDict[vol.Marker, Any] = OrderedDict()
    #     fields[
    #         vol.Required(
    #             CONF_CHARGER_VALUE,
    #             default="default value",
    #             description={"suggested_value": "suggested value"},
    #         )
    #     ] = SLXConfigFlow._build_selector(list_options)
    #     return vol.Schema(fields)

    def _get_schema_chargermanual(
        hass: HomeAssistant,
        user_input: Optional[Dict[str, Any]],
        config_entry: config_entries.ConfigEntry | None,
        # default_dict: dict[str, Any],
        # pylint: disable-next=unused-argument
        entry_id: str = None,
    ) -> vol.Schema:
        list_of_energy = SLXConfigHelper.find_entities_of_unit(hass, {"kWh", "Wh"})
        #       list_of_percent = SLXConfigHelper.find_entities_of_unit(hass, {"%"})
        list_of_plugs = SLXConfigHelper.find_entities_of_device_type(
            hass, "binary_sensor", {"plug"}
        )

        fields: OrderedDict[vol.Marker, Any] = OrderedDict()

        current_evse_energy = ""
        if config_entry is not None:
            current_evse_energy = config_entry.options.get(CONF_EVSE_SESSION_ENERGY, "")

        fields[
            vol.Required(
                CONF_EVSE_SESSION_ENERGY,
                default=current_evse_energy,
                description={"suggested_value": current_evse_energy},
            )
        ] = SLXConfigHelper.build_selector(list_of_energy)

        current_evse_plug_connected = ""
        if config_entry is not None:
            current_evse_plug_connected = config_entry.options.get(
                CONF_EVSE_PLUG_CONNECTED, ""
            )

        fields[
            vol.Required(
                CONF_EVSE_PLUG_CONNECTED,
                default=current_evse_plug_connected,
                description={"suggested_value": current_evse_plug_connected},
            )
        ] = SLXConfigHelper.build_selector(list_of_plugs)
        return vol.Schema(fields)

    @staticmethod
    async def config_flow(
        cf_object: Union[ConfigFlow, SlxChargerOptionFlowHander],
        config_entry: config_entries.ConfigEntry | None,
        step_id: str,
        title: str,
        user_input: dict[str, Any],
        defaults: dict[str, Any] = None,
        entry_id: str = None,
    ):
        """This is universal start of config flow"""
        if user_input is None:
            # we are starting the flow soclear all the data
            SLXConfigFlow.combined_user_input = {}
            SLXConfigFlow.config_step = "Charger_1"

            ## do I need to build defaults at this stage?
            # cf_object.

        else:
            SLXConfigFlow.combined_user_input.update(user_input)

        current_step = SLXConfigFlow.config_step  # store in temporary variable

        # cf_object.config_entry.

        schema = None
        match current_step:
            case "Charger_1":
                schema = SLXConfigFlow._get_schema_charger(
                    cf_object.hass, user_input, config_entry, entry_id
                )
                SLXConfigFlow.config_step = "Charger_2"
            case "Charger_2":
                # TODO - I will need to put skipping of that step.
                schema = SLXConfigFlow._get_schema_chargermanual(
                    cf_object.hass, user_input, config_entry, entry_id
                )
                SLXConfigFlow.config_step = "Car_1"

            case "Car_1":
                _LOGGER.debug(SLXConfigFlow.combined_user_input)
                title = "SLX Charging Controller"
                if config_entry is not None:
                    title = config_entry.title
                return cf_object.async_create_entry(
                    title=title,
                    data=SLXConfigFlow.combined_user_input,
                )

        return cf_object.async_show_form(
            step_id=step_id,
            data_schema=schema,
            # errors=errors,
            # description_placeholders=description_placeholders,
        )

        ## NOTE - user input isn't passed from one step to another! So I probably need to store status in some static object within this method/class.
        ## Should I also put information stored by user? YES! as cls.async_create_entry is finishing the whole flow!

        # errors["error_type"] = "error_value"
        # if user_input is not None:
        #    cls.async_create_entry()

        ### MY IDEA HOW TO HANDLE IT
        ## Move methods into class (they will be static)
        ## add static variable storing my internal step of the flow
        ## Add static dictionary which will be gathering all or user_input which we gather after each step of configuration flow
        ## I can rely on user_input is None to restart the flow!

        # Use combined_user_input.update(user_input)

        # Does it make sense to prepare the whole flow? Probably not!
