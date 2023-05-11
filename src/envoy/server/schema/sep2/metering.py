from typing import Optional

from pydantic_xml import element

from envoy.server.schema.sep2 import types
from envoy.server.schema.sep2.identification import Resource


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
