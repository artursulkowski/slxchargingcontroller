from datetime import date, datetime
from math import isclose
from unittest.mock import patch
from typing import Tuple, Sequence

from freezegun.api import FrozenDateTimeFactory, freeze_time

from custom_components.slxchargingcontroller.slxchargingplanner import (
    SLXChargingPlanner,
    SLXSolarParameter,
    SLXChargingConfig,
)
from homeassistant.core import HomeAssistant
# from homeassistant.helpers import storage


solar_prediction_test1 = {
    datetime.fromisoformat("2024-09-15T06:27:28+02:00"): 0,
    datetime.fromisoformat("2024-09-15T07:00:00+02:00"): 537,
    datetime.fromisoformat("2024-09-15T08:00:00+02:00"): 979,
    datetime.fromisoformat("2024-09-15T09:00:00+02:00"): 1352,
    datetime.fromisoformat("2024-09-15T10:00:00+02:00"): 1659,
    datetime.fromisoformat("2024-09-15T11:00:00+02:00"): 1916,
    datetime.fromisoformat("2024-09-15T12:00:00+02:00"): 2060,
    datetime.fromisoformat("2024-09-15T13:00:00+02:00"): 2092,
    datetime.fromisoformat("2024-09-15T14:00:00+02:00"): 1979,
    datetime.fromisoformat("2024-09-15T15:00:00+02:00"): 1749,
    datetime.fromisoformat("2024-09-15T16:00:00+02:00"): 1421,
    datetime.fromisoformat("2024-09-15T17:00:00+02:00"): 1052,
    datetime.fromisoformat("2024-09-15T18:00:00+02:00"): 656,
    datetime.fromisoformat("2024-09-15T19:00:00+02:00"): 378,
    datetime.fromisoformat("2024-09-15T19:07:09+02:00"): 0,
    datetime.fromisoformat("2024-09-16T06:29:07+02:00"): 0,
    datetime.fromisoformat("2024-09-16T07:15:00+02:00"): 398,
    datetime.fromisoformat("2024-09-16T08:00:00+02:00"): 820,
    datetime.fromisoformat("2024-09-16T09:00:00+02:00"): 1298,
    datetime.fromisoformat("2024-09-16T10:00:00+02:00"): 1693,
    datetime.fromisoformat("2024-09-16T11:00:00+02:00"): 1922,
    datetime.fromisoformat("2024-09-16T12:00:00+02:00"): 2133,
    datetime.fromisoformat("2024-09-16T13:00:00+02:00"): 2250,
    datetime.fromisoformat("2024-09-16T14:00:00+02:00"): 2089,
    datetime.fromisoformat("2024-09-16T15:00:00+02:00"): 1739,
    datetime.fromisoformat("2024-09-16T16:00:00+02:00"): 1291,
    datetime.fromisoformat("2024-09-16T17:00:00+02:00"): 840,
    datetime.fromisoformat("2024-09-16T19:04:46+02:00"): 0,
}

solar_prediction_output = [
    0.537,
    0.979,
    1.352,
    1.659,
    1.916,
    2.06,
    2.092,
    1.979,
    1.749,
    1.421,
    1.052,
    0.656,
    0.378,  # 19:00
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,  # 0:00
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,  # 7:00
    0.82,  # 8:00
    1.298,
    1.693,
    1.922,
    2.133,
    2.25,
    2.089,
    1.739,
    1.291,
    0.84,
]


energy_cost_test1 = {
    datetime.fromisoformat("2024-09-15T06:00:00+02:00"): 0.500,
    datetime.fromisoformat("2024-09-15T07:00:00+02:00"): 0.650,
    datetime.fromisoformat("2024-09-15T08:00:00+02:00"): 0.900,
    datetime.fromisoformat("2024-09-15T09:00:00+02:00"): 1.200,
    datetime.fromisoformat("2024-09-15T10:00:00+02:00"): 0.900,
    datetime.fromisoformat("2024-09-15T11:00:00+02:00"): 0.850,
    datetime.fromisoformat("2024-09-15T12:00:00+02:00"): 0.450,
    datetime.fromisoformat("2024-09-15T13:00:00+02:00"): 0.300,
    datetime.fromisoformat("2024-09-15T14:00:00+02:00"): 0.200,
    datetime.fromisoformat("2024-09-15T15:00:00+02:00"): 0.450,
    datetime.fromisoformat("2024-09-15T16:00:00+02:00"): 0.750,
    datetime.fromisoformat("2024-09-15T17:00:00+02:00"): 1.100,
    datetime.fromisoformat("2024-09-15T18:00:00+02:00"): 1.450,
    datetime.fromisoformat("2024-09-15T19:00:00+02:00"): 1.550,
    datetime.fromisoformat("2024-09-15T20:00:00+02:00"): 1.400,
    datetime.fromisoformat("2024-09-15T21:00:00+02:00"): 0.900,
    datetime.fromisoformat("2024-09-15T22:00:00+02:00"): 0.700,
    datetime.fromisoformat("2024-09-15T23:00:00+02:00"): 0.600,
    datetime.fromisoformat("2024-09-16T00:00:00+02:00"): 0.300,
    datetime.fromisoformat("2024-09-16T01:00:00+02:00"): -0.010,
    datetime.fromisoformat("2024-09-16T02:00:00+02:00"): -0.050,
    datetime.fromisoformat("2024-09-16T03:00:00+02:00"): -0.150,
    datetime.fromisoformat("2024-09-16T04:00:00+02:00"): 0.300,
    datetime.fromisoformat("2024-09-16T05:00:00+02:00"): 0.400,
    datetime.fromisoformat("2024-09-16T06:00:00+02:00"): 0.600,
    datetime.fromisoformat("2024-09-16T07:00:00+02:00"): 0.900,
    datetime.fromisoformat("2024-09-16T08:00:00+02:00"): 1.300,
    datetime.fromisoformat("2024-09-16T09:00:00+02:00"): 0.900,
    datetime.fromisoformat("2024-09-16T10:00:00+02:00"): 0.700,
    datetime.fromisoformat("2024-09-16T11:00:00+02:00"): 0.700,
    datetime.fromisoformat("2024-09-16T12:00:00+02:00"): 0.500,
    datetime.fromisoformat("2024-09-16T13:00:00+02:00"): 0.450,
    datetime.fromisoformat("2024-09-16T14:00:00+02:00"): 0.350,
    datetime.fromisoformat("2024-09-16T15:00:00+02:00"): 0.400,
    datetime.fromisoformat("2024-09-16T16:00:00+02:00"): 0.650,
    datetime.fromisoformat("2024-09-16T17:00:00+02:00"): 0.850,
    datetime.fromisoformat("2024-09-16T18:00:00+02:00"): 0.900,
}


energy_cost_output = [
    0.650,
    0.900,
    1.200,
    0.900,
    0.850,
    0.450,
    0.300,
    0.200,
    0.450,
    0.750,
    1.100,
    1.450,
    1.550,
    1.400,
    0.900,
    0.700,
    0.600,
    0.300,
    -0.010,
    -0.050,
    -0.150,
    0.300,
    0.400,
    0.600,
    0.900,
    1.300,
    0.900,
    0.700,
    0.700,
    0.500,
    0.450,
    0.350,
    0.400,
    0.650,
    0.850,
    0.900,
]


def compare_timeslots_float(
    referenced_timeslots: list[float],
    calculated_timeslots: list[float],
    reference_shorter=True,
):
    if reference_shorter is False:  # allow differnt
        assert len(referenced_timeslots) == len(calculated_timeslots)

    index = 0
    for referenced_entry, calculated_entry in zip(
        referenced_timeslots, calculated_timeslots, strict=False
    ):
        assert isclose(
            referenced_entry, calculated_entry
        ), f"Not the same value, reference={referenced_entry}, calculated{calculated_entry}, index={index}"
        index += 1


def compare_datetime_float(
    referenced_entries: list[(datetime, Sequence[float])],
    calculated_entries: list[(datetime, Sequence[float])],
):
    assert len(referenced_entries) == len(calculated_entries)
    for referenced_entry, calculated_entry in zip(
        referenced_entries, calculated_entries, strict=True
    ):
        assert (
            referenced_entry[0] == calculated_entry[0]
        ), f"Not the same date, reference={referenced_entry[0]}, calculated{calculated_entry[0]}"

        for index in range(1, len(referenced_entry)):
            assert isclose(
                referenced_entry[index], calculated_entry[index]
            ), f"Values are different for {referenced_entry[0]}: ref_value={referenced_entry[index]}, calculated_value={calculated_entry[index]}"


def test_fill_in_solar(hass: HomeAssistant) -> None:
    charging_planner = SLXChargingPlanner(
        hass, SLXSolarParameter(bottom_cutoff=0, upper_cutoff=20, efficiency=1.0)
    )

    charging_planner.update_time_slots(
        datetime.fromisoformat("2024-09-15T07:00:00+02:00")
    )
    charging_planner.fill_in_solar_forecast(solar_prediction_test1)

    assert len(charging_planner._time_slots) == len(charging_planner._solar_forecasts)
    compare_timeslots_float(solar_prediction_output, charging_planner._solar_forecasts)

    charging_planner.update_time_slots(
        datetime.fromisoformat("2024-09-15T09:00:00+02:00")
    )
    # slots must be filled in
    assert len(charging_planner._time_slots) == len(charging_planner._solar_forecasts)
    assert len(charging_planner._time_slots) == len(charging_planner._energy_costs)

    # we are checking if slots are correctly shifted by two slots
    compare_timeslots_float(
        solar_prediction_output[2:], charging_planner._solar_forecasts
    )


def test_fill_in_energy(hass: HomeAssistant) -> None:
    ## we are going to check if the slots are shifted according to timeslot. We are putting the neutral SLXSolarParameters.
    charging_planner = SLXChargingPlanner(
        hass, SLXSolarParameter(bottom_cutoff=0, upper_cutoff=20, efficiency=1.0)
    )

    charging_planner.update_time_slots(
        datetime.fromisoformat("2024-09-15T07:00:00+02:00")
    )
    charging_planner.fill_in_energy_cost(energy_cost_test1)
    assert len(charging_planner._time_slots) == len(charging_planner._energy_costs)
    compare_timeslots_float(energy_cost_output, charging_planner._energy_costs)

    charging_planner.update_time_slots(
        datetime.fromisoformat("2024-09-15T09:00:00+02:00")
    )
    assert len(charging_planner._time_slots) == len(charging_planner._energy_costs)
    compare_timeslots_float(energy_cost_output[2:], charging_planner._energy_costs)

    # go beyond available data
    charging_planner.update_time_slots(
        datetime.fromisoformat("2024-09-16T19:00:00+02:00")
    )
    # length should be kept the same
    assert len(charging_planner._time_slots) == len(charging_planner._energy_costs)
    # all values should be None

    for item in charging_planner._energy_costs:
        assert item is None


planned_distances_test1 = [
    (date.fromisoformat("2024-09-16"), 20),
    (date.fromisoformat("2024-09-17"), 100),
    (date.fromisoformat("2024-09-18"), 50),
    (date.fromisoformat("2024-09-19"), 600),
    (date.fromisoformat("2024-09-20"), 30),
    (date.fromisoformat("2024-09-21"), 0),
    (date.fromisoformat("2024-09-22"), 30),
]


calculate_min_bat_energy_test1_params = {
    "planned_distances": planned_distances_test1,
    "energy_consumption": 0.18,
    "bottom_buffer": 10,
    "morning_start_utc": 3,
}

charging_config_test1 = SLXChargingConfig(
    charging_efficiency=0.8,
    batery_capacity=64,
    bottom_buffer=8,
    energy_consumption=0.18,
    morning_start_utc=3,
)

output_energy_consumed_trimmed_test1 = [
    (datetime.fromisoformat("2024-09-16T03:00:00+00:00"), 3.6),
    (datetime.fromisoformat("2024-09-17T03:00:00+00:00"), 18),
    (datetime.fromisoformat("2024-09-18T03:00:00+00:00"), 9),
    (datetime.fromisoformat("2024-09-19T03:00:00+00:00"), 56),
    (datetime.fromisoformat("2024-09-20T03:00:00+00:00"), 5.4),
    (datetime.fromisoformat("2024-09-21T03:00:00+00:00"), 0),
    (datetime.fromisoformat("2024-09-22T03:00:00+00:00"), 5.4),
]

output_energy_cumulative_min_max1 = [
    (datetime.fromisoformat("2024-09-16T03:00:00+00:00"), 2.5, 54),
    (datetime.fromisoformat("2024-09-17T03:00:00+00:00"), 25, 58.5),
    (datetime.fromisoformat("2024-09-18T03:00:00+00:00"), 36.25, 81),
    (datetime.fromisoformat("2024-09-19T03:00:00+00:00"), 106.25, 92.25),
    (datetime.fromisoformat("2024-09-20T03:00:00+00:00"), 113.0, 162.25),
    (datetime.fromisoformat("2024-09-21T03:00:00+00:00"), 113.0, 169.0),
    (datetime.fromisoformat("2024-09-22T03:00:00+00:00"), 119.75, 169.0),
]

calculated_energy_needed_test1 = [
    (datetime.fromisoformat("2024-09-16T03:00:00+00:00"), 13.6),
    (datetime.fromisoformat("2024-09-17T03:00:00+00:00"), 28),
    (datetime.fromisoformat("2024-09-18T03:00:00+00:00"), 19),
]


def test_calculate_energy_needed(hass: HomeAssistant) -> None:
    charging_planner = SLXChargingPlanner(
        hass,
        SLXSolarParameter(bottom_cutoff=0, upper_cutoff=20, efficiency=1.0),
        charging_config_test1,
    )

    charging_planner.update_time_slots(
        datetime.fromisoformat("2024-09-15T07:00:00+02:00")
    )

    charging_planner._energy_in_bat_now = 10
    charging_planner.calculate_energy_needed(planned_distances_test1)

    compare_datetime_float(
        output_energy_consumed_trimmed_test1, charging_planner._energy_consumed_trimmed
    )

    compare_datetime_float(
        output_energy_cumulative_min_max1, charging_planner._cumulative_energy_min_max
    )
