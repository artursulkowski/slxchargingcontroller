""" module for charing manager"""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from datetime import timedelta, datetime
from collections.abc import Callable
from enum import Enum

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
    CHR_MODE_UNKNOWN,
    CHR_METHOD_MANUAL,
    CHR_METHOD_ECO,
    CHR_METHOD_FAST,
)

SOC_REQUEST_TIMEOUT: int = 120  # seconds
NEXT_SOC_REQUEST_UPDATE: int = 60  # minutes
CHARGING_EFFICIENCY: float = 0.80  # assumed efficiency of charging.
SOC_BEFORE_ENERGY: int = 600  # seconds
SOC_AFTER_ENERGY: int = (
    3600 * 4
)  # seconds - we accept a difference of up to 4 hours. Bigger indicates that something terribly wrong was happening and we should not treat values as relevant.

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

    def __init__(self):
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
        # few conditions need to be met to calculate ammount of energy
        length_of_history = len(self._session_energy_history)

        # if no soc information is provided - we cannot estimate SOC
        if self._soc_information[0] is None:
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
                factor: float = partial_diff.seconds / total_diff.seconds
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
            if soc_before < timedelta(seconds=SOC_BEFORE_ENERGY):
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
            if soc_after < timedelta(seconds=SOC_AFTER_ENERGY):
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


class SLXChargingManager:
    """Class for Charging Manager"""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._energy_tracker = SlxEnergyTracker()

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
        self.timer_soc_request_timeout = SlxTimer(
            self.hass,
            timedelta(seconds=SOC_REQUEST_TIMEOUT),
            self.callback_soc_timeout,
        )

        self.timer_next_soc_request = SlxTimer(
            self.hass,
            timedelta(minutes=NEXT_SOC_REQUEST_UPDATE),
            self.callback_bat_update,
        )

    def set_energy_estimated_callback(self, callback: Callable[[float], None]):
        self._callback_energy_estimated = callback

    def set_soc_requested_callback(self, callback: Callable[[int], None]):
        self._callback_soc_requested = callback

    def set_charger_mode_callback(self, callback: Callable[[str], None]):
        self._callback_set_charger_mode = callback

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
        # in case we have car not connected - just ignore SOC updates.
        if self._attr_charging_active is False:
            return

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
            self._car_connected_status = CarConnectedStates.soc_known
            self._callback_energy_estimated(self._attr_bat_energy_estimated)

        self.calculate_evse_state()

    def plug_connected(self):
        """called when plug is connected"""
        _LOGGER.info("Plug connected")
        self._attr_charging_active = True
        self._car_connected_status = CarConnectedStates.ramping_up
        self._energy_tracker.clear_history()

        # Request Bat SOC Update
        self.request_bat_soc_update()

        self._time_of_start_charging = dt_util.utcnow()

    def plug_disconnected(self):
        """called when plug got disconnected"""
        _LOGGER.info("Plug disconnected")
        self._attr_charging_active = False
        self._car_connected_status = None
        # Here we can prepare summary of charging session.

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
        _LOGGER.info("callback_soc_timeout")
        self.timer_next_soc_request.schedule_timer()
        if self._car_connected_status is CarConnectedStates.ramping_up:
            self._car_connected_status = CarConnectedStates.autopilot
            return

    @callback
    def callback_bat_update(self, _) -> None:
        """Callback for SLXTimer - called when we need to request another battery update"""
        _LOGGER.info("callback_bat_update")
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
