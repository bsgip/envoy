from enum import IntEnum, IntFlag, auto
from typing import Optional

from pydantic_xml import element

from envoy.server.schema.sep2.base import IdentifiedObject, Link
from envoy.server.schema.sep2.base import List as SepList
from envoy.server.schema.sep2.base import ListLink, Resource
from envoy.server.schema.sep2.event import RandomizableEvent
from envoy.server.schema.sep2.metering import ConsumptionBlockType, TOUType, UnitValueType


class CurrencyCode(IntEnum):
    """Non exhaustive set of numerical ISO 4217 currency codes. Described in sep2 / ISO 4217"""
    NOT_APPLICABLE = 0
    AUSTRALIAN_DOLLAR = 36
    CANADIAN_DOLLAR = 124
    US_DOLLAR = 840
    EURO = 978


class PrimacyType(IntEnum):
    """Values possible for indication of Primary provider. Described in sep2.

    It's worth noting that Values 3-64 are reserved, values 65-191 are user defineable and 192-255 are also reserved

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


class TariffProfileResponse(IdentifiedObject, tag="TariffProfile"):
    """A schedule of charges; structure that allows the definition of tariff structures such as step (block) and
    time of use (tier) when used in conjunction with TimeTariffInterval and ConsumptionTariffInterval."""

    currency: Optional[CurrencyCode] = element()
    pricePowerOfTenMultiplier: Optional[int] = element()
    primacyType: PrimacyType = element()
    rateCode: Optional[str] = element()
    serviceCategoryKind: ServiceKind = element()

    RateComponentListLink: Optional[ListLink] = element()


class RateComponentResponse(IdentifiedObject, tag="RateComponent"):
    """Specifies the applicable charges for a single component of the rate, which could be generation price or
    consumption price, for example. """
    flowRateEndLimit: Optional[UnitValueType] = element()
    flowRateStartLimit: Optional[UnitValueType] = element()
    roleFlags: int = element()  # See RoleFlagsType
    ReadingTypeLink: Link = element()
    ActiveTimeTariffIntervalListLink: Optional[ListLink] = element()
    TimeTariffIntervalListLink: ListLink = element()


class TimeTariffIntervalResponse(RandomizableEvent, tag="TimeTariffInterval"):
    """Describes the time-differentiated portion of the RateComponent, if applicable, and provides the ability to
    specify multiple time intervals, each with its own consumption-based components and other attributes."""
    touTier: TOUType = element()
    ConsumptionTariffIntervalListLink: ListLink = element()


class ConsumptionTariffIntervalResponse(Resource, tag="ConsumptionTariffInterval"):
    """One of a sequence of thresholds defined in terms of consumption quantity of a service such as electricity,
    water, gas, etc. It defines the steps or blocks in a step tariff structure, where startValue simultaneously
    defines the entry value of this step and the closing value of the previous step. Where consumption is greater
    than startValue, it falls within this block and where consumption is less than or equal to startValue, it falls
    within one of the previous blocks."""
    consumptionBlock: ConsumptionBlockType = element()
    price: Optional[int] = element()  # The charge for this rate component, per unit of measure defined by the
                                      # associated ReadingType, in currency specified in TariffProfile.  # noqa e114
    startValue: int = element()  # The lowest level of consumption that defines the starting point of this consumption
                                 # step or block. Thresholds start at zero for each billing period. # noqa e114


class TariffProfileListResponse(SepList, tag="TariffProfileList"):
    TariffProfile: Optional[list[TariffProfileResponse]] = element()


class RateComponentListResponse(SepList, tag="RateComponentList"):
    RateComponent: Optional[list[RateComponentResponse]] = element()


class TimeTariffIntervalListResponse(SepList, tag="TimeTariffIntervalList"):
    TimeTariffInterval: Optional[list[TimeTariffIntervalResponse]] = element()


class ConsumptionTariffIntervalListResponse(SepList, tag="ConsumptionTariffIntervalList"):
    ConsumptionTariffInterval: Optional[list[ConsumptionTariffIntervalResponse]] = element()
