from datetime import date, datetime
from math import isclose
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory, freeze_time

from custom_components.slxchargingcontroller.slxchargingplanner import (
    SLXChargingPlanner,
)
from homeassistant.core import HomeAssistant
# from homeassistant.helpers import storage


solar_prediction_test1 = {
    datetime.fromisoformat("2024-09-15T06:27:28+02:00"): 0,
    datetime.fromisoformat("2024-09-15T07:00:00+02:00"): 537,
    datetime.fromisoformat("2024-09-15T08:00:00+02:00"): 979,
    datetime.fromisoformat("2024-09-15T09:00:00+02:00"): 1352,
    datetime.fromisoformat("2024-09-15T10:00:00+02:00"): 1659,
    datetime.fromisoformat("2024-09-15T11:00:00+02:00"): 1916,
    datetime.fromisoformat("2024-09-15T12:00:00+02:00"): 2060,
    datetime.fromisoformat("2024-09-15T13:00:00+02:00"): 2092,
    datetime.fromisoformat("2024-09-15T14:00:00+02:00"): 1979,
    datetime.fromisoformat("2024-09-15T15:00:00+02:00"): 1749,
    datetime.fromisoformat("2024-09-15T16:00:00+02:00"): 1421,
    datetime.fromisoformat("2024-09-15T17:00:00+02:00"): 1052,
    datetime.fromisoformat("2024-09-15T18:00:00+02:00"): 656,
    datetime.fromisoformat("2024-09-15T19:00:00+02:00"): 378,
    datetime.fromisoformat("2024-09-15T19:07:09+02:00"): 0,
    datetime.fromisoformat("2024-09-16T06:29:07+02:00"): 0,
    datetime.fromisoformat("2024-09-16T07:15:00+02:00"): 398,
    datetime.fromisoformat("2024-09-16T08:00:00+02:00"): 820,
    datetime.fromisoformat("2024-09-16T09:00:00+02:00"): 1298,
    datetime.fromisoformat("2024-09-16T10:00:00+02:00"): 1693,
    datetime.fromisoformat("2024-09-16T11:00:00+02:00"): 1922,
    datetime.fromisoformat("2024-09-16T12:00:00+02:00"): 2133,
    datetime.fromisoformat("2024-09-16T13:00:00+02:00"): 2250,
    datetime.fromisoformat("2024-09-16T14:00:00+02:00"): 2089,
    datetime.fromisoformat("2024-09-16T15:00:00+02:00"): 1739,
    datetime.fromisoformat("2024-09-16T16:00:00+02:00"): 1291,
    datetime.fromisoformat("2024-09-16T17:00:00+02:00"): 840,
    datetime.fromisoformat("2024-09-16T19:04:46+02:00"): 0,
}


def test_fill_in_solar(hass: HomeAssistant) -> None:
    charging_planner = SLXChargingPlanner(hass)

    charging_planner.update_time_slots(
        datetime.fromisoformat("2024-09-15T07:00:00+02:00")
    )
    charging_planner.fill_in_solar_forecast(solar_prediction_test1)

    assert len(charging_planner._time_slots) == len(charging_planner._solar_forecasts)
