"""Calendar entities for SlxChargingController"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import Any
import json


from homeassistant.components.calendar import (
    EVENT_END,
    EVENT_RRULE,
    EVENT_START,
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import SLXChgCtrlUpdateCoordinator
from .slxtripplanner import SLXTripPlanner

_LOGGER = logging.getLogger(__name__)


def round_floats(obj):
    if isinstance(obj, float):
        return round(obj, 2)  # Adjust the number of decimal places as needed
    elif isinstance(obj, dict):
        return {k: round_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [round_floats(x) for x in obj]
    else:
        return obj


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the local calendar platform."""
    # store = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: SLXChgCtrlUpdateCoordinator = hass.data[DOMAIN][config_entry.unique_id]

    name = "slxcalendar"
    entity = SLXCalendarEntity(coordinator, name, unique_id=config_entry.entry_id)
    async_add_entities([entity], True)


class SLXCalendarEntity(CalendarEntity):
    """A calendar entity backed by a local iCalendar file."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        CalendarEntityFeature.CREATE_EVENT
        | CalendarEntityFeature.DELETE_EVENT
        | CalendarEntityFeature.UPDATE_EVENT
    )

    # TODO - I should add here SLXTripPlanner!
    def __init__(
        self,
        coordinator,
        #    store: LocalCalendarStore,
        #    calendar: Calendar,
        name: str,
        unique_id: str,
    ) -> None:
        """Initialize LocalCalendarEntity."""
        #        self._store = store
        #        self._calendar = calendar
        self._coordinator: SLXChgCtrlUpdateCoordinator = coordinator
        self._tripplanner: SLXTripPlanner = coordinator.trip_planner
        self._event: CalendarEvent | None = None
        self._attr_name = name.capitalize()
        self._attr_unique_id = unique_id

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        tmp_list = []

        daily_trips = self._tripplanner.get_daily_trips(
            start_date.date(), end_date.date()
        )
        # translate daily trips into dictionary - will be easier to combine it with predictor

        daily_trips_dict: dict[date, float] = {}
        for trip_date, distance in daily_trips:
            daily_trips_dict[trip_date] = distance

        # go through dates and check if we have distance and prediction information available.
        current_date = start_date.date()
        while current_date <= end_date.date():
            distance: float = None
            if current_date in daily_trips_dict:
                distance = daily_trips_dict[current_date]

            prediction: list[float] = None
            if current_date in self._tripplanner.predictor_output:
                prediction = self._tripplanner.predictor_output[current_date]

            if distance is not None or prediction is not None:
                summary = ""
                if distance is not None:
                    summary += f"Trip: {distance:.1f}km"
                if prediction is not None:
                    if len(summary) > 0:
                        summary += " "
                    summary += f"Prediction: {prediction[0]:.1f}km"
                information_object = {}
                if distance is not None:
                    information_object["dailytrip"] = distance
                if prediction is not None:
                    information_object["prediction"] = prediction

                description = json.dumps(round_floats(information_object))
                ce = CalendarEvent(current_date, current_date, summary, description)
                tmp_list.append(ce)

            current_date += timedelta(days=1)
        return tmp_list
