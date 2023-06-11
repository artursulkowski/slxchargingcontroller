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

# Entities - sensor
BATTERY_ENERGY_ESTIMATION = "bat_energy_estimated"
BATTERY_SOC_ESTIMATION = "bat_soc_estimated"
CHARGING_SESSION_DURATION = "charging_session_duration"
REQUEST_SOC_UPDATE = "request_soc_update"

# Entities - number
SOC_LIMIT_MIN = "soc_limit_min"
SOC_LIMIT_MAX = "soc_limit_max"

# Entities - commands in coordinator
CMD_CHARGE_MODE = "charge_mode"
CMD_SOC_MIN = "set_soc_min"
CMD_SOC_MAX = "set_soc_max"

# Entities attributes stored in coordinator->data
ENT_CHARGE_MODE = "ent_charge_mode"
ENT_SOC_LIMIT_MIN = "ent_soc_limit_min"
ENT_SOC_LIMIT_MAX = "ent_soc_limit_max"

# Charger modes

CHR_MODE_UNKNOWN = "UNKNOWN"
CHR_MODE_STOPPED = "STOPPED"
CHR_MODE_PVCHARGE = "PVCHARGE"
CHR_MODE_NORMAL = "NORMALCHARGE"

CHARGER_MODES = [CHR_MODE_UNKNOWN, CHR_MODE_STOPPED, CHR_MODE_PVCHARGE, CHR_MODE_NORMAL]
