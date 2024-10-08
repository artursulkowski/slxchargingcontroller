"""Module for charging planning.

Modules gathers information about expected solar production, electricity prices and expected trips.
Based on this it calculates the optimum charging times and sources.


For final checking we need a flat list of data (like cost).



"""

from datetime import date, datetime, timedelta, time, timezone
from dataclasses import dataclass
import logging
from typing import Any

import pulp
# 2.9.0 version

from homeassistant.core import Callable, Event, HomeAssistant
import homeassistant.util.dt as dt_util


_LOGGER = logging.getLogger(__name__)

SOLAR_FORECAST_FILL_IN = 0
ENERGY_COST_FILL_IN = None


@dataclass
class SLXSolarParameter:
    bottom_cutoff: float
    """in kW"""
    upper_cutoff: float
    """in kW"""
    efficiency: float
    """as a coefficient, e.g. 0.8. It cumulates with general charging efficiency!"""


@dataclass
class SLXChargingConfig:
    charging_efficiency: float
    """coefficient - e.g. 0.8"""

    batery_capacity: float
    """in kWh"""

    bottom_buffer: float
    """in kWh, minimum energy that should be left after planned daily drive"""

    energy_consumption: float
    """in kWh/km, car's energy consumption """

    morning_start_utc: int


class SLXChargingPlanner:
    def __init__(
        self,
        hass: HomeAssistant,
        solar_parameter: SLXSolarParameter | None = None,
        charging_config: SLXChargingConfig | None = None,
    ) -> None:
        """Creates empty planned object."""

        self.hass = hass

        self._number_of_timeslots: int = 96

        # includes hours which we will be processing.
        self._time_slots: list[datetime] = []
        self._solar_forecasts: list[datetime] = []
        self._energy_costs: list[datetime] = []

        # Now the constraints! how much energy is needed in the battery

        # PROBABLY TO REMOVE
        # here we use different approach - we provide the time by which given energy level needs to be achieved
        # we will calculate both datetime and the amount of energy mainly based on planned trips.
        # by mapping upcoming days into exact datetime we can also define easily which hour do we treat as the begin of the day(e.g. 6AM)
        # energy in kWh
        self._energy_needed_in_bat: list[tuple[datetime, float]] = []

        # energy in kWh - for the current hour
        self._energy_in_bat_now: float | None = None

        # Boundle of lists that stores information about energy requirements
        self._energy_consumed_trimmed: list[tuple[datetime, float]] = []
        """Energy to be consumed that specifc day. Datetime defines time in the morning when the car should be already charged. Trimmed - means that batter capacity is taken into consideration as the upper limit."""

        self._cumulative_energy_min_max: list[tuple[datetime, float, float]] = []
        """ """

        # TO REMOVE
        # this will be used to define constraints in calculations!
        # takes into consideration any energy loses.
        # self._min_energy_to_be_added: list[tuple[datetime, float]] = []

        # that one can be probably ignored for now.
        # self._max_energy_to_be_added: list(tuple(datetime, float)) = []

        # parameters of solar forecast to real charging capabilities
        if solar_parameter is not None:
            self._solar_parameters = solar_parameter
        else:
            self._solar_parameters = SLXSolarParameter(
                bottom_cutoff=1.4, upper_cutoff=4, efficiency=0.7
            )

        if charging_config is not None:
            self._charging_config = charging_config
        else:
            self._charging_config = SLXChargingConfig(
                charging_efficiency=0.8,
                batery_capacity=64,
                bottom_buffer=12.8,
                energy_consumption=0.18,
                morning_start_utc=3,
            )

    def update_time_slots(self, currenttime: datetime):
        # dt_util.now()

        new_start_time = self._round_to_hour_utc(currenttime)

        index = self._find_index_in_timeslots(new_start_time)
        if index == 0:
            # nothing to do
            return

        if index == -1:
            # we re-create timeslots, there are no values which we can reuse
            self._time_slots = [
                new_start_time + timedelta(hours=i)
                for i in range(self._number_of_timeslots)
            ]

            # clean other related values.
            ## I should fill it in!
            self._solar_forecasts = [SOLAR_FORECAST_FILL_IN] * self._number_of_timeslots
            self._energy_costs = [ENERGY_COST_FILL_IN] * self._number_of_timeslots

        else:
            # we already have timeslots defined. So now it is a matter of how much do we need to "shift"
            # Additionally we will need to add new timeslots
            # we are calculating of "how much to shift " and then we also shift solar forecast and energy cost

            ts_length = len(self._time_slots)
            if ts_length != self._number_of_timeslots:
                _LOGGER.error("Something is wrong!")

            self._time_slots = self._time_slots[index:]
            # fill in the remaining time slots
            index_to_start = ts_length - index
            for current_index in range(index_to_start, ts_length):
                self._time_slots.append(new_start_time + timedelta(hours=current_index))

            # shift and fill in existing forecasts

            self.shift_solar_forecast(index)
            self.shift_energy_cost(index)

    def shift_solar_forecast(self, index: int):
        initial_len = len(self._solar_forecasts)
        index_to_start = initial_len - index

        self._solar_forecasts = self._solar_forecasts[index:]
        for i in range(index_to_start, initial_len):
            self._solar_forecasts.append(SOLAR_FORECAST_FILL_IN)

    def shift_energy_cost(self, index: int):
        initial_len = len(self._energy_costs)
        index_to_start = initial_len - index
        self._energy_costs = self._energy_costs[index:]
        for i in range(index_to_start, initial_len):
            self._energy_costs.append(ENERGY_COST_FILL_IN)

    def fill_in_solar_forecast(self, solar_forecast: dict[datetime, float]):
        """Fill in solar forecast information.

        The steps conducted
        1. Fill-in solar_forecast with empty values
        2. Go through input entries, takes time and - finds relevant index and update in solar forecast
            a. ignore entries which are not full hours.
        """

        length = len(self._time_slots)
        if length == 0:
            self._solar_forecasts.clear()
            return

        self._solar_forecasts = [SOLAR_FORECAST_FILL_IN] * length

        for dt, watts in solar_forecast.items():
            if not self._isfullhour(dt):
                continue
            rounded = self._round_to_hour_utc(dt)
            index = self._find_index_in_timeslots(rounded)
            if index != -1:
                charging_power = self._solar_to_charging_power_kw(watts)
                self._solar_forecasts[index] = charging_power

    def fill_in_energy_cost(self, energy_cost: dict[datetime, float]):
        length = len(self._time_slots)
        if length == 0:
            self._energy_costs.clear()
            return
        self._energy_costs = [ENERGY_COST_FILL_IN] * length

        for dt, cost in energy_cost.items():
            if not self._isfullhour(dt):
                continue
            rounded = self._round_to_hour_utc(dt)
            index = self._find_index_in_timeslots(rounded)
            if index != -1:
                self._energy_costs[index] = cost

    def calculate_energy_needed(self, planned_distances: list[tuple[date, float]]):
        if self._energy_in_bat_now is None:
            return
        if len(self._time_slots) == 0:
            return

        self._energy_consumed_trimmed.clear()
        self._cumulative_energy_min_max.clear()

        for day, distance in planned_distances:
            exact_time = datetime.combine(
                day, time.min, tzinfo=timezone.utc
            ) + timedelta(hours=self._charging_config.morning_start_utc)
            if exact_time < self._time_slots[0]:
                continue

            energy_to_be_consumed_that_day = (
                distance * self._charging_config.energy_consumption
            )

            energy_consumed_trimmed = min(
                energy_to_be_consumed_that_day,
                self._charging_config.batery_capacity
                - self._charging_config.bottom_buffer,
            )
            self._energy_consumed_trimmed.append((exact_time, energy_consumed_trimmed))

        min_energy_sum: float = 0
        max_energy_sum: float = 0
        for exact_time, energy_consumed_trimmed in self._energy_consumed_trimmed:
            min_energy_sum += energy_consumed_trimmed

            to_store_min_energy_cumulatively = (
                min_energy_sum / self._charging_config.charging_efficiency
                + self._charging_config.bottom_buffer
                - self._energy_in_bat_now
            )
            to_store_max_energy_cumulatively = (
                max_energy_sum / self._charging_config.charging_efficiency
                + self._charging_config.batery_capacity
                - self._energy_in_bat_now
            )
            max_energy_sum += energy_consumed_trimmed  # that is "one day later"

            self._cumulative_energy_min_max.append(
                (
                    exact_time,
                    to_store_min_energy_cumulatively,
                    to_store_max_energy_cumulatively,
                )
            )

    def _isfullhour(self, dt: datetime) -> bool:
        return dt.minute == 0 and dt.second == 0 and dt.microsecond == 0

    def _round_to_hour_utc(self, dt: datetime) -> datetime:
        rounded_dt = dt.replace(minute=0, second=0, microsecond=0)
        return dt_util.as_utc(rounded_dt)

    def _find_index_in_timeslots(self, dt: datetime) -> int:
        if len(self._time_slots) == 0:
            return -1
        dt_rounded = self._round_to_hour_utc(dt)
        try:
            return self._time_slots.index(dt_rounded)
        except ValueError:
            return -1

    def _solar_to_charging_power_kw(self, solar_forecast: float) -> float:
        usable_kw = solar_forecast * self._solar_parameters.efficiency / 1000.0
        if usable_kw < self._solar_parameters.bottom_cutoff:
            usable_kw = 0
        elif usable_kw > self._solar_parameters.upper_cutoff:
            usable_kw = self._solar_parameters.upper_cutoff
        return usable_kw
