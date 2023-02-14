import enum
from typing import Optional

from pydantic_xml import BaseXmlModel, attr, element

""" Abstract
"""
nsmap = {"": "urn:ieee:std:2030.5:ns"}


class BaseXmlModelWithNS(BaseXmlModel, nsmap=nsmap):
    pass


""" Resource
"""


class PollRateType(BaseXmlModelWithNS):
    pollRate: Optional[int] = attr()


class Resource(BaseXmlModelWithNS):
    pass


class PENType(int):
    pass


class VersionType(int):
    pass


class mRIDType(int):
    pass


class IdentifiedObject(Resource):
    description: Optional[str]
    mRID: mRIDType
    version: Optional[VersionType]


""" Time
"""


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
