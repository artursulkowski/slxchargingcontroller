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

## Entities number
# Keys
SOC_LIMIT_MIN = "soc_limit_min"
SOC_LIMIT_MAX = "soc_limit_max"
SOC_TARGET = "soc_target"

# Commands in coordinator
CMD_SOC_MIN = "set_soc_min"
CMD_SOC_MAX = "set_soc_max"
CMD_SOC_TARGET = "set_soc_target"

# Attributes stored in coordinator->data
ENT_SOC_LIMIT_MIN = "ent_soc_limit_min"
ENT_SOC_LIMIT_MAX = "ent_soc_limit_max"
ENT_SOC_TARGET = "ent_soc_target"

## Entities select
# Keys
KEY_CHARGE_MODE = "charge_mode"
KEY_CHARGE_METHOD = "charge_method"

# Commands in coordinator
CMD_CHARGE_MODE = "set_charger_select"
CMD_CHARGE_METHOD = "set_charge_method"

# Attributes stored in coordinator->data
ENT_CHARGE_MODE = "ent_charge_mode"
ENT_CHARGE_METHOD = "ent_charge_method"


# Charger modes - which mode is selected on physical charger.
CHR_MODE_UNKNOWN = "UNKNOWN"
CHR_MODE_STOPPED = "STOPPED"
CHR_MODE_PVCHARGE = "PVCHARGE"
CHR_MODE_NORMAL = "NORMALCHARGE"
CHARGER_MODES = [CHR_MODE_UNKNOWN, CHR_MODE_STOPPED, CHR_MODE_PVCHARGE, CHR_MODE_NORMAL]

# Selected charging method - suggestion to SlxCharging controller which method it should use if charging is needed.
# Do not mix this with Charger mode which is current mode selected on EVSE
CHR_METHOD_ECO = "ECO"
CHR_METHOD_FAST = "FAST"
CHR_METHOD_MANUAL = "MANUAL"
CHARGE_METHODS = [CHR_METHOD_ECO, CHR_METHOD_FAST, CHR_METHOD_MANUAL]
