import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from dateutil import tz

logger = logging.getLogger(__name__)


@dataclass
class DaylightSavingsTimeInfo:
    dst_end: int  # Unix (UTC) timestamp at which daylight savings next ends begins (apply dst_offset)
    dst_start: int  # Unix (UTC) timestamp at which daylight savings next begins (remove dst_offset)
    dst_offset: int  # Daylight savings time offset (in seconds) from local time (if DST in effect), 0 otherwise.


def get_tz_key(dt: datetime) -> Optional[str]:
    """Extracts the tzinfo key for the specified datetime (if available) or None otherwise. Capable of handling
    pytz shim timezones or ZoneInfo timezones"""
    tzinfo = dt.tzinfo
    if tzinfo is None:
        logger.warn("No tzinfo specified on supplied datetime, returning zero dst info.")
        return None

    # tzlocal.get_localzone can return a _PytzShimTimezone which defines _key instead of key. Need to check
    # for this and respond accordingly
    if hasattr(tzinfo, 'key'):
        return getattr(tzinfo, 'key')
    elif hasattr(tzinfo, '_key'):
        return getattr(tzinfo, '_key')
    else:
        logger.warn(f"No timezone key accessible for supplied datetime's tzinfo: {tzinfo}")
        return None


def get_dst_info(now_time: datetime) -> DaylightSavingsTimeInfo:
    """Returns the start and end daylight savings time for the year of a specified time.

    Args:
        now_time (datetime.datetime): datetime with timezone for which daylight savings time details will be returned.

    Returns:
        DaylightSavingsTimeInfo:

    """

    # Big Caveat - this function depends on the internals of tzinfo in order to extract DST transition times. This isn't
    #              exactly best practice but there is no official way to extract this information. The alternative is
    #              pulling in pytz JUST for this. Unit tests will hopefully keep us covered in case the internals change

    dst_zero = DaylightSavingsTimeInfo(0, 0, 0)

    tzinfo_key = get_tz_key(now_time)
    if tzinfo_key is None:
        return dst_zero

    tzif_obj = tz.gettz(tzinfo_key)
    if tzif_obj is None:
        logger.warn(f"Unknown timezone name {tzinfo_key}, returning zero dst info.")
        return dst_zero

    if now_time.tzinfo == ZoneInfo("UTC"):
        return dst_zero

    last_transition_idx = tzif_obj._find_last_transition(now_time) or 1  # type: ignore  # see caveat at top of func
    if last_transition_idx >= (len(tzif_obj._trans_list_utc) - 1):  # type: ignore  # see caveat at top of func
        # No info about next transition - likely not a DST tz
        return dst_zero

    # If we are in a DST period (i.e. dst offset total seconds > 0), then the last transition index is the start of the
    # dst period and the next index is end.
    now_dst = now_time.dst()
    dst_offset_total_seconds: int = 0
    if now_dst is not None:
        dst_offset_total_seconds = int(now_dst.total_seconds())

    if dst_offset_total_seconds > 0:
        dst_start_time = tzif_obj._trans_list_utc[last_transition_idx]  # type: ignore  # see caveat at top of func
        dst_end_time = tzif_obj._trans_list_utc[last_transition_idx + 1]  # type: ignore  # see caveat at top of func
    else:
        dst_start_time = tzif_obj._trans_list_utc[last_transition_idx + 1]  # type: ignore  # see caveat at top of func
        dst_end_time = tzif_obj._trans_list_utc[last_transition_idx + 2]  # type: ignore  # see caveat at top of func

    return DaylightSavingsTimeInfo(dst_end=dst_end_time, dst_start=dst_start_time, dst_offset=dst_offset_total_seconds)
