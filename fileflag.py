""" module for handling fileflags"""

import os
import logging


ROOT_DIRECTORY = "/workspaces/core/"
INTEGRATION_DIR = "config/custom_components/slxchargingcontroller/"
FLAG_DIR = "data/"

FULL_FLAG_DIR = ROOT_DIRECTORY + INTEGRATION_DIR + FLAG_DIR
FLAG_PREFIX = "flag_"
FLAG_PREFIX_ONCE = "flagonce_"

# flags to be used:
FLAG_CLEAR_STORAGE = "clear_storage"
FLAG_EXPORT_ODOMETER = "export_odometer"

_LOGGER = logging.getLogger(__name__)


def is_flag_active(flagname: str) -> bool:
    """Check if file flag exists.

    Check if given file flag exists. If it's once per time flag, it will be automatically deleted.
    Don't call this function more than onces in the flow as "flagonce will be removed after first check
    """
    _LOGGER.info("Checking flag %s", flagname)
    if os.path.isfile(FULL_FLAG_DIR + FLAG_PREFIX + flagname):
        _LOGGER.debug("Flag %s exists", flagname)
        return True

    flag_once_full_name = FULL_FLAG_DIR + FLAG_PREFIX_ONCE + flagname
    if os.path.isfile(flag_once_full_name):
        _LOGGER.debug("Flag ONCE %s exists", flagname)
        try:
            os.remove(flag_once_full_name)
        except OSError as e:
            _LOGGER.warning(
                "Failed to remove flag file: %s, error: %s",
                flag_once_full_name,
                e.strerror,
            )
        return True
    return False
