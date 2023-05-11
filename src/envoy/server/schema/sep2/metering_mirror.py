from typing import Optional

from pydantic_xml import element

from envoy.server.schema.sep2 import primitive_types, types
from envoy.server.schema.sep2.identification import IdentifiedObject
from envoy.server.schema.sep2.identification import List as Sep2List
from envoy.server.schema.sep2.identification import Resource
from envoy.server.schema.sep2.metering import Reading, ReadingSetBase


class MirrorUsagePointListResponse(Resource):
    pass


class MirrorUsagePointRequest(Resource):
    pass


class MirrorReadingSet(ReadingSetBase):
    readings: Optional[list[Reading]] = element()


class MeterReadingBase(IdentifiedObject):
    pass


class MirrorMeterReading(MeterReadingBase):
    lastUpdateTime: Optional[types.TimeType] = element()
    nextUpdateTime: Optional[types.TimeType] = element()
    reading: Optional[Reading] = element()
    mirrorReadingSet: Optional[list[MirrorReadingSet]] = element()


class MirrorMeterReadingList(Sep2List):
    mirrorMeterReadings: Optional[list[MirrorMeterReading]] = element()


class UsagePointBase(IdentifiedObject):
    roleFlags: int = element()  # This should be of type RoleFlagsType
    serviceCategoryKind: types.ServiceKind = element()
    status: int = element()


class MirrorUsagePoint(UsagePointBase):
    deviceLFDI: primitive_types.HexBinary160 = element()
    postRate: Optional[int] = element()
    mirrorMeterReadings: Optional[list[MirrorMeterReading]] = element()


class MirrorUsagePointList(Sep2List):
    pollrate: types.PollRateType = types.DEFAULT_POLLRATE
    mirrorUsagePoints: Optional[list[MirrorUsagePoint]] = element()
