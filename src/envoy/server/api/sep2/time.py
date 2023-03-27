import datetime
import logging
from zoneinfo import ZoneInfo

from dateutil import tz
from fastapi import APIRouter, Request
from tzlocal import get_localzone

from server.api.response import XmlResponse
from server.schema.sep2.time import TimeQualityType, TimeResponse

logger = logging.getLogger(__name__)


router = APIRouter()


@router.head("/tm")
@router.get(
    "/tm",
    response_class=XmlResponse,
    response_model=TimeResponse,
    status_code=200,
)
async def get_time_resource(request: Request):
    """Returns the 2030.5 time resource response.

    Pages 77-78 Discusses how timezones should be implemented. Report in the hosts timezone. Devices
    have their own time resource.
    Pages 185-186 of IEEE Std 2030.5-2018. Figure B.14.

    Returns:
        fastapi.Response object

    """
    # Get the non-DST timezone from the host system
    timezone = get_localzone()

    # Define what the time is right now
    now_time = datetime.datetime.now(tz=timezone)

    # Get daylight savings info
    dst_info = get_dst_info(now_time)

    # Get tz offset withouth dst component
    tz_offset = now_time.utcoffset().total_seconds() - dst_info["dst_offset"]

    time_dict = {
        "href": request.url.path,
        "currentTime": int(now_time.timestamp()),
        "dstEndTime": dst_info["dst_end"],
        "dstOffset": dst_info["dst_offset"],
        "dstStartTime": dst_info["dst_start"],
        "quality": TimeQualityType.level_3_source,
        "tzOffset": tz_offset,
    }

    return XmlResponse(TimeResponse(**time_dict))


def get_dst_info(now_time: datetime.datetime) -> dict:
    """Returns the start and end daylight savings time for the year of a specified time.

    Args:
        now_time (datetime.datetime): datetime with timezone for which daylight savings time details will be returned.

    Returns:
        dst_info (dict):

    """
    dst_zero = {"dst_end": 0, "dst_start": 0, "dst_offset": 0}

    tzif_obj = tz.gettz(now_time.tzinfo._key)
    if tzif_obj is None:
        logger.warn("Unknown timezone name, returning zero dst info.")
        return dst_zero

    if now_time.tzinfo == ZoneInfo("UTC"):
        return dst_zero

    last_transition_idx = tzif_obj._find_last_transition(now_time) or 1
    if last_transition_idx >= (len(tzif_obj._trans_list_utc) - 1):
        # No info about next transition - likely not a DST tz
        return dst_zero

    # If we are in a DST period (i.e. dst offset total seconds > 0), then the last transition index is the start of the
    # dst period and the next index is end.
    dst_offset = now_time.dst().total_seconds()
    if dst_offset > 0:
        dst_start_time = tzif_obj._trans_list_utc[last_transition_idx]
        dst_end_time = tzif_obj._trans_list_utc[last_transition_idx + 1]
    else:
        dst_start_time = tzif_obj._trans_list_utc[last_transition_idx + 1]
        dst_end_time = tzif_obj._trans_list_utc[last_transition_idx + 2]

    # Put the start and end times in a dict to return
    dst_info = {
        "dst_end": dst_end_time,
        "dst_start": dst_start_time,
        "dst_offset": dst_offset,
    }

    return dst_info
