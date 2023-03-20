""" module for charing manager"""

from homeassistant.core import HomeAssistant, callback, CALLBACK_TYPE
from homeassistant.helpers.event import async_call_later
from datetime import timedelta, datetime
from collections.abc import Callable
from enum import Enum
from bisect import bisect_left

import homeassistant.util.dt as dt_util


SOC_REQUEST_TIMEOUT: int = 120  # seconds
NEXT_SOC_REQUEST_UPDATE: int = 60  # minutes
CHARGING_EFFICIENCY: float = 0.80  # assumed efficiency of charging.


class CarConnectedStates(Enum):
    """Represent the current state when car is connected"""

    ramping_up = "RAMPING_UP"
    autopilot = "AUTOPILOT"
    soc_known = "SOC_KNOWN"

    def __str__(self) -> str:
        """Return the description"""
        return self.value


class SlxEnergyTracker:
    """Class for tracking energy transferred during charging session

    Prepare more detailed description using https://peps.python.org/pep-0257/
    """

    def __init__(self, logger):
        self.logger = logger
        self._session_energy_history: list[tuple[datetime, float]] = []
        self._soc_information: tuple[datetime, float] = (None, None)
        self._session_energy_at_soc: float = None

    def clear_history(self):
        self._session_energy_history.clear()
        self._session_energy_at_soc = None

    def add_entry(self, new_session_energy: float) -> bool:
        self._session_energy_history.append((dt_util.utcnow(), new_session_energy))
        return self.calculate_estimated_session()

    def update_soc(self, new_time: datetime, soc_level: float) -> bool:
        self._soc_information = (new_time, soc_level)
        return self.calculate_estimated_session()

    def calculate_estimated_session(self) -> bool:
        # few conditions need to be met..
        length_of_history = len(self._session_energy_history)
        if length_of_history < 2:
            return False
        if self._soc_information[0] is None:
            return False
        index: int = -1
        for i in range(length_of_history):
            if self._session_energy_history[i][0] >= self._soc_information[0]:
                index = i
                break
        if index <= 0:
            return False

        lower_value = self._session_energy_history[index - 1]
        higher_value = self._session_energy_history[index]

        total_diff: timedelta = higher_value[0] - lower_value[0]
        partial_diff: timedelta = self._soc_information[0] - lower_value[0]
        factor: float = partial_diff.seconds / total_diff.seconds
        self._session_energy_at_soc = lower_value[1] + factor * (
            higher_value[1] - lower_value[1]
        )
        return True

    def get_added_energy(self) -> float:
        """Returns energy added since SOC was checked"""
        if self._session_energy_at_soc is None:
            return None
        history_len = len(self._session_energy_history)
        if history_len == 0:
            return None

        added_energy: float = (
            self._session_energy_history[history_len - 1][1]
            - self._session_energy_at_soc
        )
        return added_energy

    # def get_stored_soc(self) -> tuple(datetime,float):
    def get_stored_soc(self) -> float:
        return self._soc_information[1]

    # Version with bisect_left will be usable after switching to newer HA version (python 3.10)
    # For now I will use very primitive search)
    # def calculate_estimated_session(self) -> bool:
    #     # few conditions need to be met..
    #     if len(self._session_energy_history) < 2:
    #         return False
    #     index = bisect_left(
    #         self._session_energy_history,
    #         self._soc_information,
    #         key=extract_datetime,
    #         # key=lambda item: item[0],
    #     )


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

        self._energy_tracker = SlxEnergyTracker(self.logger)

        # status when car connected
        self._car_connected_status: CarConnectedStates = None
        self._plug_status: bool = None

        # configs
        self._battery_capacity: float = None

        # calculated values
        self._attr_bat_energy_estimated: float = None
        self._attr_bat_soc_estimated: float = None
        self._attr_charging_session_duration: int = None
        self._attr_request_soc_update: int = 0

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

        soc_update_time = new_soc_update
        if soc_update_time is None:
            soc_update_time = dt_util.utcnow()

        self._energy_tracker.update_soc(soc_update_time, new_soc_level)
        self.timer_next_soc_request.schedule_timer()

    def add_charger_energy(self, new_charger_energy: float, new_time: datetime = None):
        # Ignore charger information if car is not connected
        if self._attr_charging_active is not True:
            return
        can_calculate: bool = self._energy_tracker.add_entry(new_charger_energy)
        if can_calculate is True:
            self.recalculate_energy()

    def recalculate_energy(self):
        added_energy = self._energy_tracker.get_added_energy()
        if added_energy is None:
            return False

        soc_checked = self._energy_tracker.get_stored_soc()
        if soc_checked is None:
            return False

        self._attr_bat_energy_estimated = (
            soc_checked / 100.0
        ) * self._battery_capacity + added_energy * CHARGING_EFFICIENCY
        self._attr_bat_soc_estimated = (
            self._attr_bat_energy_estimated * 100 / self.battery_capacity
        )
        if self._callback_energy_estimated is not None:
            # passing estimated energy to callback - however - this values is not used directly (to be removed)
            self._callback_energy_estimated(self._attr_bat_energy_estimated)

    def plug_connected(self):
        """called when plug is connected"""
        self.logger.debug("Charging started")
        self._attr_charging_active = True
        self._car_connected_status = CarConnectedStates.ramping_up
        self._energy_tracker.clear_history()

        # Request Bat SOC Update
        self.request_bat_soc_update()

        self._time_of_start_charging = dt_util.utcnow()

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
