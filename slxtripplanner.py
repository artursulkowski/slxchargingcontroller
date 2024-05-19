""" module for trip planned"""

from __future__ import annotations

import asyncio
import bisect
import contextlib
import csv
from datetime import date, datetime, timedelta
import logging
import os
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
        self.daily_drive: list[date, float] = []
        self.ha_config_path = hass.config.config_dir
        self.odometer_entity = None
        _LOGGER.info("HA Path:  %s", self.ha_config_path)

    async def initialize(self, odometer_entity: str):
        """Initialize processing of odometer input and subscribes for its changes."""
        self.odometer_entity = odometer_entity

        # Run odometer analysis?
        # TODO - subscribe odometer entity changes
        self._subscribe_entity(odometer_entity, self._callback_soc_level)

    async def disconnect(self) -> bool:
        """Use for tear down of the object."""
        for entity_name, cancel in self.unsub_dict.items():
            _LOGGER.debug("Unsubscribing entity %s", entity_name)
            cancel()

    async def _callback_soc_level(self, event: Event) -> None:
        _LOGGER.debug("Called odometer callback")
        value = None
        with contextlib.suppress(ValueError):
            value = float(event.data["new_state"].state)
        if value is not None:
            _LOGGER.debug("Odometer value = %d", value)

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
            list_one[:] = list_two
            return

        last_entry_dt = list_one[-1][0]
        index = bisect.bisect_right(list_two, (last_entry_dt,))
        list_one.extend(list_two[index:])

    async def capture_odometer(self):
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

        self.__append_odometer_list(self.odometer_list, odometer_from_stats)

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
            self.__append_odometer_list(self.odometer_list, odometer_list_history)

        # STAGE 4 - checks if we need to store some new entries
        # TO CHECK IF WE NEED TO STORE SOMETHING ?!
        stats_to_store: int = len(self.odometer_list)
        if stats_to_store > read_storage_size:
            await self._write_storage(self.odometer_list)

        # STAGE 5 - calculate daily
        self._calculate_daily()
        stats_daily_entries = len(self.daily_drive)
        _LOGGER.info(
            "Odometer processing stats: Storage Read Entries=%d, Odometer History Read=%d, Storage Write Entries=%d, Total daily entries=%d",
            read_storage_size,
            stats_read_odometer_history,
            stats_to_store,
            stats_daily_entries,
        )

        # Flag - exporting data
        if is_flag_active(self.ha_config_path, FLAG_EXPORT_ODOMETER):
            self.__export_csv_odometer(self.odometer_list)

        if is_flag_active(self.ha_config_path, FLAG_EXPORT_DAILY):
            self.__export_csv_daily_odometer(self.daily_drive)

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
