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
        daystart = start_date.date()
        dayfinish = end_date.date()

        daily_trips = self._tripplanner.daily_drive
        for trip_date, distance in daily_trips:
            if trip_date >= daystart and trip_date <= dayfinish:
                summary = f"Trip: {distance:.1f}km"
                information_object = {"dailytrip": distance}
                description = json.dumps(information_object)
                ce = CalendarEvent(trip_date, trip_date, summary, description)
                tmp_list.append(ce)
        return tmp_list
