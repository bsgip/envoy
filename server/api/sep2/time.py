import datetime

import pytz
from fastapi import APIRouter, Request
from tzlocal import get_localzone

from server.api.response import XmlResponse
from server.schema.sep2.time import TimeResponse

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

    # Get tzOffset, the non daylight savings time displacement from UTC in seconds.
    random_non_dst_time = timezone.localize(datetime.datetime(2020, 6, 28, 15, 25))
    tz_offset = int(random_non_dst_time.utcoffset().total_seconds())

    quality = 4

    time_dict = {
        "href": request.url.path,
        "currentTime": int(now_time.timestamp()),
        "dstEndTime": dst_info["dst_end"],
        "dstOffset": dst_info["dst_offset"],
        "dstStartTime": dst_info["dst_start"],
        "quality": quality,
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
    # Get timezone information
    timezone_info = pytz.timezone(now_time.tzinfo.zone)

    # Is timezone UTC? It's the default if a timezone can't be found. And it doesn't have the
    # attribute _utc_transition_times, as it has no daylight savings.
    if timezone_info in [pytz.UTC, pytz.utc, pytz.timezone("Etc/UTC")]:
        dst_info = {"dst_end": 0, "dst_start": 0, "dst_offset": 0}
        return dst_info

    # Get the transition times in and out of daylight savings. These are in UTC
    transition_times = timezone_info._utc_transition_times
    transition_times.sort(reverse=False)

    # This is in UTC too
    current_year = now_time.year

    # Get the first daylight savings transitions for the current year. This would be the end of
    # daylight savings in the southern hemisphere.
    dst_end_time_index, dst_end_time = next(
        ((i, t) for (i, t) in enumerate(transition_times) if t.year == current_year),
        (None, None),
    )

    # Get the second daylight savings transition for the current year. This would be the start of
    # daylight savings in the southern hemisphere
    # Running the check again in case a jurisdiction decides to stop daylight savings
    if dst_end_time is None:
        dst_start_time = None
        dst_offset = 0
    else:
        dst_start_time_index = dst_end_time_index - 1
        dst_start_time = transition_times[dst_start_time_index]

        # Get the timezone offset. This should be usually be 1 hour
        dst_offset = int(
            timezone_info._transition_info[dst_start_time_index][1].total_seconds()
        )

        # Convert dst_start_time to unixtime
        if dst_start_time is not None:
            dst_start_time = int(dst_start_time.timestamp())

        if dst_end_time is not None:
            dst_end_time = int(dst_end_time.timestamp())

    # Put the start and end times in a dict to return
    dst_info = {
        "dst_end": dst_end_time + now_time.utcoffset().seconds,
        "dst_start": dst_start_time + now_time.utcoffset().seconds - dst_offset,
        "dst_offset": dst_offset,
    }

    return dst_info
