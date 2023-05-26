from typing import List, Optional

from pydantic_xml import element

from envoy.server.schema.sep2 import primitive_types, types
from envoy.server.schema.sep2.identification import IdentifiedObject
from envoy.server.schema.sep2.identification import List as Sep2List
from envoy.server.schema.sep2.identification import Resource
from envoy.server.schema.sep2.metering import Reading, ReadingSetBase, ReadingType, UsagePointBase


class MirrorReadingSet(ReadingSetBase):
    readings: Optional[List[Reading]] = element(tag="Reading")


class MeterReadingBase(IdentifiedObject):
    pass


class MirrorMeterReading(MeterReadingBase):
    lastUpdateTime: Optional[types.TimeType] = element()
    nextUpdateTime: Optional[types.TimeType] = element()
    reading: Optional[Reading] = element(tag="Reading")
    readingType: Optional[ReadingType] = element(tag="ReadingType")
    mirrorReadingSets: Optional[List[MirrorReadingSet]] = element(tag="MirrorReadingSet")


class MirrorUsagePoint(UsagePointBase):
    deviceLFDI: primitive_types.HexBinary160 = element()
    postRate: Optional[int] = element()
    mirrorMeterReadings: Optional[List[MirrorMeterReading]] = element(tag="MirrorMeterReading")


class MirrorUsagePointList(Sep2List):
    pollrate: types.PollRateType = types.DEFAULT_POLLRATE
    mirrorUsagePoints: Optional[List[MirrorUsagePoint]] = element(tag="MirrorUsagePoint")


class MirrorMeterReadingList(Sep2List):
    mirrorMeterReadings: Optional[List[MirrorMeterReading]] = element(tag="MirrorMeterReading")


class MirrorMeterReadingRequest(MirrorMeterReading, tag="MirrorMeterReading"):
    pass


# Unlike MirrorMeterReadingList this is a list resource is doesn't subclass Sep2List. The reasons is that clients
# don't need to specify the attributes 'all' or 'result' for the list resources they are posting
class MirrorMeterReadingListRequest(Resource, tag="MirrorMeterReadingList"):
    mirrorMeterReadings: Optional[List[MirrorMeterReading]] = element(tag="MirrorMeterReading")


class MirrorUsagePointListResponse(Sep2List, tag="MirrorUsagePointList"):
    mirrorUsagePoints: Optional[list[MirrorUsagePoint]] = element(tag="MirrorUsagePoint")
    pass


class MirrorUsagePointRequest(MirrorUsagePoint, tag="MirrorUsagePoint"):
    pass
