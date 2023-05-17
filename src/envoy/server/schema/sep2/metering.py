from typing import Optional

from pydantic_xml import attr, element

from envoy.server.schema.sep2 import primitive_types, types
from envoy.server.schema.sep2.identification import IdentifiedObject, Resource


class ReadingBase(Resource):
    consumptionBlock: Optional[types.ConsumptionBlockType] = element(default=0)
    qualityFlags: Optional[primitive_types.HexBinary16] = element(
        default=primitive_types.HexBinary16("00")
    )  # string (hex encoded) form that maps to QualityFlagsType
    timePeriod: Optional[types.DateTimeIntervalType] = element()
    touTier: Optional[types.TOUType] = element(default=0)
    value: Optional[int] = element()


class Reading(ReadingBase):
    subscribable: Optional[types.SubscribableType] = attr()
    localID: Optional[primitive_types.HexBinary16] = element()


class ReadingSetBase(IdentifiedObject):
    timePeriod: types.DateTimeIntervalType = element()


class ReadingType(Resource):
    """Type of data conveyed by a specific Reading. See IEC 61968 Part 9 Annex C for full definitions
    of these values."""

    accumulationBehaviour: Optional[types.AccumulationBehaviourType] = element()
    calorificValue: Optional[types.UnitValueType] = element()
    commodity: Optional[types.CommodityType] = element()
    conversionFactor: Optional[types.UnitValueType] = element()
    dataQualifier: Optional[types.DataQualifierType] = element()
    flowDirection: Optional[types.FlowDirectionType] = element()
    intervalLength: Optional[int] = element()
    kind: Optional[types.KindType] = element()
    maxNumberOfIntervals: Optional[int] = element()
    numberOfConsumptionBlocks: Optional[int] = element()
    numberOfTouTiers: Optional[int] = element()
    phase: Optional[types.PhaseCode] = element()
    powerOfTenMultiplier: Optional[int] = element()
    subIntervalLength: Optional[int] = element()
    supplyLimit: Optional[int] = element()
    tieredConsumptionBlocks: Optional[bool] = element()
    uom: Optional[types.UomType] = element()


class UsagePointBase(IdentifiedObject):
    roleFlags: int = element()  # This should be of type RoleFlagsType
    serviceCategoryKind: types.ServiceKind = element()
    status: int = element()
