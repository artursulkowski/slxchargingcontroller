""" module for charing manager"""

from homeassistant.core import HomeAssistant, callback, CALLBACK_TYPE
from homeassistant.helpers.event import async_call_later
from datetime import timedelta, datetime
from collections.abc import Callable
from enum import Enum

SOC_REQUEST_TIMEOUT: int = 20  # seconds

NEXT_SOC_REQUEST_UPDATE: int = 60  # minutes


class CarConnectedStates(Enum):
    """Represent the current state when car is connected"""

    ramping_up = "RAMPING_UP"
    autopilot = "AUTOPILOT"
    soc_known = "SOC_KNOWN"

    def __str__(self) -> str:
        """Return the description"""
        return self.value


# class SessionEnergy
# TODO  create a class to store session energy
# Gather timestamps and information about session energy.
# calculate session energy for the
# High level cases:
# Gather session energy. Clear session energy.
# When provided with SOC update:
# - store SOC Value and it's time.
# - check if we can identify session energy for the moment of SOC Update. If we can:
#    - store SessionEnergy value for the moment of SOC Update.
# CalculateAddedSessionEnergy
#  - on top of SOC Update.
# Future use cases:
# Help calculate energy loses.
# Help calculate session summary?


class SlxTimer:
    def __init__(
        self,
        hass: HomeAssistant,
        logger,
        default_time: timedelta,
        timer_callback: Callable[[], None],
    ):
        self.hass = hass
        self.logger = logger
        self.wait_time: timedelta = default_time
        self.timer_callback = timer_callback
        self.unsub_callback: Callable[[], None] = None

    def schedule_timer(self, new_wait_time: timedelta = None):
        if self.unsub_callback is not None:
            self.unsub_callback()
            self.unsub_callback = None
            self.logger.debug("Cancel timer %s before scheduling again", __name__)
        wait_time_to_use = self.wait_time
        if new_wait_time is not None:
            wait_time_to_use = new_wait_time
        self.unsub_callback = async_call_later(
            self.hass, wait_time_to_use, self.timer_callback
        )

    def cancel_timer(self):
        if self.unsub_callback is not None:
            self.unsub_callback()
            self.unsub_callback = None
            self.logger.debug("Canceled timer %s", __name__)
        else:
            self.logger.debug("Ignore canceling timer %s", __name__)


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
        self._attr_bat_energy_estimated: float = None
        self._attr_bat_soc_estimated: float = None
        self._attr_charging_session_duration: int = None
        self._attr_request_soc_update: int = 0

        self._session_energy_history: list[tuple[datetime, float]] = []

        # not exposed yet
        self._attr_charging_active: bool = False
        self._time_of_start_charging: datetime = None

        self._callback_energy_estimated: Callable[[float]] = None
        self._callback_soc_requested: Callable[[int]] = None

        # timers for controller
        self.timer_soc_request_timeout = SlxTimer(
            self.hass,
            self.logger,
            timedelta(seconds=SOC_REQUEST_TIMEOUT),
            self.callback_soc_timeout,
        )

        self.timer_next_soc_request = SlxTimer(
            self.hass,
            self.logger,
            timedelta(minutes=NEXT_SOC_REQUEST_UPDATE),
            self.callback_bat_update,
        )

    def set_energy_estimated_callback(self, callback: Callable[[float]]):
        self._callback_energy_estimated = callback

    def set_soc_requested_callback(self, callback: Callable[[int]]):
        self._callback_soc_requested = callback

    @property
    def plug_status(self):
        return self._plug_status

    @plug_status.setter
    def plug_status(self, new_plug_status: bool):
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
        # in case we have car not connected - just ignore SOC updates.
        if self._attr_charging_active is False:
            return

        self.timer_soc_request_timeout.cancel_timer()
        self._soc_level = new_soc_level
        if new_soc_update is not None:
            self._soc_update = new_soc_level
        else:
            self._soc_update = datetime.now()
        self.timer_next_soc_request.schedule_timer()

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
        if self._attr_charging_active is True:
            self._session_energy_history.append((datetime.now(), new_charger_energy))
            self._charger_energy = new_charger_energy
        # This will require a change. How to calculate energy after car is disconnected.
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
        self._session_energy_history.clear()

        # Request BAT Soc Update
        self.request_bat_soc_update()

        self._time_of_start_charging = datetime.now()

    def plug_disconnected(self):
        """called when plug got disconnected"""
        self.logger.debug("Charging stopped")
        self._attr_charging_active = False
        self._car_connected_status = None
        # Here we can prepare summary of charging session.

    def request_bat_soc_update(self):
        """Requests now for Battery SOC update"""
        self._attr_request_soc_update += 1

        self.logger.debug("start timeout for SOC update")
        self.timer_soc_request_timeout.schedule_timer()

        # notify coordinator that we want to get SOC Update
        if self._callback_soc_requested is not None:
            self._callback_soc_requested(self._attr_request_soc_update)
        else:
            self.logger.warning("Callback for SOC requested is not set up")

    @callback
    def callback_soc_timeout(self, _) -> None:
        """Callback for SLXTimer - called when SOC Update timeouts"""
        self.logger.debug("callback_soc_timeout")
        self.timer_next_soc_request.schedule_timer()
        if self._car_connected_status is CarConnectedStates.ramping_up:
            self._car_connected_status = CarConnectedStates.autopilot
            return

    @callback
    def callback_bat_update(self, _) -> None:
        """Callback for SLXTimer - called when we need to request another battery update"""
        self.logger.debug("callback_bat_update")
        if self._attr_charging_active is True:
            self.request_bat_soc_update()
