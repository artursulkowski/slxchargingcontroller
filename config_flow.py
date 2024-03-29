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

from .slxopenevse import SLXOpenEvse
from .slxkiahyundai import SLXKiaHyundai
from .slxcar import SLXCar
from .slxbmw import SLXBmw

from .const import (
    DOMAIN,
    CONF_CHARGER_TYPE,
    CONF_CAR_TYPE,
    CONF_BATTERY_CAPACITY,
    DEFAULT_BATTERY_CAPACITY,
    CONF_EVSE_SESSION_ENERGY,
    CONF_EVSE_PLUG_CONNECTED,
    CONF_CAR_SOC_LEVEL,
    CONF_CAR_SOC_UPDATE_TIME,
)

import json

_LOGGER = logging.getLogger(__name__)

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


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SlxChargingController."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
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

    async def async_step_init(self, user_input=None) -> FlowResult:
        # Probably needed for service setup.
        # descriptions = await async_get_all_descriptions(self.hass)

        return await SLXConfigFlow.config_flow(
            self, self.config_entry, "init", "Title", user_input
        )


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
    def build_selector(
        listEntities: dict[str, Any], dropdown: bool = True
    ) -> SelectSelector:
        # https://www.home-assistant.io/docs/blueprint/selectors/#select-selector
        options_list = []
        for key, value in listEntities.items():
            options_list.append(SelectOptionDict(value=key, label=value))

        if dropdown is True:
            mode = SelectSelectorMode.DROPDOWN
        else:
            mode = SelectSelectorMode.LIST
        built_selector = SelectSelector(
            SelectSelectorConfig(
                options=options_list,
                custom_value=False,
                mode=mode,
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

        openevse_devices = SLXOpenEvse.find_openevse_devices(hass)

        for device_id, device_name in openevse_devices.items():
            if SLXOpenEvse.check_all_entities(hass, device_id, device_name):
                list_openevse[f"openevse.{device_id}"] = f"OpenEVSE: {device_name}"
                _LOGGER.info(
                    "Found correct OpenEVSE deviceID: %s, deviceName: %s",
                    device_id,
                    device_name,
                )
            else:
                _LOGGER.warning(
                    "Found OpenEVSE device but without proper entities, deviceID: %s, deviceName: %s",
                    device_id,
                    device_name,
                )

        list_options: dict[str, Any] = list_openevse
        list_options["manual"] = "Manual Configuraton"

        current_charger_type = ""
        if config_entry is not None:
            current_charger_type = config_entry.options.get(CONF_CHARGER_TYPE, "")

        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[
            vol.Required(
                CONF_CHARGER_TYPE,
                # default=current_charger_type,
                description={"suggested_value": current_charger_type},
            )
        ] = SLXConfigHelper.build_selector(list_options, dropdown=False)
        return vol.Schema(fields)

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
    async def _get_schema_car(
        hass: HomeAssistant,
        user_input: Optional[Dict[str, Any]],
        # default_dict: Dict[str, Any],
        config_entry: config_entries.ConfigEntry | None,
        # pylint: disable-next=unused-argument
        entry_id: str = None,
    ) -> vol.Schema:
        list_options: dict[str, str] = {}

        integration_found_kiahyundai = await SLXCar.async_find_integration_by_domain(
            hass, SLXKiaHyundai.get_domain()
        )
        if integration_found_kiahyundai is True:
            found_kiahyundai_devices = SLXCar.find_devices_check_entites(
                hass, SLXKiaHyundai.get_domain(), SLXKiaHyundai.get_required_entities()
            )
            for device_id, device_name in found_kiahyundai_devices.items():
                list_options[
                    f"kia_hyundai.{device_id}"
                ] = f"[Kia/Hyundai] {device_name}"

        integration_found_bmw = await SLXCar.async_find_integration_by_domain(
            hass, SLXBmw.get_domain()
        )
        if integration_found_bmw is True:
            found_bmw_devices = SLXCar.find_devices_check_entites(
                hass, SLXBmw.get_domain(), SLXBmw.get_required_entities()
            )
            for device_id, device_name in found_bmw_devices.items():
                list_options[f"bmw.{device_id}"] = f"[BMW] {device_name}"

        list_options["manual"] = "Manual Configuraton"

        current_car_type = ""
        if config_entry is not None:
            current_car_type = config_entry.options.get(CONF_CAR_TYPE, "")

        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[
            vol.Required(
                CONF_CAR_TYPE,
                default=current_car_type,
                description={"suggested_value": current_car_type},
            )
        ] = SLXConfigHelper.build_selector(list_options, dropdown=False)
        return vol.Schema(fields)

    def _get_schema_carmanual(
        hass: HomeAssistant,
        user_input: Optional[Dict[str, Any]],
        config_entry: config_entries.ConfigEntry | None,
        entry_id: str = None,
    ) -> vol.Schema:
        list_of_percent = SLXConfigHelper.find_entities_of_unit(hass, {"%"})
        list_of_timestamps = SLXConfigHelper.find_entities_of_device_type(
            hass, "sensor", {"timestamp"}
        )

        fields: OrderedDict[vol.Marker, Any] = OrderedDict()

        current_car_soc_level = ""
        if config_entry is not None:
            current_car_soc_level = config_entry.options.get(CONF_CAR_SOC_LEVEL, "")

        fields[
            vol.Required(
                CONF_CAR_SOC_LEVEL,
                default=current_car_soc_level,
                description={"suggested_value": current_car_soc_level},
            )
        ] = SLXConfigHelper.build_selector(list_of_percent)

        current_car_soc_update_time = ""
        if config_entry is not None:
            current_car_soc_update_time = config_entry.options.get(
                CONF_CAR_SOC_UPDATE_TIME, ""
            )

        fields[
            vol.Optional(
                CONF_CAR_SOC_UPDATE_TIME,
                default=current_car_soc_update_time,
                description={"suggested_value": current_car_soc_update_time},
            )
        ] = SLXConfigHelper.build_selector(list_of_timestamps)
        return vol.Schema(fields)

    def _get_schema_cardetails(
        hass: HomeAssistant,
        user_input: Optional[Dict[str, Any]],
        config_entry: config_entries.ConfigEntry | None,
        entry_id: str = None,
    ) -> vol.Schema:
        BATTERY_SELECTOR = vol.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=10, max=100)
            ),
            vol.Coerce(int),
        )

        fields: OrderedDict[vol.Marker, Any] = OrderedDict()

        current_battery_capacity = ""
        if config_entry is not None:
            current_battery_capacity = config_entry.options.get(
                CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY
            )

        fields[
            vol.Required(CONF_BATTERY_CAPACITY, default=current_battery_capacity)
        ] = BATTERY_SELECTOR
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

            # Test only - flow for SLXKiaHyundai
            # result = await SLXKiaHyundai.async_find_integration(cf_object.hass)
            # _LOGGER.warning(result)
            # SLXKiaHyundai.check_entites_and_devices(cf_object.hass)
            # _LOGGER.warning("######")

        else:
            SLXConfigFlow.combined_user_input.update(user_input)

        current_step = SLXConfigFlow.config_step

        last_step: bool = False
        schema = None
        my_description_placeholders = {
            "config_step_description": "Config Step",
            "config_step_title": "Setup SLX charging controller",
        }
        if current_step == "Charger_1":
            schema = SLXConfigFlow._get_schema_charger(
                cf_object.hass, user_input, config_entry, entry_id
            )
            my_description_placeholders["config_step_title"] = "Select charger device"
            my_description_placeholders[
                "config_step_description"
            ] = "Select existing integration or Manual Configuration for integration through entities"
            SLXConfigFlow.config_step = "Charger_2"

        if current_step == "Charger_2":
            charger_type = ""
            if CONF_CHARGER_TYPE in SLXConfigFlow.combined_user_input:
                charger_type = SLXConfigFlow.combined_user_input[CONF_CHARGER_TYPE]
            if charger_type == "manual":
                my_description_placeholders[
                    "config_step_title"
                ] = "Charger integration through entities"
                my_description_placeholders[
                    "config_step_description"
                ] = "Select entities including required information"
                schema = SLXConfigFlow._get_schema_chargermanual(
                    cf_object.hass, user_input, config_entry, entry_id
                )
                SLXConfigFlow.config_step = "Car_1"
            else:
                # jump straight to another step
                current_step = "Car_1"

        if current_step == "Car_1":
            my_description_placeholders["config_step_title"] = "Select car integration"
            my_description_placeholders[
                "config_step_description"
            ] = "Select existing integration or Manual Configuration for integration through entities"
            schema = await SLXConfigFlow._get_schema_car(
                cf_object.hass, user_input, config_entry, entry_id
            )
            SLXConfigFlow.config_step = "Car_2"

        if current_step == "Car_2":
            car_type = ""
            if CONF_CAR_TYPE in SLXConfigFlow.combined_user_input:
                car_type = SLXConfigFlow.combined_user_input[CONF_CAR_TYPE]
            if car_type == "manual":
                my_description_placeholders[
                    "config_step_title"
                ] = "Manual car integration"
                my_description_placeholders[
                    "config_step_description"
                ] = "Select entities including required information"
                schema = SLXConfigFlow._get_schema_carmanual(
                    cf_object.hass, user_input, config_entry, entry_id
                )
                SLXConfigFlow.config_step = "Car_3"
            else:
                current_step = "Car_3"

        if current_step == "Car_3":
            my_description_placeholders["config_step_title"] = "Car details"
            my_description_placeholders[
                "config_step_description"
            ] = "Last step! Just few details about your car"
            schema = SLXConfigFlow._get_schema_cardetails(
                cf_object.hass, user_input, config_entry, entry_id
            )
            last_step = True
            SLXConfigFlow.config_step = "End"

        if current_step == "End":
            _LOGGER.debug(SLXConfigFlow.combined_user_input)
            title = "SLX Charging Controller"
            if config_entry is not None:
                title = config_entry.title
                return cf_object.async_create_entry(
                    title=title,
                    data=SLXConfigFlow.combined_user_input,
                )
            else:
                return cf_object.async_create_entry(
                    title=title,
                    data=SLXConfigFlow.combined_user_input,  # can skip - put just empty data into entry
                    options=SLXConfigFlow.combined_user_input,
                )

        return cf_object.async_show_form(
            step_id=step_id,
            data_schema=schema,
            last_step=last_step,
            # errors=errors,
            description_placeholders=my_description_placeholders,
        )
