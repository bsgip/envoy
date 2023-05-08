import datetime
import logging

from fastapi import APIRouter, Request
from tzlocal import get_localzone

from envoy.server.api.response import XmlResponse
from envoy.server.manager.time import get_dst_info
from envoy.server.schema.sep2.time import TimeQualityType, TimeResponse

logger = logging.getLogger(__name__)


router = APIRouter(tags=["time"])


@router.head("/tm")
@router.get(
    "/tm",
    response_class=XmlResponse,
    response_model=TimeResponse,
    status_code=200,
)
async def get_time_resource(request: Request):
    """Returns the sep2 time resource response.

    Pages 77-78 Discusses how timezones should be implemented. Report in the hosts timezone. Devices
    have their own time resource.
    Pages 185-186 of IEEE Std 2030.5-2018. Figure B.14.

    Args:
        request: FastAPI request object.

    Returns:
        fastapi.Response object

    """
    # Get the non-DST timezone from the host system
    timezone = get_localzone()

    # Define what the time is right now
    now_time = datetime.datetime.now(tz=timezone)

    # Get daylight savings info
    dst_info = get_dst_info(now_time)

    # Get tz offset without dst component
    now_utcoffset = now_time.utcoffset()
    if now_utcoffset is None:
        now_utcoffset = datetime.timedelta()
    tz_offset = now_utcoffset.total_seconds() - dst_info.dst_offset

    time_dict = {
        "href": request.url.path,
        "currentTime": int(now_time.timestamp()),
        "dstEndTime": dst_info.dst_end,
        "dstOffset": dst_info.dst_offset,
        "dstStartTime": dst_info.dst_start,
        "quality": TimeQualityType.level_3_source,
        "tzOffset": tz_offset,
    }

    return XmlResponse(TimeResponse(**time_dict))
