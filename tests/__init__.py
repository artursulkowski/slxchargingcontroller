"""Tests for slxchargingcontroller integration."""

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

FIXTURE_CONFIG_ENTRY = {
    "entry_id": "1",
    "domain": DOMAIN,
    "title": "tytul slxchargingcontroller",
    "options": {
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        CONF_CAR_TYPE: "manual",
        CONF_CAR_SOC_LEVEL: "test_entity_soc",
        CONF_CAR_SOC_UPDATE_TIME: "",
        CONF_CHARGER_TYPE: "manual",
        CONF_EVSE_SESSION_ENERGY: "",
        CONF_EVSE_PLUG_CONNECTED: "",
    },
    #    "source": config_entries.SOURCE_USER,
    "unique_id": f"{DOMAIN}-fdew",
}
