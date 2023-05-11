from typing import Optional

from pydantic_xml import attr, element

from envoy.server.schema.sep2 import primitive_types, types
from envoy.server.schema.sep2.identification import IdentifiedObject
from envoy.server.schema.sep2.identification import List as Sep2List
from envoy.server.schema.sep2.identification import Resource


class MirrorUsagePointListResponse(Resource):
    pass


class MirrorUsagePointRequest(Resource):
    pass


class ReadingBase(Resource):
    consumptionBlock: Optional[types.ConsumptionBlockType] = element(default=0)
    qualityFlags: Optional[primitive_types.HexBinary16] = element(default=primitive_types.HexBinary16("00"))
    timePeriod: Optional[types.DateTimeIntervalType] = element()
    touTier: Optional[types.TOUType] = element(default=0)
    value: Optional[int] = element()


class Reading(ReadingBase):
    subscribable: Optional[types.SubscribableType] = attr()
    localID: Optional[primitive_types.HexBinary16] = element()


class ReadingSetBase(IdentifiedObject):
    timePeriod: types.DateTimeIntervalType = element()


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
