"""Constants for the Salix Charging Controller integration."""

DOMAIN = "slxchargingcontroller"

CONF_CHARGE_TARGET: str = "charge_target"
DEFAULT_CHARGE_TARGET: int = 80
DEFAULT_SCAN_INTERVAL: int = 5

CONF_BATTERY_CAPACITY: str = "battery_capacity"
DEFAULT_BATTERY_CAPACITY: int = 64

CONF_EVSE_SESSION_ENERGY: str = "evse_session_energy"
CONF_EVSE_PLUG_CONNECTED: str = "evse_plug_connected"

CONF_CAR_SOC_LEVEL: str = "car_soc_level"
CONF_CAR_SOC_UPDATE_TIME: str = "car_soc_update_time"
