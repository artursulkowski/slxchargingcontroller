""" module for charing manager"""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from datetime import timedelta, datetime
from collections.abc import Callable
from enum import Enum
from .slxcar import SLXCar
from typing import Any


# from bisect import bisect_left

import homeassistant.util.dt as dt_util
from .timer import SlxTimer
import logging


from .const import (
    CHARGER_MODES,
    CHR_MODE_UNKNOWN,
    CHR_MODE_STOPPED,
    CHR_MODE_PVCHARGE,
    CHR_MODE_NORMAL,
    CHR_METHOD_MANUAL,
    CHR_METHOD_ECO,
    CHR_METHOD_FAST,
)


CHARGING_EFFICIENCY: float = 0.80  # assumed efficiency of charging.

_LOGGER = logging.getLogger(__name__)


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

    def __init__(self, soc_before_energy: int, soc_after_energy: int):
        self._session_energy_history: list[tuple[datetime, float]] = []
        self._soc_information: tuple[datetime, float] = (None, None)
        self._session_energy_at_soc: float = None
        self._soc_before_energy = soc_before_energy
        self._soc_after_energy = soc_after_energy
        self._plug_connected: bool = False

    def _clear_history(self):
        self._session_energy_history.clear()
        self._session_energy_at_soc = None

    def connect_plug(self):
        self._plug_connected = True

    def disconnect_plug(self):
        self._plug_connected = False
        self._clear_history()

    def add_entry(self, new_session_energy: float) -> bool:
        # if plug is not connected skip adding energy to the storage
        if self._plug_connected is False:
            return False
        self._session_energy_history.append((dt_util.utcnow(), new_session_energy))
        return self.calculate_estimated_session()

    def update_soc(self, new_time: datetime, soc_level: float) -> bool:
        self._soc_information = (new_time, soc_level)
        return self.calculate_estimated_session()

    def calculate_estimated_session(self) -> bool:
        # few conditions need to be met to calculate ammount of energy
        if self._plug_connected is False:
            return False
        length_of_history = len(self._session_energy_history)

        # if no soc information is provided - we cannot estimate SOC
        if self._soc_information[0] is None:
            return False

        if length_of_history == 0:
            return False

        if length_of_history >= 2:
            # we approach finding SOC value in between session energy entries
            index: int = -1
            for i in range(length_of_history):
                # find first value stored after soc was checked
                if self._session_energy_history[i][0] >= self._soc_information[0]:
                    index = i
                    break
            if index > 0:
                lower_value = self._session_energy_history[index - 1]
                higher_value = self._session_energy_history[index]

                total_diff: timedelta = higher_value[0] - lower_value[0]
                partial_diff: timedelta = self._soc_information[0] - lower_value[0]
                factor: float = 0
                if total_diff.seconds > 0:
                    factor = partial_diff.seconds / total_diff.seconds
                self._session_energy_at_soc = lower_value[1] + factor * (
                    higher_value[1] - lower_value[1]
                )
                return True
        # if we've reached that place it means that we have only one session energy entry OR soc time if before/after energy entries.
        # if SOC was measured before first energy entry ( or after last energy entry)
        # we will assume that _session_energy_at_soc can be calculated if time difference is not bigger than predefined time

        # TODO - use slice notation "[-1:]"  OR  just [-1] to get the last element from the list (https://docs.python.org/2/tutorial/introduction.html#lists)
        if self._soc_information[0] <= self._session_energy_history[0][0]:
            soc_before: timedelta = (
                self._session_energy_history[0][0] - self._soc_information[0]
            )
            if soc_before < timedelta(seconds=self._soc_before_energy):
                self._session_energy_at_soc = self._session_energy_history[0][1]
                return True
        elif (
            self._soc_information[0]
            >= self._session_energy_history[length_of_history - 1][0]
        ):
            soc_after: timedelta = (
                self._soc_information[0]
                - self._session_energy_history[length_of_history - 1][0]
            )
            if soc_after < timedelta(seconds=self._soc_after_energy):
                self._session_energy_at_soc = self._session_energy_history[
                    length_of_history - 1
                ][1]
                return True
        return False

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

    def soc_validity(self) -> int:
        """returns for how long is SOC valid. Value in seconds >= 0"""
        soc_time = self._soc_information[0]
        if soc_time is None:
            return 0

        age_of_soc: timedelta = dt_util.utcnow() - soc_time
        remaining_valid: int = self._soc_before_energy - age_of_soc.seconds
        if remaining_valid < 0:
            return 0
        else:
            return remaining_valid


class SLXChargingManager:
    """Class for Charging Manager"""

    def __init__(self, hass: HomeAssistant, car_config: dict[str, Any]):
        self.hass = hass
        self._energy_tracker = SlxEnergyTracker(
            soc_before_energy=car_config[SLXCar.CONF_SOC_BEFORE_ENERGY],
            soc_after_energy=car_config[SLXCar.CONF_SOC_AFTER_ENERGY],
        )

        # status when car connected
        self._car_connected_status: CarConnectedStates = None
        self._plug_status: bool = None

        # configs
        self._battery_capacity: float = None

        # settings
        self._soc_minimum: float = None
        self._soc_maximum: float = None
        self._target_soc: float = None
        self._charge_method: str = None

        # calculated values
        self._attr_bat_energy_estimated: float = None
        self._attr_bat_soc_estimated: float = None
        self._attr_charging_session_duration: int = None
        self._attr_request_soc_update: int = 0

        self._evse_value: str = None

        # not exposed yet
        self._attr_charging_active: bool = False
        self._time_of_start_charging: datetime = None

        self._callback_energy_estimated: Callable[[float], None] = None
        self._callback_soc_requested: Callable[[int], None] = None
        self._callback_set_charger_mode: Callable[[str], None] = None

        # timers for controller
        soc_request_timeout = car_config[SLXCar.CONF_SOC_REQUEST_TIMEOUT]
        self.timer_soc_request_timeout = SlxTimer(
            self.hass,
            timedelta(seconds=soc_request_timeout),
            self.callback_soc_timeout,
        )

        soc_next_update = car_config[SLXCar.CONF_SOC_NEXT_UPDATE]
        self.timer_next_soc_request = SlxTimer(
            self.hass,
            timedelta(seconds=soc_next_update),
            self.callback_bat_update,
        )

    def cleanup(self):
        self.timer_soc_request_timeout.cancel_timer()
        self.timer_next_soc_request.cancel_timer()

    def set_energy_estimated_callback(self, ext_callback: Callable[[float], None]):
        self._callback_energy_estimated = ext_callback

    def set_soc_requested_callback(self, ext_callback: Callable[[int], None]):
        self._callback_soc_requested = ext_callback

    def set_charger_mode_callback(self, ext_callback: Callable[[str], None]):
        self._callback_set_charger_mode = ext_callback

    @property
    def battery_capacity(self):
        return self._battery_capacity

    @battery_capacity.setter
    def battery_capacity(self, new_bat_capacity: float):
        self._battery_capacity = new_bat_capacity

    @property
    def soc_minimum(self):
        return self._soc_minimum

    @soc_minimum.setter
    def soc_minimum(self, new_value: float):
        # TODO - I have in total 4 parameters which will have the same setter. Consider alternative solution (property decorator?)
        old_value = self._soc_minimum
        self._soc_minimum = new_value
        if old_value is not None and old_value != new_value:
            self.calculate_evse_state()

    @property
    def soc_maximum(self):
        return self._soc_maximum

    @soc_maximum.setter
    def soc_maximum(self, new_value: float):
        old_value = self._soc_maximum
        self._soc_maximum = new_value
        if old_value is not None and old_value != new_value:
            self.calculate_evse_state()

    @property
    def target_soc(self):
        return self._target_soc

    @target_soc.setter
    def target_soc(self, new_value: float):
        old_value = self._target_soc
        self._target_soc = new_value
        if old_value is not None and old_value != new_value:
            self.calculate_evse_state()

    @property
    def charge_method(self):
        return self._charge_method

    @charge_method.setter
    def charge_method(self, new_value: str):
        old_value = self._charge_method
        self._charge_method = new_value
        if (
            old_value is not None
            and old_value != new_value
            and new_value != CHR_METHOD_MANUAL
        ):
            self.calculate_evse_state()

    def set_soc_level(self, new_soc_level: float, new_soc_update: datetime = None):
        self.timer_soc_request_timeout.cancel_timer()

        soc_update_time = new_soc_update
        if soc_update_time is None:
            soc_update_time = dt_util.utcnow()

        can_calculate: bool = self._energy_tracker.update_soc(
            soc_update_time, new_soc_level
        )
        self.timer_next_soc_request.schedule_timer()
        if can_calculate is True:
            self.recalculate_energy()

    def add_charger_energy(self, new_charger_energy: float, new_time: datetime = None):
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
            self._car_connected_status = CarConnectedStates.soc_known
            self._callback_energy_estimated(self._attr_bat_energy_estimated)

        self.calculate_evse_state()

    def plug_connected(
        self, new_charger_energy: float = None, new_time: datetime = None
    ):
        """called when plug is connected"""
        _LOGGER.info("Plug connected")
        self._attr_charging_active = True

        self._energy_tracker.connect_plug()
        if new_charger_energy is not None:
            self._energy_tracker.add_entry(new_charger_energy)

        can_calculate = self._energy_tracker.calculate_estimated_session()
        if can_calculate:
            self._car_connected_status = CarConnectedStates.soc_known
            self.recalculate_energy()
            self.calculate_evse_state()
        else:
            self._car_connected_status = CarConnectedStates.ramping_up
            self.request_bat_soc_update()

    def plug_disconnected(self):
        """called when plug got disconnected"""
        _LOGGER.info("Plug disconnected")

        # Here we can prepare summary of charging session.

        self._attr_charging_active = False
        self._car_connected_status = None

        self._attr_bat_energy_estimated = None
        self._attr_bat_soc_estimated = None
        self._attr_charging_session_duration = None

        self._energy_tracker.disconnect_plug()

    def request_bat_soc_update(self):
        """Requests now for Battery SOC update"""
        self._attr_request_soc_update += 1

        _LOGGER.info("Request SOC update and start timeout for SOC update")
        self.timer_soc_request_timeout.schedule_timer()

        # notify coordinator that we want to get SOC Update
        if self._callback_soc_requested is not None:
            self._callback_soc_requested(self._attr_request_soc_update)
        else:
            _LOGGER.warning("Callback for SOC requested is not set up")

    def request_evse_set(self, evse_mode: str):
        # for evse mode use CHARGER_MODES
        _LOGGER.info("Request EVSE set to move %s", evse_mode)

        if self._callback_set_charger_mode is not None:
            self._callback_set_charger_mode(evse_mode)
        else:
            _LOGGER.warning("Callback for setting charger mode is not set up")

    @callback
    def callback_soc_timeout(self, _) -> None:
        """Callback for SLXTimer - called when SOC Update timeouts"""
        _LOGGER.info("SOC Update timeouted")
        self.timer_next_soc_request.schedule_timer()
        if self._car_connected_status is CarConnectedStates.ramping_up:
            self._car_connected_status = CarConnectedStates.autopilot
            self.calculate_evse_state()
            return

    @callback
    def callback_bat_update(self, _) -> None:
        """Callback for SLXTimer - called when we need to request another battery update"""
        _LOGGER.info("Timer - we need to request SOC Update")
        if self._attr_charging_active is True:
            self.request_bat_soc_update()

    def calculate_evse_state(self) -> None:
        """Method is called to recalculate if what state should the charger be depending on charging manager status"""
        new_evse_value: str = None

        _LOGGER.info("Calculate EVSE state")
        _LOGGER.debug("_car_connected_status: %s", self._car_connected_status)
        _LOGGER.debug("_charge_method: %s", self._charge_method)
        _LOGGER.debug("_attr_bat_soc_estimated: %.2f", self._attr_bat_soc_estimated)
        _LOGGER.debug(
            "_soc_minimum: %.1f, _soc_maximum: %.1f, _target_soc: %.1f",
            self._soc_minimum,
            self._soc_maximum,
            self._target_soc,
        )

        match self._car_connected_status:
            case CarConnectedStates.ramping_up:
                new_evse_value = (
                    None  # set none as "I don't know and I don't want to change"
                )

            case CarConnectedStates.autopilot:
                new_evse_value = CHR_MODE_NORMAL

            case CarConnectedStates.soc_known:
                # we can select normal,sleep or PV charge.

                if self._attr_bat_soc_estimated < self.soc_minimum:
                    new_evse_value = CHR_MODE_NORMAL
                elif self._attr_bat_soc_estimated < self.soc_maximum:
                    if self.charge_method == CHR_METHOD_ECO:
                        new_evse_value = CHR_MODE_PVCHARGE
                    if self.charge_method == CHR_METHOD_FAST:
                        if self._attr_bat_soc_estimated < self.target_soc:
                            new_evse_value = CHR_MODE_NORMAL
                        else:
                            new_evse_value = CHR_MODE_STOPPED
                else:  # soc >= soc_maximum
                    if self._attr_bat_soc_estimated > self.target_soc:
                        new_evse_value = CHR_MODE_STOPPED
                    else:
                        if self.charge_method == CHR_METHOD_FAST:
                            new_evse_value = CHR_MODE_NORMAL
                        if self.charge_method == CHR_METHOD_ECO:
                            new_evse_value = CHR_MODE_PVCHARGE

        if new_evse_value is None:
            _LOGGER.warning("Cannot define expected EVSE state")
            return  # nothing to do

        if self._evse_value is None or self._evse_value != new_evse_value:
            # we need to change charger setting
            _LOGGER.info(
                "Change EVSE state to %s (previous = %s)",
                new_evse_value,
                self._evse_value,
            )
            self._evse_value = new_evse_value
            self.request_evse_set(new_evse_value)
        else:
            _LOGGER.debug("EVSE state didn't change %s", new_evse_value)
