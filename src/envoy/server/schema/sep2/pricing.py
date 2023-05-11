from typing import Optional

from pydantic_xml import element

from envoy.server.schema.sep2.event import RandomizableEvent
from envoy.server.schema.sep2.identification import IdentifiedObject, Link
from envoy.server.schema.sep2.identification import List as SepList
from envoy.server.schema.sep2.identification import ListLink, Resource
from envoy.server.schema.sep2.types import (
    ConsumptionBlockType,
    CurrencyCode,
    PrimacyType,
    ServiceKind,
    TOUType,
    UnitValueType,
)


class TariffProfileResponse(IdentifiedObject, tag="TariffProfile"):
    """A schedule of charges; structure that allows the definition of tariff structures such as step (block) and
    time of use (tier) when used in conjunction with TimeTariffInterval and ConsumptionTariffInterval."""

    currency: Optional[CurrencyCode] = element()
    pricePowerOfTenMultiplier: Optional[int] = element()
    primacyType: Optional[PrimacyType] = element()
    rateCode: Optional[str] = element()
    serviceCategoryKind: ServiceKind = element()

    RateComponentListLink: Optional[ListLink] = element()


class RateComponentResponse(IdentifiedObject, tag="RateComponent"):
    """Specifies the applicable charges for a single component of the rate, which could be generation price or
    consumption price, for example."""

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
