"""Global fixtures for openevse integration."""

from unittest import mock
from unittest.mock import patch

import pytest
import logging
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


pytest_plugins = "pytest_homeassistant_custom_component"

from homeassistant.const import (
    CONF_SCAN_INTERVAL,
)

from custom_components.slxchargingcontroller.const import (
    DEFAULT_SCAN_INTERVAL,
    CONF_CHARGER_TYPE,
    CONF_EVSE_SESSION_ENERGY,
    CONF_EVSE_PLUG_CONNECTED,
    CONF_CAR_TYPE,
    CONF_CAR_SOC_LEVEL,
    CONF_CAR_SOC_UPDATE_TIME,
    CONF_BATTERY_CAPACITY,
    DOMAIN,
    ENT_CHARGE_MODE,
    ENT_CHARGE_METHOD,
    CHR_MODE_UNKNOWN,
    CHR_METHOD_ECO,
    CHR_METHOD_MANUAL,
    ENT_SOC_LIMIT_MIN,
    ENT_SOC_LIMIT_MAX,
    ENT_SOC_TARGET,
    CHARGER_MODES,
)

FIXTURE__DEFAULT_CONFIG_ENTRY = {
    "entry_id": "1",
    "domain": DOMAIN,
    "title": "testinstance_slxchargingcontroller",
    "options": {
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        CONF_CAR_TYPE: "manual",
        CONF_CAR_SOC_LEVEL: "test.entity_soc",
        #        CONF_CAR_SOC_UPDATE_TIME: "",
        CONF_CHARGER_TYPE: "manual",
        CONF_EVSE_SESSION_ENERGY: "evsetest.energy",
        CONF_EVSE_PLUG_CONNECTED: "evsetest.plug",
    },
    #    "source": config_entries.SOURCE_USER,
    "unique_id": f"{DOMAIN}-fdew",
}

_LOGGER = logging.getLogger(__name__)


# This fixture enables loading custom integrations in all tests.
# Remove to enable selective use of this fixture
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integration tests."""
    yield


# registering customer marker
def pytest_configure(config):
    config.addinivalue_line("markers", "fixt_data")


@pytest.fixture
def coordinator_factory(hass: HomeAssistant, request):
    marker = request.node.get_closest_marker("fixt_data")
    if marker is None:
        yield creation_of_coordinator(hass)
    else:
        params = marker.args[0]
        yield creation_of_coordinator(hass, params)


async def creation_of_coordinator(hass, params: any = None):
    if params is None:
        config_entry = MockConfigEntry(**FIXTURE__DEFAULT_CONFIG_ENTRY)
    else:
        tmp_config = FIXTURE__DEFAULT_CONFIG_ENTRY
        _LOGGER.warning(params)
        for k, v in params.items():
            tmp_config["options"][k] = v
        _LOGGER.error(tmp_config)
        config_entry = MockConfigEntry(**tmp_config)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator_intance = hass.data[config_entry.domain][config_entry.unique_id]
    return coordinator_intance
