""" module for trip planned"""

from __future__ import annotations

from datetime import timedelta, datetime, date

import logging
import asyncio
import os
import bisect

from typing import Any


from homeassistant.core import HomeAssistant, Event

from homeassistant.const import UnitOfLength

# from homeassistant.components import recorder
from homeassistant.components.recorder import statistics
from homeassistant.components.recorder import history
from homeassistant.components.recorder import Recorder


from homeassistant.helpers import storage
import homeassistant.util.dt as dt_util

from .const import ODOMETER_DAYS_BACK
from .fileflag import (
    is_flag_active,
    FLAG_CLEAR_STORAGE,
    FLAG_EXPORT_ODOMETER,
    FLAG_DIR,
)
import csv


_LOGGER = logging.getLogger(__name__)


ODOMETER_STORAGE_KEY = "slxintegration_storage"


class SLXTripPlanner:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.odometer_list: list[datetime, float] = []
        self.daily_drive: list[date, float] = []
        self.ha_config_path = hass.config.config_dir
        _LOGGER.info("HA Path:  %s", self.ha_config_path)

    async def initialize(self, odometer_entity: str):
        self.odometer_entity = odometer_entity

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
            if odometer_str is not None:
                try:
                    odometer_value = float(odometer_str)
                except ValueError:
                    odometer_value = None
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
            try:
                value_odometer = float(event.state)
            except ValueError:
                value_odometer = None
            if value_odometer is not None and event.last_changed is not None:
                temp_list.append((event.last_changed, value_odometer))
        return temp_list

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

    def __append_odometer_list(
        self, list_one: list[datetime, float], list_two: list[datetime, float]
    ):
        if len(list_two) == 0:
            # nothing to do
            return
        if len(list_one) == 0:
            # TODO - will I need a hard copy if it? Probably now but be aware that it might be tricky.
            list_one = list_two
            return

        last_entry_dt = list_one[-1][0]
        index = bisect.bisect_right(list_two, (last_entry_dt,))
        list_one.extend(list_two[index:])

    async def capture_odometer(self):
        ## this function is correct at first run as it is going through all possible sources of information.
        ## clearing or reading the storage
        if is_flag_active(self.ha_config_path, FLAG_CLEAR_STORAGE):
            _LOGGER.info("Detected flag for clearing the storage")
            await self._clear_storage()
        else:
            self.odometer_list = await self._read_storage()
        read_storage_size: int = len(self.odometer_list)
        read_storage_start: datetime | None = None
        read_storage_finish: datetime | None = None

        if read_storage_size > 0:
            read_storage_start = self.odometer_list[0][0]
            read_storage_finish = self.odometer_list[-1][0]

        # TODO move it
        MAX_DAYS_BACK = 180

        ## now approach to capture any new odometer entries from statistics
        time_now = dt_util.as_utc(dt_util.now())
        time_start_statistics = (
            (time_now - timedelta(days=MAX_DAYS_BACK))
            if read_storage_finish is None
            else read_storage_finish
        )
        odometer_from_stats = await self._get_statistics(
            time_start_statistics, time_now
        )

        self.__append_odometer_list(self.odometer_list, odometer_from_stats)

        # re-check last entry
        odometer_last_time: datetime | None = (
            self.odometer_list[-1][0] if len(self.odometer_list) > 0 else None
        )

        stats_read_odometer_history = 0
        if odometer_last_time is None or odometer_last_time < time_now - timedelta(
            hours=6
        ):
            # we check entitiy history only if from statistics we didn't manage to get older than 6 hours
            time_start_odometer = (
                time_now - timedelta(days=MAX_DAYS_BACK)
                if odometer_last_time is None
                else odometer_last_time
            )
            odometer_list_history = await self._get_historical_odometer(
                time_start_odometer, time_now
            )
            stats_read_odometer_history = len(odometer_list_history)
            self.__append_odometer_list(self.odometer_list, odometer_list_history)

        # TO CHECK IF WE NEED TO STORE SOMETHING ?!
        stats_to_store: int = len(self.odometer_list)
        if stats_to_store > read_storage_size:
            await self._write_storage(self.odometer_list)

        self._calculate_daily()
        stats_daily_entries = len(self.daily_drive)
        _LOGGER.info(
            "Odometer processing stats: Storage Read Entries=%d, Odometer History Read=%d, Storage Write Entries=%d, Total daily entries=%d",
            read_storage_size,
            stats_read_odometer_history,
            stats_to_store,
            stats_daily_entries,
        )

        if is_flag_active(self.ha_config_path, FLAG_EXPORT_ODOMETER):
            self.__export_csv_odometer(self.odometer_list)

    def _calculate_daily(self):
        if len(self.daily_drive) > 0:
            _LOGGER.warning("Missing implementation of incremental recalculation")
            self.daily_drive.clear()

        currently_processed_day: date | None = None
        currently_processed_odo_start: float | None
        currently_processed_odo_end: float | None

        for odo_time, odo_distance in self.odometer_list:
            #            _LOGGER.info("Time %s:Value %.1f", odo_time, odo_distance)
            odo_date_current: date = odo_time.date()

            # first entry
            if currently_processed_day is None:
                currently_processed_day = odo_date_current
                currently_processed_odo_start = odo_distance

            # we are still in the same day
            if currently_processed_day == odo_date_current:
                currently_processed_odo_end = odo_distance

            # we started processing new day!
            if odo_date_current > currently_processed_day:
                # summarize previously processed days!

                days_diff = (odo_date_current - currently_processed_day).days
                if days_diff < 2:
                    to_store = (
                        currently_processed_day,
                        currently_processed_odo_end - currently_processed_odo_start,
                    )
                    self.daily_drive.append(to_store)
                else:
                    distance_per_day = (
                        currently_processed_odo_end - currently_processed_odo_start
                    ) / days_diff
                    for n in range(days_diff):
                        to_store = (
                            currently_processed_day + timedelta(days=n),
                            distance_per_day,
                        )
                        self.daily_drive.append(to_store)

                # switch to a new day
                currently_processed_day = odo_date_current
                currently_processed_odo_start = currently_processed_odo_end
                currently_processed_odo_end = odo_distance
        # TODO - summarize last and not finished day!

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
