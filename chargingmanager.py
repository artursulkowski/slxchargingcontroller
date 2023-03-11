""" module for charing manager"""

from homeassistant.core import HomeAssistant, callback, CALLBACK_TYPE
from homeassistant.helpers.event import async_call_later
from datetime import timedelta, datetime
from collections.abc import Callable
from enum import Enum


SOC_REQUEST_TIMEOUT: int = 20


class CarConnectedStates(Enum):
    """Represent the current state when car is connected"""

    ramping_up = "RAMPING_UP"
    autopilot = "AUTOPILOT"
    soc_known = "SOC_KNOWN"

    def __str__(self) -> str:
        """Return the description"""
        return self.value


class SLXChargingManager:
    """Class for Charging Manager"""

    def __init__(self, hass: HomeAssistant, logger):
        self.hass = hass
        self.logger = logger

        # status when car connected
        self._car_connected_status: CarConnectedStates = None

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
        self._callback_soc_requested: Callable[[int]] = None

    def set_energy_estimated_callback(self, callback: Callable[[float]]):
        self._callback_energy_estimated = callback

    def set_soc_requested_callback(self, callback: Callable[[int]]):
        self._callback_soc_requested = callback

    @property
    def plug_status(self):
        return self._plug_status

    @plug_status.setter
    def plug_status(self, new_plug_status: bool):
        # TODO - add start of the session
        if self._plug_status == new_plug_status:
            return
        if new_plug_status is True:
            self.plug_connected()
        elif new_plug_status is False:
            self.plug_disconnected()
        self._plug_status = new_plug_status

    @property
    def battery_capacity(self):
        return self._battery_capacity

    @battery_capacity.setter
    def battery_capacity(self, new_bat_capacity: float):
        self._battery_capacity = new_bat_capacity

    def set_soc_level(self, new_soc_level: float, new_soc_update: datetime = None):
        self._soc_level = new_soc_level
        if new_soc_update is not None:
            self._soc_update = new_soc_level
        else:
            self._soc_update = datetime.now()

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
        if self._charger_energy is None:
            return False
        return True

    def plug_connected(self):
        """called when plug is connected"""
        self.logger.debug("Charging started")
        self._attr_charging_active = True
        self._car_connected_status = CarConnectedStates.ramping_up

        # Request BAT Soc Update
        self.request_bat_soc_update(SOC_REQUEST_TIMEOUT)

        ## gather a number of data related to charging session
        # TODO - should this be combined into dataclass?
        self._time_of_start_charging = datetime.now()
        # do not store charging session energy yet! This should be updated once new value is received!

    def plug_disconnected(self):
        """called when plug got disconnected"""
        self.logger.debug("Charging stopped")
        self._attr_charging_active = False
        self._car_connected_status = None
        # TODO - prepare summary of charging session?

    def request_bat_soc_update(self, timeout: int):
        """Requests now for Battery SOC update"""
        self._attr_request_soc_update += 1
        self._soc_request_active = True

        self.logger.debug("start timeout for SOC update")
        async_call_later(
            self.hass,
            timedelta(seconds=timeout),  # not sure if this is provided in seconds?
            self.callback_soc_timeout,
        )

        if self._callback_soc_requested is not None:
            self._callback_soc_requested(self._attr_request_soc_update)
        else:
            self.logger.warning("Callback for SOC requested is not set up")

    @callback
    def callback_soc_timeout(self, _) -> None:
        self.logger.debug("callback_soc_timeout")
        if self._soc_request_active is False:
            return  # just ignore timeout

        self._soc_request_active = False

        if self._car_connected_status is CarConnectedStates.ramping_up:
            self._car_connected_status = CarConnectedStates.autopilot
            return

    def schedule_bat_soc_update(self, wait_minutes: int):
        async_call_later(
            self.hass,
            timedelta(minutes=wait_minutes),  # not sure if this is provided in seconds?
            self.callback_bat_update,
        )

    @callback
    def callback_bat_update(self, _) -> None:
        """called when we need to request another battery update"""
        self.logger.debug("callback_bat_update")
        # TODO - check if we are in the correct state to request battery update!
