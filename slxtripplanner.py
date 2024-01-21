""" module for trip planned"""

from __future__ import annotations

from datetime import timedelta, datetime

import logging
import asyncio

from typing import Any


from homeassistant.core import HomeAssistant, Event

from homeassistant.components.recorder import history


from homeassistant.helpers import storage
import homeassistant.util.dt as dt_util


_LOGGER = logging.getLogger(__name__)


ODOMETER_STORAGE_KEY = "slxintegration_storage"


class SLXTripPlanner:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        pass

    async def initialize(self, odometer_entity: str):
        self.odometer_entity = odometer_entity
        self.odometer_list: list[datetime, float] = []

    async def process_historical_odometer(self):
        if self.process_historical_odometer is None:
            return
        _LOGGER.info("Process odometer, entity name = %s", self.odometer_entity)
        end_time = dt_util.utcnow()
        start_time = end_time - timedelta(days=7)

        events = await self.hass.async_add_executor_job(
            history.state_changes_during_period,
            self.hass,
            start_time,
            end_time,
            self.odometer_entity,
        )

        odometer_list: list[datetime, float] = []

        for event in events[self.odometer_entity]:
            try:
                value_odometer = float(event.state)
            except ValueError:
                value_odometer = None

            if value_odometer is not None and event.last_changed is not None:
                odometer_list.append((event.last_changed, value_odometer))
        _LOGGER.warning(odometer_list)

    async def read_storage(self) -> bool:
        store = storage.Store(self.hass, 1, ODOMETER_STORAGE_KEY)
        data_read = await store.async_load()
        # odometer_list: list[datetime, float] = []
        list_odo_read = data_read[self.odometer_entity]
        _LOGGER.info(list_odo_read)
        for x, y in list_odo_read:
            try:
                dt_obj = datetime.fromisoformat(x)
                _LOGGER.info("Time %s Value %.1f", x, y)
            except Exception:  # pylint: disable=broad-except
                dt_obj = None
                _LOGGER.warning("Invalid time format %s", x)
            if dt_obj is not None:
                self.odometer_list.append((dt_obj, y))
        return True
