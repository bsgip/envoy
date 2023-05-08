"""Time resource related
"""
from typing import Literal, Optional

from pydantic_xml import attr, element

from envoy.server.schema.sep2.identification import Resource
from envoy.server.schema.sep2.types import TimeOffsetType, TimeQualityType, TimeType


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
