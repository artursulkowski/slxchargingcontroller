""" module for trip planned"""

from __future__ import annotations

from datetime import timedelta, datetime, date

import logging
import asyncio
import os

from typing import Any


from homeassistant.core import HomeAssistant, Event

from homeassistant.components.recorder import history


from homeassistant.helpers import storage
import homeassistant.util.dt as dt_util

from .const import ODOMETER_DAYS_BACK
from .fileflag import (
    is_flag_active,
    FLAG_CLEAR_STORAGE,
    FLAG_EXPORT_ODOMETER,
    FULL_FLAG_DIR,
)
import csv


_LOGGER = logging.getLogger(__name__)


ODOMETER_STORAGE_KEY = "slxintegration_storage"


def export_csv_odometer(filename: str, data: list[datetime, float]):
    with open(FULL_FLAG_DIR + filename, "w", newline="") as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["Timestamp", "Odometer"])
        csv_writer.writerows(
            [
                (timestamp.strftime("%Y-%m-%d %H:%M:%S"), value)
                for timestamp, value in data
            ]
        )


class SLXTripPlanner:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.odometer_list: list[datetime, float] = []
        self.daily_drive: list[date, float] = []

    async def initialize(self, odometer_entity: str):
        self.odometer_entity = odometer_entity

    # I will move capturing of data from recorder here so I can mock it easily in tests without the need to real with the recorder.
    # Other function should play more with extending storage using odometer data.
    async def _get_historical_odometer(self, daysback: int) -> list[(datetime, float)]:
        temp_list: list[(datetime, float)] = []
        _LOGGER.info("Process odometer, entity name = %s", self.odometer_entity)
        end_time = dt_util.utcnow()
        start_time = end_time - timedelta(days=daysback)

        events = await self.hass.async_add_executor_job(
            history.state_changes_during_period,
            self.hass,
            start_time,
            end_time,
            self.odometer_entity,
        )

        for event in events[self.odometer_entity]:
            try:
                value_odometer = float(event.state)
            except ValueError:
                value_odometer = None
            if value_odometer is not None and event.last_changed is not None:
                temp_list.append((event.last_changed, value_odometer))
        return temp_list

    async def clear_storage(self):
        store = storage.Store(self.hass, 1, ODOMETER_STORAGE_KEY)
        await store.async_remove()

    async def read_storage(self) -> bool:
        store = storage.Store(self.hass, 1, ODOMETER_STORAGE_KEY)
        data_read = await store.async_load()
        # odometer_list: list[datetime, float] = []
        if data_read is None:
            return False
        try:
            list_odo_read = data_read[self.odometer_entity]
        except KeyError:
            return False
        for x, y in list_odo_read:
            try:
                dt_obj = datetime.fromisoformat(x)
            except Exception:  # pylint: disable=broad-except
                dt_obj = None
                _LOGGER.warning("Invalid time format %s", x)
            if dt_obj is not None:
                self.odometer_list.append((dt_obj, y))
        return True

    async def write_storage(self) -> bool:
        store = storage.Store(self.hass, 1, ODOMETER_STORAGE_KEY)
        entries_to_write = len(self.odometer_list)
        if entries_to_write > 0:
            data_for_write = {self.odometer_entity: self.odometer_list}
            await store.async_save(data_for_write)
            _LOGGER.info("Writen odometer storage with %d entries", entries_to_write)
            return True
        return False

    async def capture_odometer(self):
        if is_flag_active(FLAG_CLEAR_STORAGE):
            _LOGGER.info("Detected flag for clearing the storage")
            await self.clear_storage()
        else:
            await self.read_storage()

        stats_read_storage: int = len(self.odometer_list)

        # merge two lists
        # assume that storage is time-sorted!
        # when re-writing historical odometer to the storage - check that it's time sorted!
        last_stored_date: datetime | None = None
        if len(self.odometer_list) > 0:
            last_stored_date = self.odometer_list[-1][0]

        max_days_back = ODOMETER_DAYS_BACK
        if last_stored_date is not None:
            time_now = dt_util.as_utc(dt_util.now())
            how_old_storage: timedelta = time_now - last_stored_date
            num_days = how_old_storage.days + 1
            if num_days < max_days_back:
                max_days_back = num_days

        _LOGGER.info("Capture odometer history from %d days", max_days_back)
        odometer_list = await self._get_historical_odometer(max_days_back)
        stats_read_odometer_history: int = len(odometer_list)

        for time, odometer in odometer_list:
            if (last_stored_date is None) or (time > last_stored_date):
                last_stored_date = time
                self.odometer_list.append((time, odometer))

        self.calculate_daily()
        stats_to_store: int = len(self.odometer_list)
        stats_daily_entries = len(self.daily_drive)
        if stats_to_store > stats_read_storage:
            await self.write_storage()
        _LOGGER.info(
            "Odometer processing stats: Storage Read Entries=%d, Odometer History Read=%d, Storage Write Entries=%d, Total daily entries=%d",
            stats_read_storage,
            stats_read_odometer_history,
            stats_to_store,
            stats_daily_entries,
        )

        if is_flag_active(FLAG_EXPORT_ODOMETER):
            current_time = dt_util.now()
            filename = f"odometer_{current_time.strftime('%Y%m%d_%H%M%S')}.csv"
            export_csv_odometer(filename, self.odometer_list)

    def calculate_daily(self):
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
