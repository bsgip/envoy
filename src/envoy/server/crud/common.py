from datetime import datetime
from typing import Optional, Protocol, TypeVar
from zoneinfo import ZoneInfo

from sqlalchemy import Row


class HasStartTime(Protocol):
    start_time: datetime


T = TypeVar("T", bound=HasStartTime)


def localize_start_time(rate_and_tz: Optional[Row[tuple[T, str]]]) -> T:
    """Localizes a TariffGeneratedRate.start_time to be in the local timezone passed in as the second
    element in the tuple. Returns the TariffGeneratedRate (it will be modified in place)"""
    if rate_and_tz is None:
        raise ValueError("row is None")

    rate: T
    tz_name: str
    (rate, tz_name) = rate_and_tz
    tz = ZoneInfo(tz_name)
    rate.start_time = rate.start_time.astimezone(tz)
    return rate
