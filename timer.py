""" module for SlxTimer """

from homeassistant.helpers.event import async_call_later
from homeassistant.core import HomeAssistant
from datetime import timedelta
from collections.abc import Callable


class SlxTimer:
    def __init__(
        self,
        hass: HomeAssistant,
        logger,
        default_time: timedelta,
        timer_callback: Callable[[], None],
    ):
        self.hass = hass
        self.logger = logger
        self.wait_time: timedelta = default_time
        self.timer_callback = timer_callback
        self.unsub_callback: Callable[[], None] = None

    def schedule_timer(self, new_wait_time: timedelta = None):
        if self.unsub_callback is not None:
            self.unsub_callback()
            self.unsub_callback = None
            self.logger.debug("Cancel timer %s before scheduling again", __name__)
        wait_time_to_use = self.wait_time
        if new_wait_time is not None:
            wait_time_to_use = new_wait_time
        self.unsub_callback = async_call_later(
            self.hass, wait_time_to_use, self.timer_callback
        )

    def cancel_timer(self):
        if self.unsub_callback is not None:
            self.unsub_callback()
            self.unsub_callback = None
            self.logger.debug("Canceled timer %s", __name__)
        else:
            self.logger.debug("Ignore canceling timer %s", __name__)
