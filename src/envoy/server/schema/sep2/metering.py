from enum import IntEnum
from typing import Optional

from pydantic_xml import element

from envoy.server.schema.sep2.base import BaseXmlModelWithNS, Resource


class AccumulationBehaviourType(IntEnum):
    """sep2 AccumulationBehaviourType type. All other values are reserved"""
    NOT_APPLICABLE = 0
    CUMULATIVE = 3
    DELTA_DATA = 4
    INDICATING = 6
    SUMMATION = 9
    INSTANTANEOUS = 12


class UomType(IntEnum):
    """Described in sep2 as:

    The following values are recommended values sourced from the unit of measure enumeration in IEC 61968-9 [61968].
    Other values from the unit of measure enumeration in IEC 61968-9 [61968] MAY be used."""
    NOT_APPLICABLE = 0
    CURRENT_AMPERES = 5
    TEMPERATURE_KELVIN = 6
    TEMPERATURE_CELSIUS = 23
    VOLTAGE = 29
    JOULES = 31
    FREQUENCY_HZ = 33
    REAL_POWER_WATT = 38
    VOLUME_CUBIC_METRE = 42
    APPARENT_POWER_VA = 61
    REACTIVE_POWER_VAR = 63
    DISPLACEMENT_POWER_FACTOR_COSTHETA = 65
    VOLTS_SQUARED = 67
    AMPERES_SQUARED = 69
    APPARENT_ENERGY_VAH = 71
    REAL_ENERGY_WATT_HOURS = 72
    REACTIVE_ENERGY_VARH = 73
    AVAILABLE_CHARGE_AMPERE_HOURS = 106
    VOLUME_CUBIC_FEET = 119
    VOLUME_CUBIC_FEET_PER_HOUR = 122
    VOLUME_CUBIC_METRE_PER_HOUR = 125
    VOLUME_US_GALLON = 128
    VOLUME_US_GALLON_PER_HOUR = 129
    VOLUME_IMPERIAL_GALLON = 130
    VOLUME_IMPERIAL_GALLON_PER_HOUR = 131
    BRITISH_THERMAL_UNIT = 132
    BRITISH_THERMAL_UNIT_PER_HOUR = 133
    VOLUME_LITER = 134
    VOLUME_LITER_PER_HOUR = 137


class CommodityType(IntEnum):
    """All other values reserved"""
    NOT_APPLICABLE = 0
    ELECTRICITY_SECONDARY_METERED_VALUE = 1
    ELECTRICITY_PRIMARY_METERED_VALUE = 2
    AIR = 4
    NATURAL_GAS = 7
    PROPANE = 8
    POTABLE_WATER = 9
    STEAM = 10
    WASTE_WATER = 11
    HEATING_FLUID = 12
    COOLING_FLUID = 13


class DataQualifierType(IntEnum):
    """All other values reserved"""
    NOT_APPLICABLE = 0
    AVERAGE = 2
    MAXIMUM = 8
    MINIMUM = 9
    STANDARD = 12
    STD_DEVIATION_OF_POPULATION = 29
    STD_DEVIATION_OF_SAMPLE = 30


class FlowDirectionType(IntEnum):
    """All other values reserved"""
    NOT_APPLICABLE = 0
    FORWARD = 1  # delivered to customer
    REVERSE = 19  # received from customer


class KindType(IntEnum):
    """All other values reserved"""
    NOT_APPLICABLE = 0
    CURRENCY = 3
    DEMAND = 8
    ENERGY = 12
    POWER = 37


class PhaseCode(IntEnum):
    """All other values reserved"""
    NOT_APPLICABLE = 0
    PHASE_C_S2 = 32
    PHASE_CN_S2N = 33
    PHASE_CA = 40
    PHASE_B = 64
    PHASE_BN = 65
    PHASE_BC = 66
    PHASE_A_S1 = 128
    PHASE_AN_S1N = 129
    PHASE_AB = 132
    PHASE_ABC = 224


class TOUType(IntEnum):
    """All other values reserved"""
    NOT_APPLICABLE = 0
    TOU_A = 1
    TOU_B = 2
    TOU_C = 3
    TOU_D = 4
    TOU_E = 5
    TOU_F = 6
    TOU_G = 7
    TOU_H = 8
    TOU_I = 9
    TOU_J = 10
    TOU_K = 11
    TOU_L = 12
    TOU_M = 13
    TOU_N = 14
    TOU_O = 15


class ConsumptionBlockType(IntEnum):
    """All other values reserved"""
    NOT_APPLICABLE = 0
    BLOCK_1 = 1
    BLOCK_2 = 2
    BLOCK_3 = 3
    BLOCK_4 = 4
    BLOCK_5 = 5
    BLOCK_6 = 6
    BLOCK_7 = 7
    BLOCK_8 = 8
    BLOCK_9 = 9
    BLOCK_10 = 10
    BLOCK_11 = 11
    BLOCK_12 = 12
    BLOCK_13 = 13
    BLOCK_14 = 14
    BLOCK_15 = 15
    BLOCK_16 = 16


class UnitValueType(BaseXmlModelWithNS):
    """Type for specification of a specific value, with units and power of ten multiplier."""
    multiplier: int = element()
    unit: UomType = element()
    value: int = element()


class ReadingType(Resource):
    """Type of data conveyed by a specific Reading. See IEC 61968 Part 9 Annex C for full definitions
    of these values. """
    accumulationBehaviour: Optional[AccumulationBehaviourType] = element()
    calorificValue: Optional[UnitValueType] = element()
    commodity: Optional[CommodityType] = element()
    conversionFactor: Optional[UnitValueType] = element()
    dataQualifier: Optional[DataQualifierType] = element()
    flowDirection: Optional[FlowDirectionType] = element()
    intervalLength: Optional[int] = element()
    kind: Optional[KindType] = element()
    maxNumberOfIntervals: Optional[int] = element()
    numberOfConsumptionBlocks: Optional[int] = element()
    numberOfTouTiers: Optional[int] = element()
    phase: Optional[PhaseCode] = element()
    powerOfTenMultiplier: Optional[int] = element()
    subIntervalLength: Optional[int] = element()
    supplyLimit: Optional[int] = element()
    tieredConsumptionBlocks: Optional[bool] = element()
    uom: Optional[UomType] = element()
