"""Test the for the SLXChargingController config flow."""
from custom_components.slxchargingcontroller.const import DOMAIN

from homeassistant import config_entries, data_entry_flow

# from homeassistant.components.bmw_connected_drive.config_flow import DOMAIN
# from homeassistant.components.bmw_connected_drive.const import (
#     CONF_READ_ONLY,
#     CONF_REFRESH_TOKEN,
# )
# from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from homeassistant.core import HomeAssistant


def test_domain():
    assert DOMAIN == "slxchargingcontroller"
