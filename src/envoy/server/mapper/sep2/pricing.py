from datetime import date, datetime, time
from enum import Enum, IntEnum, auto

from envoy.server.mapper.exception import InvalidMappingError
from envoy.server.model.tariff import Tariff, TariffGeneratedRate
from envoy.server.schema.sep2.base import Link, ListLink
from envoy.server.schema.sep2.metering import CommodityType, FlowDirectionType, ReadingType, UnitValueType, UomType
from envoy.server.schema.sep2.pricing import (
    PrimacyType,
    RateComponentListResponse,
    RateComponentResponse,
    RoleFlagsType,
    ServiceKind,
    TariffProfileResponse,
)


class TariffProfileMapper:
    @staticmethod
    def map_to_response(tariff: Tariff) -> TariffProfileResponse:
        """Returns a mapped sep2 entity. The href to RateComponentListLink will be to an endpoint
        for returning rate components for an unspecified site id"""
        tp_href = f"/tp/{tariff.tariff_id}"
        return TariffProfileResponse.validate(
            {
                "href": tp_href,
                "mRID": f"{tariff.tariff_id:x}",
                "description": tariff.name,
                "currency": tariff.currency_code,
                "pricePowerOfTenMultiplier": 0,
                "rateCode": tariff.dnsp_code,
                "primacyType": PrimacyType.IN_HOME_ENERGY_MANAGEMENT_SYSTEM,
                "serviceCategoryKind": ServiceKind.ELECTRICITY,
                "RateComponentListLink": ListLink(href=tp_href + '/rc', all_=0),  # unspecified site' rate components
            }
        )


class PricingReadingType(IntEnum):
    """The different types of readings that can be priced"""
    IMPORT_ACTIVE_POWER_KWH = 1
    EXPORT_ACTIVE_POWER_KWH = 2
    IMPORT_REACTIVE_POWER_KVARH = 3
    EXPORT_REACTIVE_POWER_KVARH = 4


class PricingReadingTypeMapper:
    @staticmethod
    def pricing_reading_type_href(rt: PricingReadingType) -> str:
        return f"/pricing/rt/{rt}"

    @staticmethod
    def create_reading_type(rt: PricingReadingType) -> ReadingType:
        """Creates a named reading type based on a fixed enum describing the readings associated
        with a particular type of pricing"""
        href = PricingReadingTypeMapper.pricing_reading_type_href(rt)
        if rt == PricingReadingType.IMPORT_ACTIVE_POWER_KWH:
            return ReadingType.validate({
                "href": href,
                "commodity": CommodityType.ELECTRICITY_PRIMARY_METERED_VALUE,
                "flowDirection": FlowDirectionType.FORWARD,
                "powerOfTenMultiplier": 3,  # kilowatt hours
                "uom": UomType.REAL_ENERGY_WATT_HOURS
            })
        elif rt == PricingReadingType.EXPORT_ACTIVE_POWER_KWH:
            return ReadingType.validate({
                "href": href,
                "commodity": CommodityType.ELECTRICITY_PRIMARY_METERED_VALUE,
                "flowDirection": FlowDirectionType.REVERSE,
                "powerOfTenMultiplier": 3,  # kilowatt hours
                "uom": UomType.REAL_ENERGY_WATT_HOURS
            })
        elif rt == PricingReadingType.IMPORT_REACTIVE_POWER_KVARH:
            return ReadingType.validate({
                "href": href,
                "commodity": CommodityType.ELECTRICITY_SECONDARY_METERED_VALUE,
                "flowDirection": FlowDirectionType.FORWARD,
                "powerOfTenMultiplier": 3,  # kvar hours
                "uom": UomType.REACTIVE_ENERGY_VARH
            })
        elif rt == PricingReadingType.EXPORT_REACTIVE_POWER_KVARH:
            return ReadingType.validate({
                "href": href,
                "commodity": CommodityType.ELECTRICITY_SECONDARY_METERED_VALUE,
                "flowDirection": FlowDirectionType.REVERSE,
                "powerOfTenMultiplier": 3,  # kvar hours
                "uom": UomType.REACTIVE_ENERGY_VARH
            })
        else:
            raise InvalidMappingError(f"Unknown reading type {rt}")


class RateComponentMapper:
    @staticmethod
    def map_to_response(total_rates: int, tariff_id: int, site_id: int,
                        pricing_reading: PricingReadingType, day: date) -> RateComponentResponse:
        """Maps/Creates a single rate component response describing a single type of reading"""

        start_date = day.isoformat()
        start_timestamp = int(datetime.combine(day, time()).timestamp())
        rc_href = f"/tp/{tariff_id}/{site_id}/rc/{start_date}/{pricing_reading}"
        return RateComponentResponse.validate({
            "href": rc_href,
            "mRID": f"{tariff_id:x}{site_id:x}{start_timestamp:x}",
            "description": pricing_reading.name,
            "roleFlags": RoleFlagsType(0),
            "ReadingTypeLink": Link(href=PricingReadingTypeMapper.pricing_reading_type_href(pricing_reading)),
            "TimeTariffIntervalListLink": ListLink(href=rc_href + "/tti", all_=total_rates)
        })
