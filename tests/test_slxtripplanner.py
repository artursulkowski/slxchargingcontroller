"""Test the for the SLXChargingController coordinator."""

from datetime import date, datetime
from math import isclose
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory, freeze_time

from custom_components.slxchargingcontroller.slxtripplanner import (
    ODOMETER_STORAGE_KEY,
    SLXTripPlanner,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import storage

from . import FIXTURE_CONFIG_ENTRY

ODOMETER_ENTITY_NAME = "kona.odometer_entity_test"


odometer_list_storage: list[(datetime, float)] = [
    (datetime.fromisoformat("2024-01-17 18:54:41.0+00:00"), 1234.0),
    (datetime.fromisoformat("2024-01-18 12:54:41.0+00:00"), 1240.1),  # 6.1
    (datetime.fromisoformat("2024-01-18 14:20:00.0+00:00"), 1310.6),  # 70.5
    (datetime.fromisoformat("2024-01-19 01:00:00.0+00:00"), 1325.6),  # 15.0
    (datetime.fromisoformat("2024-01-21 12:00:41.0+00:00"), 1340),
    (datetime.fromisoformat("2024-01-23 03:10:00.0+00:00"), 1700.1),
    (datetime.fromisoformat("2024-01-24 17:30:00.0+00:00"), 1710.2),
]

indexes_list: list[(date, int)] = [
    (date.fromisoformat("2024-01-17"), 0),
    (date.fromisoformat("2024-01-18"), 2),
    (date.fromisoformat("2024-01-19"), 3),
    (date.fromisoformat("2024-01-21"), 4),
    (date.fromisoformat("2024-01-23"), 5),
    (date.fromisoformat("2024-01-24"), 6),
]

distance_per_day: list[(date, float)] = [
    (date.fromisoformat("2024-01-16"), 0),
    (date.fromisoformat("2024-01-17"), 0),
    (date.fromisoformat("2024-01-18"), 76.6),
    (date.fromisoformat("2024-01-19"), 15),
    (date.fromisoformat("2024-01-20"), 0),
    (date.fromisoformat("2024-01-21"), 14.4),
    (date.fromisoformat("2024-01-22"), 0),
    (date.fromisoformat("2024-01-23"), 360.1),
    (date.fromisoformat("2024-01-24"), 10.1),
    (date.fromisoformat("2024-01-25"), 0),
]

histogram: list[list[float]] = [
    [0],
    [360.1],
    [],
    [76.6],
    [15],
    [0],
    [14.4],
]


odometer_list_entity: list[(datetime, float)] = [
    (datetime.fromisoformat("2024-01-24 12:00:00.0+00:00"), 1705),
    (datetime.fromisoformat("2024-01-26 19:54:41.0+00:00"), 1720.2),
]


odometer_test_time = datetime.fromisoformat("2024-01-27 13:14:15.0+00:00")


async def test_tripplanner_storage_read(hass: HomeAssistant) -> None:
    odometer_list: list[(datetime, float)] = [
        (datetime.fromisoformat("2024-01-17 18:54:41.482455+00:00"), 1234.5),
        (datetime.fromisoformat("2024-01-18 19:54:41.482455+00:00"), 2345.6),
    ]

    data_for_write = {ODOMETER_ENTITY_NAME: odometer_list}
    store = storage.Store(hass, 1, ODOMETER_STORAGE_KEY)
    await store.async_save(data_for_write)
    odometer_list_empty: list[(datetime, float)] = []

    tripplanner = SLXTripPlanner(hass)
    with patch(
        "custom_components.slxchargingcontroller.slxtripplanner.SLXTripPlanner._get_historical_odometer",
        return_value=odometer_list_empty,
    ), patch(
        "custom_components.slxchargingcontroller.slxtripplanner.SLXTripPlanner._get_statistics",
        return_value=[],
    ):
        await tripplanner.initialize(ODOMETER_ENTITY_NAME)
        list_odo = tripplanner.odometer_list
        assert len(list_odo) == 2
        assert list_odo[1][1] == 2345.6


async def test_tripplanner_historical_odometer(
    hass: HomeAssistant,
) -> None:
    """No storage available, check that it will request records for last 30 days"""
    with patch(
        "custom_components.slxchargingcontroller.slxtripplanner.SLXTripPlanner._get_historical_odometer",
        return_value=[
            (datetime.fromisoformat("2024-01-18 19:54:41.482455+00:00"), 2345.6),
            (datetime.fromisoformat("2024-01-19 21:54:41.482455+00:00"), 2445.6),
        ],
    ) as historical_odometer, patch(
        "custom_components.slxchargingcontroller.slxtripplanner.SLXTripPlanner._get_statistics",
        return_value=[],
    ):
        tripplanner = SLXTripPlanner(hass)
        await tripplanner.initialize(ODOMETER_ENTITY_NAME)
        historical_odometer.assert_called_once()


async def test_tripplanner_merge_storage_and_historical(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    data_for_write = {ODOMETER_ENTITY_NAME: odometer_list_storage}
    store = storage.Store(hass, 1, ODOMETER_STORAGE_KEY)
    await store.async_save(data_for_write)

    tripplanner = SLXTripPlanner(hass)
    with patch(
        "custom_components.slxchargingcontroller.slxtripplanner.SLXTripPlanner._get_historical_odometer",
        return_value=odometer_list_entity,
    ) as historical_odometer, patch(
        "custom_components.slxchargingcontroller.slxtripplanner.SLXTripPlanner._get_statistics",
        return_value=[],
    ):
        freezer.move_to(odometer_test_time)
        await tripplanner.initialize(ODOMETER_ENTITY_NAME)
        historical_odometer.assert_called_once()
        list_odo = tripplanner.odometer_list
        assert len(list_odo) == 8


def test_append_odometer_list(hass: HomeAssistant):
    tripplanner = SLXTripPlanner(hass)
    odometer_sublist1 = odometer_list_storage[:6]
    odometer_sublist2 = odometer_list_storage[3:]
    tripplanner._append_odometer_list(odometer_sublist1, odometer_sublist2)
    assert len(odometer_sublist1) == len(odometer_list_storage)


def test_calculate_indexes(hass: HomeAssistant):
    tripplanner = SLXTripPlanner(hass)
    tripplanner.odometer_list = odometer_list_storage
    tripplanner._recalculate_odometer_index()
    assert len(tripplanner.odometer_index) == 6
    for a, b in zip(tripplanner.odometer_index, indexes_list):
        assert (a, tripplanner.odometer_index[a]) == b


def test_calculate_distance(hass: HomeAssistant):
    tripplanner = SLXTripPlanner(hass)
    tripplanner.odometer_list = odometer_list_storage
    tripplanner._recalculate_odometer_index()

    for drive_day, distance in distance_per_day:
        calculated_distance: float = tripplanner._get_day_distance_driven(drive_day)
        assert isclose(
            distance, calculated_distance
        ), f"Comparison failed: {drive_day}: distance={distance}, calculated_distance={calculated_distance}, "


def test_daily_stats(hass: HomeAssistant):
    # Test scenario in which we are calculating daily drive statistics.
    # We shall have daily driven distances per day and then aggregate them into "per weekday"
    # based on this we will create very simple model for estimating most probable daily drive.
    # This plus reasonable updates will give me a good place to finish:
    # - updating daily drive calendar
    # - estimating upcoming days drive.

    # How to structure in trip planner?
    # ignore the last day with available odometer (in fact refer to index list - and we can consider in statistics the one before the last) - we can only calculate for the day before the last one (any easy way to find it?)
    # create matrix (or simpler - list of lists) [7][n]. This matrix will store days driven for each weekday
    # together with that matrix - store also the last day(date) which is put into the list. We will

    tripplanner = SLXTripPlanner(hass)
    tripplanner.odometer_list = odometer_list_storage
    tripplanner._recalculate_odometer_index()
    tripplanner._update_daily_histogram()
    for weekday in range(7):
        assert len(histogram[weekday]) == len(tripplanner.daily_histogram[weekday])
        for distance, calculated in zip(
            histogram[weekday], tripplanner.daily_histogram[weekday]
        ):
            assert isclose(
                distance, calculated
            ), f"Comparison failed: weekday{weekday}: distance={distance}, calculated_distance={calculated}, "


odometer_list_storage_test_merging: list[(datetime, float)] = [
    (datetime.fromisoformat("2024-01-17 18:54:41.0+00:00"), 1234.0),  # Wed
    (datetime.fromisoformat("2024-01-18 12:54:41.0+00:00"), 1240.1),  #
    (datetime.fromisoformat("2024-01-18 14:20:00.0+00:00"), 1310.6),  # Thu, 76.6
    (datetime.fromisoformat("2024-01-19 01:00:00.0+00:00"), 1325.6),  # Fri  # 15.0
    (datetime.fromisoformat("2024-01-21 12:00:41.0+00:00"), 1340),  # Sun
    (datetime.fromisoformat("2024-01-23 03:10:00.0+00:00"), 1700.1),  # Tue
    (datetime.fromisoformat("2024-01-24 17:30:00.0+00:00"), 1710.2),  # Wed , 10.1
    (datetime.fromisoformat("2024-01-27 11:30:00.0+00:00"), 1720.2),  # Sat # 10
    # break
    (datetime.fromisoformat("2024-01-27 12:30:00.0+00:00"), 1730.2),  # Sat
    (datetime.fromisoformat("2024-01-27 14:30:00.0+00:00"), 1731.2),  # Sat -> 21
    (datetime.fromisoformat("2024-01-29 10:30:00.0+00:00"), 1751.2),  # Mon
    (datetime.fromisoformat("2024-01-30 10:30:00.0+00:00"), 1851.2),  # Tue
    (datetime.fromisoformat("2024-01-30 11:30:00.0+00:00"), 1861.2),  # Tue
]

histogram_test_merging1: list[list[float]] = [
    [0],
    [360.1],
    [10.1],
    [76.6],
    [15],
    [0],
    [14.4],
]

histogram_test_merging2: list[list[float]] = [
    [0, 20],
    [360.1],
    [10.1],
    [76.6, 0],
    [15, 0],
    [0, 21],
    [14.4, 0],
]

odometer_test_merging_daily_trips1: list[(date, float)] = [
    (date.fromisoformat("2024-01-18"), 76.6),
    (date.fromisoformat("2024-01-19"), 15),
    (date.fromisoformat("2024-01-20"), 0),
    (date.fromisoformat("2024-01-21"), 14.4),
    (date.fromisoformat("2024-01-22"), 0),
    (date.fromisoformat("2024-01-23"), 360.1),
    (date.fromisoformat("2024-01-24"), 10.1),
    (date.fromisoformat("2024-01-25"), 0),
    (date.fromisoformat("2024-01-26"), 0),
    (date.fromisoformat("2024-01-27"), 21),
    (date.fromisoformat("2024-01-28"), 0),
    (date.fromisoformat("2024-01-29"), 20),
]


def compare_histograms(
    referenced_historgram: list[list[float]], calculated_historgram: list[list[float]]
):
    for weekday in range(7):
        assert len(referenced_historgram[weekday]) == len(
            calculated_historgram[weekday]
        )
        for distance, calculated in zip(
            referenced_historgram[weekday], calculated_historgram[weekday]
        ):
            assert isclose(
                distance, calculated
            ), f"Comparison failed: weekday{weekday}: ref_distance={distance}, calculated_distance={calculated}, "


def compare_daily_trips(
    referenced_trips: list[(date, float)], calculated_trips: list[(date, float)]
):
    assert len(referenced_trips) == len(calculated_trips)
    for referenced_entry, calculated_entry in zip(referenced_trips, calculated_trips):
        assert (
            referenced_entry[0] == calculated_entry[0]
        ), f"Not the same date, reference={referenced_entry[0]}, calculated{calculated_entry[0]}"
        assert isclose(
            referenced_entry[1], calculated_entry[1]
        ), f"Distance is different for {referenced_entry[0]}: ref_distance={referenced_entry[1]}, calculated_distance={calculated_entry[1]}"


def test_odometer_merge_and_histogram(hass: HomeAssistant):
    # Scenario - set odometer, calculate index and histogram.
    # Then, extend odometer array, recalculate index and histogram.
    # through debugging - test if we are doing it in optional way.

    tripplanner = SLXTripPlanner(hass)
    tripplanner.odometer_list = odometer_list_storage_test_merging[:8]
    tripplanner._recalculate_odometer_index()
    tripplanner._update_daily_histogram()
    assert tripplanner.daily_histogram_last_date == date.fromisoformat("2024-01-24")
    compare_histograms(histogram_test_merging1, tripplanner.daily_histogram)

    tripplanner.odometer_list = odometer_list_storage_test_merging
    tripplanner._recalculate_odometer_index()
    tripplanner._update_daily_histogram()
    assert tripplanner.daily_histogram_last_date == date.fromisoformat("2024-01-29")
    compare_histograms(histogram_test_merging2, tripplanner.daily_histogram)


def test_get_daily_drives(hass: HomeAssistant):
    tripplanner = SLXTripPlanner(hass)
    tripplanner.odometer_list = odometer_list_storage_test_merging
    tripplanner._recalculate_odometer_index()
    daily_drives = tripplanner.get_daily_trips(None, None)
    compare_daily_trips(odometer_test_merging_daily_trips1, daily_drives)


def test_get_daily_drives2(hass: HomeAssistant):
    tripplanner = SLXTripPlanner(hass)
    tripplanner.odometer_list = odometer_list_storage_test_merging
    tripplanner._recalculate_odometer_index()
    daily_drives = tripplanner.get_daily_trips(date.fromisoformat("2024-01-19"), None)
    compare_daily_trips(odometer_test_merging_daily_trips1[1:], daily_drives)


def test_get_daily_drives3(hass: HomeAssistant):
    tripplanner = SLXTripPlanner(hass)
    tripplanner.odometer_list = odometer_list_storage_test_merging
    tripplanner._recalculate_odometer_index()
    daily_drives = tripplanner.get_daily_trips(date.fromisoformat("2024-01-25"), None)
    compare_daily_trips(odometer_test_merging_daily_trips1[7:], daily_drives)


def test_get_daily_drives4(hass: HomeAssistant):
    tripplanner = SLXTripPlanner(hass)
    tripplanner.odometer_list = odometer_list_storage_test_merging
    tripplanner._recalculate_odometer_index()
    daily_drives = tripplanner.get_daily_trips(None, date.fromisoformat("2024-01-25"))
    compare_daily_trips(odometer_test_merging_daily_trips1[:8], daily_drives)


def compare_predictor(
    referenced_predictor: dict[date, list[float]],
    calculated_predictor: dict[date, list[float]],
):
    keys_reference = list(referenced_predictor.keys())
    keys_calculated = list(calculated_predictor.keys())
    assert len(keys_reference) == len(keys_calculated)
    # any inconsistency in keys will appear at checking entries, so I don't need to verify them one by one.

    for date_to_check in keys_reference:
        list_ref = referenced_predictor[date_to_check]
        list_calc = calculated_predictor[date_to_check]

        assert len(list_ref) == len(list_calc)
        for dist_ref, dist_calc in zip(list_ref, list_calc):
            assert isclose(
                dist_ref, dist_calc
            ), f"Comparison failed: {date_to_check}: ref_distance={dist_ref}, calculated_distance={dist_calc}, "


predictor_test1_value: dict[date, list[float]] = {
    date(2024, 1, 30): [360.1],
    date(2024, 1, 31): [10.1],
    date(2024, 2, 1): [0],
    date(2024, 2, 2): [0],
    date(2024, 2, 3): [21.0],
    date(2024, 2, 4): [0],
    date(2024, 2, 5): [20.0],
}


def test_predictor1(hass: HomeAssistant):
    ## TODO - use artifical histograms to test predictor. It does not make sense to do it based on odometer(too much hustle with creating test data!)
    tripplanner = SLXTripPlanner(hass)
    tripplanner.odometer_list = odometer_list_storage_test_merging[:8]
    tripplanner.odometer_list = odometer_list_storage_test_merging
    tripplanner._recalculate_odometer_index()
    tripplanner._update_daily_histogram()
    assert tripplanner.daily_histogram_last_date == date.fromisoformat("2024-01-29")
    compare_histograms(histogram_test_merging2, tripplanner.daily_histogram)
    tripplanner._run_predictor()
    compare_predictor(predictor_test1_value, tripplanner.predictor_output)


## more advanced predictor checks

histogram_input_predictor_test2: list[list[float]] = [
    [25.9, 28.1, 42.3, 52.8, 16.0, 20.2, 18],
    [12.2, 31.8, 26.3, 5.8, 50.2, 1.9, 7.5],
    [20.7, 10.8, 26.3, 0, 39.7, 20.8, 26.2],
    [222.6, 0.0, 5.4, 13.6, 0.0, 8.3, 21.5],
    [20.7, 59.7, 720.4, 52.4, 13.6, 9.6, 15.6],
    [63.5, 35.2, 693.6, 55.3, 812.2, 10.6, 19.6],
    [0.0, 0.0, 0.0, 0.0, 33.8, 606.9, 223.1],
]

predictor_test2_values: dict[date, list[float]] = {
    date(2024, 7, 14): [223.1],
    date(2024, 7, 15): [20.2],
    date(2024, 7, 16): [7.5],
    date(2024, 7, 17): [26.2],
    date(2024, 7, 18): [8.3],
    date(2024, 7, 19): [15.6],
    date(2024, 7, 20): [55.3],
}

predictor_test3_values: dict[date, list[float]] = {
    date(2024, 7, 14): [223.1],
    date(2024, 7, 15): [20.2, 20.2],
    date(2024, 7, 16): [7.5, 7.5],
    date(2024, 7, 17): [26.2, 26.2],
    date(2024, 7, 18): [8.3, 8.3],
    date(2024, 7, 19): [15.6, 15.6],
    date(2024, 7, 20): [55.3, 55.3],
    date(2024, 7, 21): [223.1],
}


def test_predictor2(hass: HomeAssistant):
    tripplanner = SLXTripPlanner(hass)
    tripplanner.daily_histogram_last_date = date(2024, 7, 13)
    tripplanner.daily_histogram = histogram_input_predictor_test2
    tripplanner._run_predictor()
    compare_predictor(predictor_test2_values, tripplanner.predictor_output)


def test_predictor3(hass: HomeAssistant):
    tripplanner = SLXTripPlanner(hass)
    tripplanner.daily_histogram_last_date = date(2024, 7, 13)
    tripplanner.daily_histogram = histogram_input_predictor_test2
    tripplanner._run_predictor()
    tripplanner.daily_histogram_last_date = date(2024, 7, 14)
    tripplanner._run_predictor()
    compare_predictor(predictor_test3_values, tripplanner.predictor_output)
