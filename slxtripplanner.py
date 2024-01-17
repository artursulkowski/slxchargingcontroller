""" module for trip planned"""

from __future__ import annotations

from datetime import timedelta, datetime

import logging
import asyncio

from typing import Any


from homeassistant.core import (
    HomeAssistant,
)

from homeassistant.components.recorder import history


from homeassistant.helpers import storage


_LOGGER = logging.getLogger(__name__)


class SLXTripPlanner:
    def __init__(self):
        pass

    async def initialize(self, hass):
        store = storage.Store(hass, 1, "slxintegration_storage")
        data = await store.async_load()

        if data is None:
            # If no data is found, initialize with default values
            data = {"key1": "value1", "key2": "value2"}
            await store.async_save(data)

        # Access the stored data
        key1_value = data.get("key1")

        # Update and save data
        data["key1"] = "new_value1"
        await store.async_save(data)
        _LOGGER.warning(data)

        # Continue with the setup of your integration
        return True

    # from homeassistant.helpers import storage

    # async def async_setup(hass, config):
    #     # Initialize the storage
    #     store = storage.Store(hass, 1, 'your_integration_storage')

    #     # Read data from storage
    #     data = await store.async_load()

    #     if data is None:
    #         # If no data is found, initialize with default values
    #         data = {'key1': 'value1', 'key2': 'value2'}
    #         await store.async_save(data)

    #     # Access the stored data
    #     key1_value = data.get('key1')

    #     # Update and save data
    #     data['key1'] = 'new_value1'
    #     await store.async_save(data)

    #     # Continue with the setup of your integration
    #     return True

    ################### RECORDER ACCESS ########


# async def async_setup(hass, config):
#     # Get the history from the recorder for the last 24 hours
#     end_time = hass.datetime.now()
#     start_time = end_time - timedelta(hours=24)

#     events = await history.state_changes_during_period(hass, start_time, end_time)

#     # Process the events as needed
#     for event in events:
#         # Do something with each event
#         print(event)

#     # Continue with the setup of your integration
#     return True
