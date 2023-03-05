""" module for charing manager"""

from homeassistant.core import HomeAssistant
from datetime import timedelta, datetime
from collections.abc import Callable


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
        self._plug_status: bool = None

        # configs
        self._battery_capacity: float = None

        # calculated values
        # self._energy_measured: float | None = None
        self._attr_bat_energy_estimated: float = None
        self._attr_bat_soc_estimated: float = None
        self._attr_charging_session_duration: int = None
        self._attr_request_soc_update: int = 0

        # not exposed yet
        self._attr_charging_active: bool = False
        self._time_of_start_charging: datetime = None

        self._callback_energy_estimated: Callable[[float]] = None

    def set_energy_estimated_callback(self, callback: Callable[[float]]):
        self._callback_energy_estimated = callback

    @property
    def plug_status(self):
        return self._plug_status

    @plug_status.setter
    def plug_status(self, new_plug_status: bool):
        # TODO - add start of the session
        if self._plug_status == new_plug_status:
            return
        if new_plug_status is True:
            self.started_charging()
        elif new_plug_status is False:
            self.stopped_charging()
        self._plug_status = new_plug_status

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

    @property
    def charger_energy(self):
        return self._charger_energy

    def add_charger_energy(self, new_charger_energy: float, new_time: datetime = None):
        self._charger_energy = new_charger_energy
        if self._charger_energy is not None:
            self.recalculate_energy()
        self._charger_energy_time = new_time

    @charger_energy.setter
    def charger_energy(self, new_charger_energy: float):
        # in more advanced version we will be adding
        self._charger_energy = new_charger_energy
        if self._charger_energy is not None:
            self.recalculate_energy()

    def recalculate_energy(self):
        if not self.has_enough_info():
            return None

        # this is incorrect algorithm once SOC will be updated during a charging session.

        self._attr_bat_energy_estimated = (
            self._soc_level / 100.0
        ) * self._battery_capacity + self._charger_energy
        self._attr_bat_soc_estimated = (
            self._attr_bat_energy_estimated * 100 / self.battery_capacity
        )
        if self._callback_energy_estimated is not None:
            # passing estimated energy to callback - however - this values is not used directly (to be removed)
            self._callback_energy_estimated(self._attr_bat_energy_estimated)

    def has_enough_info(self) -> bool:
        if self._soc_level is None:
            return False
        # for now - ignore SOC time
        # if self._soc_update is None:
        #     return False
        if self._charger_energy is None:
            return False
        return True

    def started_charging(self):
        """called when charging has started (plug connected)"""
        self.logger.debug("Charging started")
        self._attr_charging_active = True

        ## gather a number of data related to charging session
        # TODO - should this be combined into dataclass?
        self._time_of_start_charging = datetime.now()
        # do not store charging session energy yet! This should be updated once new value is received!

    def stopped_charging(self):
        """called when charging has stoped (plug disconnected)"""
        self.logger.debug("Charging stopped")
        self._attr_charging_active = False

        # TODO - prepare summary of charging session?
