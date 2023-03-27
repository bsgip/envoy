"""Time resource related
"""
import enum
from typing import Literal, Optional

from pydantic_xml import attr, element

from envoy.server.schema.sep2.base import BaseXmlModelWithNS, Resource


# p170
class TimeType(int):
    # Unix time
    pass


# p170
class TimeOffsetType(int):
    # A sign time offset, typically applied to a TimeType value, expressed in seconds.
    pass


class TimeQualityType(enum.IntEnum):
    authoritative_source = 3
    level_3_source = 4
    level_4_source = 5
    level_5_source = 6
    intentionally_uncoordinated = 7


class DateTimeIntervalType(BaseXmlModelWithNS):
    duration: int
    start: TimeType


class TimeResponse(Resource, tag="Time"):
    # xsd
    href: Literal["/tm"] = attr()

    currentTime: TimeType = element()
    dstEndTime: TimeType = element()
    dstOffset: TimeOffsetType = element()
    dstStartTime: TimeType = element()
    localTime: Optional[TimeType] = element()
    quality: TimeQualityType = element()
    tzOffset: TimeOffsetType = element()
