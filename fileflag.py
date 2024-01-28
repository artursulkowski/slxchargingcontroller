""" module for handling fileflags"""

import os
import logging


FLAG_DIR = "custom_components/slxchargingcontroller/data/"

FLAG_PREFIX = "flag_"
FLAG_PREFIX_ONCE = "flagonce_"

# flags to be used:
FLAG_CLEAR_STORAGE = "clear_storage"
FLAG_EXPORT_ODOMETER = "export_odometer"

_LOGGER = logging.getLogger(__name__)


def is_flag_active(ha_config_path: str, flagname: str) -> bool:
    """Check if file flag exists.

    Check if given file flag exists. If it's once per time flag, it will be automatically deleted.
    Don't call this function more than onces in the flow as "flagonce will be removed after first check
    """
    full_path = ha_config_path + "/" + FLAG_DIR

    _LOGGER.info("Checking flag %s", flagname)
    if os.path.isfile(full_path + FLAG_PREFIX + flagname):
        _LOGGER.debug("Flag %s exists", flagname)
        return True

    flag_once_full_name = full_path + FLAG_PREFIX_ONCE + flagname
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
