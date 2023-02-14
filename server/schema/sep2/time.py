"""Time resource related
"""
from typing import Literal, Optional

from pydantic_xml import attr, element

from server.schema.sep2.base import Resource, TimeOffsetType, TimeQualityType, TimeType


class TimeResponse(Resource):
    # xsd
    href: Literal["/tm"] = attr()

    currentTime: TimeType = element()
    dstEndTime: TimeType = element()
    dstOffset: TimeOffsetType = element()
    dstStartTime: TimeType = element()
    localTime: Optional[TimeType] = element()
    quality: TimeQualityType = element()
    tzOffset: TimeOffsetType = element()
