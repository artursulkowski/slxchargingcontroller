"""Calendar entities for SlxChargingController"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import Any


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

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the local calendar platform."""
    # store = hass.data[DOMAIN][config_entry.entry_id]

    name = "slxcalendar"
    entity = SLXCalendarEntity(name, unique_id=config_entry.entry_id)
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
        #    store: LocalCalendarStore,
        #    calendar: Calendar,
        name: str,
        unique_id: str,
    ) -> None:
        """Initialize LocalCalendarEntity."""
        #        self._store = store
        #        self._calendar = calendar
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
        scope: timedelta = end_date - start_date
        num_days = scope.days + 1
        for i in range(0, num_days):
            current_start = start_date + timedelta(days=i)
            current_event_time = datetime(
                current_start.year, current_start.month, current_start.day, hour=13 + i
            )
            current_event_time_end = current_event_time + timedelta(seconds=3600 * 2)
            if i != 2:
                ce = CalendarEvent(
                    dt_util.as_local(current_event_time),
                    dt_util.as_local(current_event_time_end),
                    "short summary",
                    "ble ble description",
                )
            else:
                current_date: date = current_event_time.date()
                # check all day event
                ce = CalendarEvent(
                    current_date,
                    current_date,
                    "short summary",
                    "ble ble description",
                )

            _LOGGER.warning(ce)
            tmp_list.append(ce)
            if i == 0:
                self._event = ce
        return tmp_list

        # start_date.day()

        # events = self._calendar.timeline_tz(start_date.tzinfo).overlapping(
        #     start_date,
        #     end_date,
        # )
        # return [_get_calendar_event(event) for event in events]


# def _parse_event(event: dict[str, Any]) -> Event:
#     """Parse an ical event from a home assistant event dictionary."""
#     if rrule := event.get(EVENT_RRULE):
#         event[EVENT_RRULE] = Recur.from_rrule(rrule)

#     # This function is called with new events created in the local timezone,
#     # however ical library does not properly return recurrence_ids for
#     # start dates with a timezone. For now, ensure any datetime is stored as a
#     # floating local time to ensure we still apply proper local timezone rules.
#     # This can be removed when ical is updated with a new recurrence_id format
#     # https://github.com/home-assistant/core/issues/87759
#     for key in (EVENT_START, EVENT_END):
#         if (
#             (value := event[key])
#             and isinstance(value, datetime)
#             and value.tzinfo is not None
#         ):
#             event[key] = dt_util.as_local(value).replace(tzinfo=None)

#     try:
#         return Event(**event)
#     except CalendarParseError as err:
#         _LOGGER.debug("Error parsing event input fields: %s (%s)", event, str(err))
#         raise vol.Invalid("Error parsing event input fields") from err


# def _get_calendar_event(event: Event) -> CalendarEvent:
#     """Return a CalendarEvent from an API event."""
#     start: datetime | date
#     end: datetime | date
#     if isinstance(event.start, datetime) and isinstance(event.end, datetime):
#         start = dt_util.as_local(event.start)
#         end = dt_util.as_local(event.end)
#         if (end - start) <= timedelta(seconds=0):
#             end = start + timedelta(minutes=30)
#     else:
#         start = event.start
#         end = event.end
#         if (end - start) < timedelta(days=0):
#             end = start + timedelta(days=1)

#     return CalendarEvent(
#         summary=event.summary,
#         start=start,
#         end=end,
#         description=event.description,
#         uid=event.uid,
#         rrule=event.rrule.as_rrule_str() if event.rrule else None,
#         recurrence_id=event.recurrence_id,
#         location=event.location,
#     )
