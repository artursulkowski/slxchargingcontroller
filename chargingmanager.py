""" module for charing manager"""

from homeassistant.core import HomeAssistant
from datetime import timedelta, datetime


class SLXChargingManager:
    """Class for Charging Manager"""

    def __init__(self, hass: HomeAssistant, logger):
        self.hass = hass
        self.logger = logger

        # variable during charging process
        self._soc_level: float = None
        self._soc_update: datetime = None
        self._charger_energy: float = None
        self._charger_energy_time: datetime = None
        self._plug: bool = None

        # configs
        self._battery_capacity: float = None

        # calculated values
        # self._energy_measured: float | None = None
        self._energy_estimated: float = None

    @property
    def battery_capacity(self):
        return self._battery_capacity

    @battery_capacity.setter
    def battery_capacity(self, new_bat_capacity: float):
        self._battery_capacity = new_bat_capacity

    @property
    def soc_level(self):
        return self._soc_level

    # Set as a percentage
    @soc_level.setter
    def soc_level(self, new_soc_level: float):
        self._soc_level = new_soc_level
        if self._soc_level is not None:
            self.recalculate_energy()

    def recalculate_energy(self):
        if not self.has_enough_info():
            return None

        # this is incorrect algorithm once SOC will be updated during a charging session.

        self._energy_estimated = (
            self._soc_level / 100.0
        ) * self._battery_capacity + self._charger_energy

    def has_enough_info(self) -> bool:
        if self._soc_level is None:
            return False
        if self._soc_update is None:
            return False
        if self._charger_energy is None:
            return False
        return True


#      _ev_driving_range: float = None
# def ev_driving_range(self):
#     return self._ev_driving_range

# @ev_driving_range.setter
# def ev_driving_range(self, value):
#     self._ev_driving_range_value = value[0]
#     self._ev_driving_range_unit = value[1]
#     self._ev_driving_range = value[0]
