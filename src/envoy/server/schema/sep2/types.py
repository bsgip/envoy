from enum import IntEnum, IntFlag, auto
from functools import reduce
from typing import Optional

from pydantic_xml import attr, element

from envoy.server.schema.sep2 import base, primitive_types


class PENType(int):
    pass


class VersionType(int):
    pass


class mRIDType(primitive_types.HexBinary128):
    pass


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


class SubscribableType(IntEnum):
    resource_does_not_support_subscriptions = 0
    resource_supports_non_conditional_subscriptions = 1
    resource_supports_conditional_subscriptions = 2
    resource_supports_both_conditional_and_non_conditional_subscriptions = 3


class UnitValueType(base.BaseXmlModelWithNS):
    """Type for specification of a specific value, with units and power of ten multiplier."""

    multiplier: int = element()
    unit: UomType = element()
    value: int = element()


class PollRateType(base.BaseXmlModelWithNS):
    pollRate: Optional[int] = attr()


DEFAULT_POLLRATE = PollRateType(pollRate=900)


class DeviceCategory(IntFlag):
    """DeviceCategory is a series of bit flags describing a category of EndDevice. Described in sep2"""

    PROGRAMMABLE_COMMUNICATING_THERMOSTAT = auto()
    STRIP_HEATERS = auto()
    BASEBOARD_HEATERS = auto()
    WATER_HEATER = auto()
    POOL_PUMP = auto()
    SAUNA = auto()
    HOT_TUB = auto()
    SMART_APPLIANCE = auto()
    IRRIGATION_PUMP = auto()
    MANAGED_COMMERCIAL_AND_INDUSTRIAL_LOADS = auto()
    SIMPLE_MISC_LOADS = auto()
    EXTERIOR_LIGHTING = auto()
    INTERIOR_LIGHTING = auto()
    LOAD_CONTROL_SWITCH = auto()
    ENERGY_MANAGEMENT_SYSTEM = auto()
    SMART_ENERGY_MODULE = auto()
    ELECTRIC_VEHICLE = auto()
    ELECTRIC_VEHICLE_SUPPLY_EQUIPMENT = auto()
    VIRTUAL_OR_MIXED_DER = auto()
    RECIPROCATING_ENGINE = auto()
    FUEL_CELL = auto()
    PHOTOVOLTAIC_SYSTEM = auto()
    COMBINED_HEAT_AND_POWER = auto()
    COMBINED_PV_AND_STORAGE = auto()
    OTHER_GENERATION_SYSTEM = auto()
    OTHER_STORAGE_SYSTEM = auto()


# The combination of ALL DeviceCategory bit flags
DEVICE_CATEGORY_ALL_SET: DeviceCategory = reduce(lambda a, b: a | b, DeviceCategory)  # type: ignore # py311 issue


class TimeType(int):
    # Unix time
    pass


class TimeOffsetType(int):
    # A sign time offset, typically applied to a TimeType value, expressed in seconds.
    pass


class TimeQualityType(IntEnum):
    authoritative_source = 3
    level_3_source = 4
    level_4_source = 5
    level_5_source = 6
    intentionally_uncoordinated = 7


class DateTimeIntervalType(base.BaseXmlModelWithNS):
    duration: int = element()
    start: TimeType = element()


class CurrencyCode(IntEnum):
    """Non exhaustive set of numerical ISO 4217 currency codes. Described in sep2 / ISO 4217"""

    NOT_APPLICABLE = 0
    AUSTRALIAN_DOLLAR = 36
    CANADIAN_DOLLAR = 124
    US_DOLLAR = 840
    EURO = 978


class PrimacyType(IntEnum):
    """Values possible for indication of Primary provider. Described in sep2.

    It's worth noting that Values 3-64 are reserved, values 65-191 are user definable and 192-255 are also reserved

    Lower numbers indicate higher priority"""

    IN_HOME_ENERGY_MANAGEMENT_SYSTEM = 0
    CONTRACTED_PREMISES_SERVICE_PROVIDER = 1


class ServiceKind(IntEnum):
    """sep2 ServiceKind type. All other values are reserved"""

    ELECTRICITY = 0
    GAS = 1
    WATER = 2
    TIME = 3
    PRESSURE = 4
    HEAT = 5
    COOLING = 6


class RoleFlagsType(IntFlag):
    """Specifies the roles that apply to a usage point. Described in sep2. Other bits reserved"""

    NONE = 0
    IS_MIRROR = auto()
    IS_PREMISES_AGGREGATION_POINT = auto()
    IS_PEV = auto()
    IS_DER = auto()
    IS_REVENUE_QUALITY = auto()
    IS_DC = auto()
    IS_SUBMETER = auto()


class ReasonCodeType(IntEnum):
    invalid_request_format = 0
    invalid_request_values = 1
    resource_limit_reached = 2
    conditional_subscription_field_not_supported = 3
    maximum_request_frequency_exceeded = 4

    # Custom values outside sep2 specification
    internal_error = 16384  # Unspecified error due to an issue with some internal logic/system


class OneHourRangeType(int):
    """A signed time offset, typically applied to a Time value, expressed in seconds, with range -3600 to 3600."""

    pass


class SignedPerCent(int):
    # Used for signed percentages, specified in hundredths of a percent, -10000 - 10000. (10000 = 100%)
    pass


class PerCent(int):
    # Used for percentages, specified in hundredths of a percent, 0 - 10000. (10000 = 100%)
    pass


class DERUnitRefType(IntEnum):
    """Specifies context for interpreting percent values:. All other values are reserved"""

    NOT_APPLICABLE = 0
    PERC_SET_MAX_W = 1
    PERC_SET_MAX_VAR = 2
    PERC_STAT_VAR_AVAIL = 3
    PERC_SET_EFFECTIVE_V = 4
    PERC_SET_MAX_CHARGE_RATE_W = 5
    PERC_SET_MAX_DISCHARGE_RATE_W = 6
    PERC_STAT_W_AVAIL = 7


class QualityFlagsType(IntFlag):
    """There is no corresponding definition of this within sep2 - it's instead outlined on the HexBinary16 definition
    of ReadingBase.qualityFlags"""

    NONE = 0
    VALID = auto()  # data that has gone through all required validation checks is now considered valid / verified
    MANUALLY_EDITED = auto()  # manually edited: Replaced or approved by a human
    ESTIMATED_BY_DAY = auto()  # value was replaced by a machine computed value based on analysis of historical data
    ESTIMATED_BY_LINEAR = auto()  # data value was computed using linear interp based on the readings before / after it
    QUESTIONABLE = auto()  # data that has failed one or more checks
    DERIVED = auto()  # data that has been calculated (using logic or mathematical operations), not measured directly
    FORECAST = auto()  # data that has been calculated as a projection or forecast of future readings
