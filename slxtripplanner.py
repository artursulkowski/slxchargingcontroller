""" module for trip planned"""

from __future__ import annotations

import bisect
from collections import OrderedDict
import contextlib
import csv
from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.components.recorder import history, statistics
from homeassistant.const import UnitOfLength
from homeassistant.core import Callable, Event, HomeAssistant
from homeassistant.helpers import storage
from homeassistant.helpers.event import async_track_state_change_event
import homeassistant.util.dt as dt_util

from .const import ODOMETER_DAYS_BACK
from .fileflag import (
    FLAG_CLEAR_STORAGE,
    FLAG_DIR,
    FLAG_EXPORT_DAILY,
    FLAG_EXPORT_ODOMETER,
    is_flag_active,
)

_LOGGER = logging.getLogger(__name__)


ODOMETER_STORAGE_KEY = "slxintegration_storage"


class SLXTripPlanner:
    """Process odometer and estimate future trips."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Create empty planner object.

        Does not run any data processing.
        """
        self.hass = hass
        self.unsub_dict: dict[str, Callable[[Event], Any]] = {}
        self.odometer_list: list[datetime, float] = []
        self.odometer_index: OrderedDict[date, int] = {}
        self.daily_histogram: list[list[float]] = []
        for weekday in range(7):
            self.daily_histogram.append(list())
        self.daily_histogram_last_date: date | None = None
        self.ha_config_path = hass.config.config_dir
        self.odometer_entity = None
        _LOGGER.info("HA Path:  %s", self.ha_config_path)

    async def initialize(self, odometer_entity: str):
        """Initialize processing of odometer input and subscribes for its changes."""
        self.odometer_entity = odometer_entity

        await self.startup_capture_odometer()
        self._subscribe_entity(odometer_entity, self._callback_odometer_value)

    async def disconnect(self) -> bool:
        """Use for tear down of the object."""
        for entity_name, cancel in self.unsub_dict.items():
            _LOGGER.debug("Unsubscribing entity %s", entity_name)
            cancel()

    async def _callback_odometer_value(self, event: Event) -> None:
        _LOGGER.debug("Called odometer callback")
        value = None
        with contextlib.suppress(ValueError):
            value = float(event.data["new_state"].state)
        if value is not None:
            _LOGGER.debug("Odometer value = %d", value)
            when_event = event.time_fired
            # TODO - to be tested if appended value and the one read from history have same datetime.
            self.odometer_list.append((when_event, value))
            self._recalculate_odometer_index()
            self._update_daily_histogram()
            # TODO calculate predictions ( if daily histogram has added a new day)

    async def _get_statistics(
        self, start_time: datetime, end_time: datetime
    ) -> list[datetime, float]:
        statistic_list = await self.hass.async_add_executor_job(
            statistics.statistics_during_period,
            self.hass,
            start_time,
            end_time,
            [self.odometer_entity],
            "hour",
            {"distance": UnitOfLength.KILOMETERS},
            {"state"},
        )

        tmp_list: list[datetime, float] = []

        stats_list = statistic_list.get(self.odometer_entity, None)
        if stats_list is None:
            _LOGGER.info(
                "No long-term statistics for statistic_id = %s", self.odometer_entity
            )
            return tmp_list
        found_stat_entries = len(stats_list)
        first_entry_timestamp = stats_list[0].get("start", None)
        if first_entry_timestamp is None:
            first_entry_date = "N/A"
        else:
            first_entry_date = dt_util.utc_from_timestamp(first_entry_timestamp)
        last_entry_timestamp = stats_list[-1].get("start", None)
        if last_entry_timestamp is None:
            last_entry_date = "N/A"
        else:
            last_entry_date = dt_util.utc_from_timestamp(last_entry_timestamp)

        _LOGGER.warning(
            "Captured stats for %s: Entries: %d, start: %s, end: %s",
            self.odometer_entity,
            found_stat_entries,
            first_entry_date,
            last_entry_date,
        )

        for stats_entry in stats_list:
            timestamp_str = stats_entry.get("start", None)
            odometer_str = stats_entry.get("state", None)
            odometer_value = None
            if odometer_str is not None:
                with contextlib.suppress(ValueError):
                    odometer_value = float(odometer_str)
            if timestamp_str is not None and odometer_value is not None:
                tmp_list.append(
                    (dt_util.utc_from_timestamp(timestamp_str), odometer_value)
                )
        return tmp_list

    # I will move capturing of data from recorder here so I can mock it easily in tests without the need to real with the recorder.
    # Other function should play more with extending storage using odometer data.
    async def _get_historical_odometer(
        self, start_time: datetime, end_time: datetime
    ) -> list[(datetime, float)]:
        temp_list: list[(datetime, float)] = []
        _LOGGER.info("Process odometer, entity name = %s", self.odometer_entity)

        events = await self.hass.async_add_executor_job(
            history.get_significant_states,
            self.hass,
            start_time,
            end_time,
            [self.odometer_entity],
            None,
            True,
            True,
        )

        if self.odometer_entity not in events.keys():
            return temp_list

        for event in events[self.odometer_entity]:
            value_odometer = None
            with contextlib.suppress(ValueError):
                value_odometer = float(event.state)
            if value_odometer is not None and event.last_changed is not None:
                temp_list.append((event.last_changed, value_odometer))
        return temp_list

    ## storage operations

    async def _clear_storage(self):
        store = storage.Store(self.hass, 1, ODOMETER_STORAGE_KEY)
        await store.async_remove()

    async def _read_storage(self) -> list[(datetime, float)]:
        store = storage.Store(self.hass, 1, ODOMETER_STORAGE_KEY)
        tmp_odometer: list[(datetime, float)] = []
        data_read = await store.async_load()
        if data_read is None:
            return tmp_odometer
        try:
            list_odo_read = data_read[self.odometer_entity]
        except KeyError:
            return tmp_odometer
        for x, y in list_odo_read:
            try:
                dt_obj = datetime.fromisoformat(x)
            except Exception:  # pylint: disable=broad-except
                dt_obj = None
                _LOGGER.warning("Invalid time format %s", x)
            if dt_obj is not None:
                tmp_odometer.append((dt_obj, y))
        return tmp_odometer

    async def _write_storage(self, odometer_list: list[datetime, float]) -> bool:
        store = storage.Store(self.hass, 1, ODOMETER_STORAGE_KEY)
        entries_to_write = len(odometer_list)
        if entries_to_write > 0:
            data_for_write = {self.odometer_entity: odometer_list}
            await store.async_save(data_for_write)
            _LOGGER.info("Writen odometer storage with %d entries", entries_to_write)
            return True
        return False

    ## helper methods

    def _append_odometer_list(
        self, list_one: list[datetime, float], list_two: list[datetime, float]
    ) -> int:
        """Appends two lists of odometrs, returns number of items added"""
        len_list_one = len(list_one)
        if len_list_one == 0:
            # nothing to do
            return 0
        if len(list_one) == 0:
            list_one[:] = list_two
            return len(list_two)

        last_entry_dt = list_one[-1][0]
        last_entry_odometer = list_one[-1][1]
        index = bisect.bisect(list_two, (last_entry_dt, last_entry_odometer))
        list_one.extend(list_two[(index):])
        added_items = len(list_one) - len_list_one
        return added_items

    async def startup_capture_odometer(self):
        """Run it at startup of HA. It is combining all possible sources of odometer information."""

        ## Flag! Clearing or reading the storage
        if is_flag_active(self.ha_config_path, FLAG_CLEAR_STORAGE):
            _LOGGER.info("Detected flag for clearing the storage")
            await self._clear_storage()
        else:
            ## STAGE 1 - read the storage
            self.odometer_list = await self._read_storage()
        read_storage_size: int = len(self.odometer_list)
        read_storage_start: datetime | None = None
        read_storage_finish: datetime | None = None

        if read_storage_size > 0:
            read_storage_start = self.odometer_list[0][0]
            read_storage_finish = self.odometer_list[-1][0]

        # STAGE 2 - read from statistics and add it to read entries.
        # now approach to capture any new odometer entries from statistics
        time_now = dt_util.as_utc(dt_util.now())
        time_start_statistics = (
            time_now - timedelta(days=ODOMETER_DAYS_BACK)
            if read_storage_finish is None
            else read_storage_finish
        )
        odometer_from_stats = await self._get_statistics(
            time_start_statistics, time_now
        )

        self._append_odometer_list(self.odometer_list, odometer_from_stats)

        # Check last entry
        odometer_last_time: datetime | None = (
            self.odometer_list[-1][0] if len(self.odometer_list) > 0 else None
        )

        # STAGE 3- read from entity history
        stats_read_odometer_history = 0
        if odometer_last_time is None or odometer_last_time < time_now - timedelta(
            hours=6
        ):
            # we check entitiy history only if from statistics we didn't manage to get older than 6 hours
            time_start_odometer = (
                time_now - timedelta(days=ODOMETER_DAYS_BACK)
                if odometer_last_time is None
                else odometer_last_time
            )
            odometer_list_history = await self._get_historical_odometer(
                time_start_odometer, time_now
            )
            stats_read_odometer_history = len(odometer_list_history)
            self._append_odometer_list(self.odometer_list, odometer_list_history)

        # STAGE 4 - checks if we need to store some new entries
        # TO CHECK IF WE NEED TO STORE SOMETHING ?!
        stats_to_store: int = len(self.odometer_list)
        if stats_to_store > read_storage_size:
            await self._write_storage(self.odometer_list)

        # STAGE 5 - update histogram daily
        self._recalculate_odometer_index()
        self._update_daily_histogram()

        # Flag - exporting data
        if is_flag_active(self.ha_config_path, FLAG_EXPORT_ODOMETER):
            self.__export_csv_odometer(self.odometer_list)

        if is_flag_active(self.ha_config_path, FLAG_EXPORT_DAILY):
            daily_trips = self._get_daily_trips(None, None)
            if len(daily_trips) > 0:
                self.__export_csv_daily_odometer(daily_trips)

    async def _update_odometer(self):
        """Read odometer entity and add if there are new entires."""
        # Check last entry
        odometer_last_time: datetime | None = (
            self.odometer_list[-1][0] if len(self.odometer_list) > 0 else None
        )
        if odometer_last_time is None:
            _LOGGER.warning(
                "We tried to update odometer but odometer_list is empty. We are ignoring such edge case"
            )
            return None
        time_now = dt_util.as_utc(dt_util.now())
        odometer_list_history = await self._get_historical_odometer(
            odometer_last_time, time_now
        )
        self._append_odometer_list(self.odometer_list, odometer_list_history)

    def _recalculate_odometer_index(self):
        keys = list(self.odometer_index.keys())

        first_new_index_value = 0
        if keys:
            # list is not empty
            first_new_index_value = self.odometer_index[keys[-1]] + 1
        # lets start processing..

        odometer_entries_for_processing = self.odometer_list[first_new_index_value:]
        for index, (odo_datetime, _) in enumerate(
            odometer_entries_for_processing, first_new_index_value
        ):
            odo_date = odo_datetime.date()
            self.odometer_index[odo_date] = index

    def _get_day_distance_driven(self, day_to_calculate: date) -> float:
        # it is quite inefficient. Don't use it to calculate some group statistics for a longer periods.
        if day_to_calculate not in self.odometer_index:
            return 0
        keys = list(self.odometer_index.keys())
        position_in_index_list = keys.index(day_to_calculate)
        if position_in_index_list == 0:
            # it's a first day - we can only calculate refering to previous one!
            return 0
        odometer_current_day = self.odometer_list[
            self.odometer_index[day_to_calculate]
        ][1]
        odometer_previous_day = self.odometer_list[
            self.odometer_index[keys[position_in_index_list - 1]]
        ][1]
        return odometer_current_day - odometer_previous_day

    def _get_daily_trips(
        self, start_date: date | None, end_date: date | None
    ) -> list[(date, float)]:
        """Calculate daily distances for each dates in the range.

        In case when start_date is None - take first possible date for which we can calculate distance driven
        In case when end_date is None - take the last possible date for which we can calculate distance driven
        In case when we cannot calculate the distance since start_date (or till end_date) - we are not filling in the list with those dates.

        Assumptions: odometer_index is updated.
        """
        index_keys = list(self.odometer_index.keys())
        if len(index_keys) < 2:
            # for sure we won't be able to calculate any day!
            # return empty list
            return []

        first_possible_date: date = index_keys[0]
        last_possible_date: date = index_keys[-2]

        # TODO - start date is not the same as first day to process! We need to get one day back in out processing (how to do it?)
        if start_date is None:
            first_day_to_process = first_possible_date
            start_date = first_day_to_process + timedelta(days=1)
        else:
            # we need to find a day for processing which is before start_date.
            index = bisect.bisect_left(index_keys, start_date)
            if (
                index > 0
            ):  # not always mathematically correct but we can just move one index before. In worst case we will process (but ignore) few additional entries.
                index -= 1
            first_day_to_process = index_keys[index]

        if end_date is None:
            last_day_to_calculate = last_possible_date
        else:
            last_day_to_calculate = min(last_possible_date, end_date)

        temporary_daily: list[(date, float)] = []
        # TODO - brutal copy-paste from _update_daily_histogram. To refactor - separate algorithm and action taken on data.

        previous_odometer = self.odometer_list[
            self.odometer_index[first_day_to_process]
        ][1]
        current_date = first_day_to_process + timedelta(days=1)
        while current_date <= last_day_to_calculate:
            # we are iterating day by day , through this loop we can decide if the day is empty or present in odometer index and make relevant calculations.
            daily_distance: float = 0
            if current_date in self.odometer_index:
                current_odometer = self.odometer_list[
                    self.odometer_index[current_date]
                ][1]
                daily_distance = current_odometer - previous_odometer
                previous_odometer = current_odometer
            if current_date >= start_date:  # ignore dates before
                temporary_daily.append((current_date, daily_distance))

            # Add histogramic information!
            current_date += timedelta(days=1)
        return temporary_daily

    def _update_daily_histogram(self):
        # check the last day which we can calculate from odometer index.
        keys = list(self.odometer_index.keys())
        if len(keys) < 2:
            # nothing to do! With only one day indexed we cannot calcuate the day.
            return
        last_day_to_calculate = keys[-2]

        if self.daily_histogram_last_date is not None:
            first_day_to_process = self.daily_histogram_last_date
        else:
            first_day_to_process = keys[0]

        previous_odometer = self.odometer_list[
            self.odometer_index[first_day_to_process]
        ][1]

        temporary_daily: list[date, float] = []

        current_date = first_day_to_process + timedelta(days=1)
        while current_date <= last_day_to_calculate:
            # we are iterating day by day , through this loop we can decide if the day is empty or present in odometer index and make relevant calculations.
            daily_distance: float = 0
            if current_date in self.odometer_index:
                current_odometer = self.odometer_list[
                    self.odometer_index[current_date]
                ][1]
                daily_distance = current_odometer - previous_odometer
                previous_odometer = current_odometer
            temporary_daily.append((current_date, daily_distance))

            # Add histogramic information!

            self.daily_histogram[current_date.weekday()].append(daily_distance)
            self.daily_histogram_last_date = current_date

            current_date += timedelta(days=1)

    def __export_csv_odometer(self, data: list[datetime, float]):
        current_time = dt_util.now()
        filename = f"odometer_{current_time.strftime('%Y%m%d_%H%M%S')}.csv"

        csv_full_filename = self.ha_config_path + "/" + FLAG_DIR + filename
        with open(csv_full_filename, "w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(["Timestamp", "Odometer"])
            csv_writer.writerows(
                [
                    (timestamp.strftime("%Y-%m-%d %H:%M:%S"), value)
                    for timestamp, value in data
                ]
            )

    def __export_csv_daily_odometer(self, data: list[date, float]):
        current_time = dt_util.now()
        filename = f"daily_{current_time.strftime('%Y%m%d_%H%M%S')}.csv"

        csv_full_filename = self.ha_config_path + "/" + FLAG_DIR + filename
        with open(csv_full_filename, "w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(["Date", "Daily Trips"])
            csv_writer.writerows(
                [(timestamp.strftime("%Y-%m-%d"), value) for timestamp, value in data]
            )

    def _subscribe_entity(
        self, entity_name: str, external_calback: Callable[[Event], Any]
    ) -> None:
        self.unsub_dict[entity_name] = async_track_state_change_event(
            self.hass, entity_name, external_calback
        )
