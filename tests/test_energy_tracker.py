# I can use BMW test_coordinator.py as a reference.
# use freezer to manipulate time

from homeassistant.core import HomeAssistant
from custom_components.slxchargingcontroller.chargingmanager import SlxEnergyTracker
import homeassistant.util.dt as dt_util
from time import sleep
from datetime import datetime, timedelta
from freezegun import freeze_time
import logging

_LOGGER = logging.getLogger(__name__)


# https://github.com/spulec/freezegun
def test_energy_tracker_timemachine():
    with freeze_time("Jan 1, 2023") as frozen_datetime:
        energy_tracker = SlxEnergyTracker(soc_before_energy=300, soc_after_energy=200)
        can_calculate: bool = False
        energy_tracker.connect_plug()
        can_calculate = energy_tracker.add_entry(10)
        frozen_datetime.tick(delta=timedelta(seconds=10))
        assert can_calculate is False
        energy_tracker.update_soc(dt_util.utcnow(), 50)
        _LOGGER.warning(dt_util.utcnow())

        frozen_datetime.tick(delta=timedelta(seconds=10))
        can_calculate = energy_tracker.add_entry(11)
        assert can_calculate is True
        added_energy = energy_tracker.get_added_energy()
        assert 0.499 < added_energy < 0.501


def test_energy_tracker_soc_before():
    with freeze_time("Jan 1, 2023") as frozen_datetime:
        energy_tracker = SlxEnergyTracker(soc_before_energy=300, soc_after_energy=200)
        can_calculate: bool = False
        energy_tracker.update_soc(dt_util.utcnow(), 50)

        frozen_datetime.tick(delta=timedelta(seconds=290))
        energy_tracker.connect_plug()
        can_calculate = energy_tracker.add_entry(10)
        assert can_calculate is True

        added_energy = energy_tracker.get_added_energy()
        assert added_energy == 0.0


def test_energy_tracker_soc_before_fail():
    with freeze_time("Jan 1, 2023") as frozen_datetime:
        energy_tracker = SlxEnergyTracker(soc_before_energy=300, soc_after_energy=200)
        can_calculate: bool = False
        energy_tracker.update_soc(dt_util.utcnow(), 50)
        frozen_datetime.tick(delta=timedelta(seconds=310))
        energy_tracker.connect_plug()
        can_calculate = energy_tracker.add_entry(10)
        assert can_calculate is False

        added_energy = energy_tracker.get_added_energy()
        assert added_energy is None


# https://github.com/spulec/freezegun
def test_energy_tracker_soc_after():
    with freeze_time("Jan 1, 2023") as frozen_datetime:
        energy_tracker = SlxEnergyTracker(soc_before_energy=300, soc_after_energy=200)
        can_calculate: bool = False

        energy_tracker.connect_plug()
        can_calculate = energy_tracker.add_entry(10)
        assert can_calculate is False

        frozen_datetime.tick(delta=timedelta(seconds=190))

        energy_tracker.update_soc(dt_util.utcnow(), 50)
        can_calculate = energy_tracker.calculate_estimated_session()
        assert can_calculate is True
        added_energy = energy_tracker.get_added_energy()
        assert added_energy == 0


def test_energy_tracker_soc_fail():
    with freeze_time("Jan 1, 2023") as frozen_datetime:
        energy_tracker = SlxEnergyTracker(soc_before_energy=300, soc_after_energy=200)
        can_calculate: bool = False
        energy_tracker.connect_plug()
        can_calculate = energy_tracker.add_entry(10)
        assert can_calculate is False

        frozen_datetime.tick(delta=timedelta(seconds=210))

        energy_tracker.update_soc(dt_util.utcnow(), 50)
        can_calculate = energy_tracker.calculate_estimated_session()
        assert can_calculate is False
        added_energy = energy_tracker.get_added_energy()
        assert added_energy is None
