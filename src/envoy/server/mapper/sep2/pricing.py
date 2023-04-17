from datetime import date, datetime, time
from decimal import Decimal
from enum import IntEnum, auto
from itertools import islice, product

from envoy.server.crud.pricing import TariffGeneratedRateDailyStats
from envoy.server.mapper.common import generate_mrid
from envoy.server.mapper.exception import InvalidMappingError
from envoy.server.model.tariff import PRICE_DECIMAL_PLACES, PRICE_DECIMAL_POWER, Tariff, TariffGeneratedRate
from envoy.server.schema.sep2.base import Link, ListLink
from envoy.server.schema.sep2.metering import (
    CommodityType,
    ConsumptionBlockType,
    FlowDirectionType,
    ReadingType,
    TOUType,
    UomType,
)
from envoy.server.schema.sep2.pricing import (
    ConsumptionTariffIntervalResponse,
    PrimacyType,
    RateComponentListResponse,
    RateComponentResponse,
    RoleFlagsType,
    ServiceKind,
    TariffProfileResponse,
    TimeTariffIntervalListResponse,
    TimeTariffIntervalResponse,
)
from envoy.server.schema.sep2.time import DateTimeIntervalType


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
                "pricePowerOfTenMultiplier": PRICE_DECIMAL_PLACES,
                "rateCode": tariff.dnsp_code,
                "primacyType": PrimacyType.IN_HOME_ENERGY_MANAGEMENT_SYSTEM,
                "serviceCategoryKind": ServiceKind.ELECTRICITY,
                "RateComponentListLink": ListLink(href=tp_href + '/rc', all_=0),  # unspecified site' rate components
            }
        )


class PricingReadingType(IntEnum):
    """The different types of readings that can be priced"""
    IMPORT_ACTIVE_POWER_KWH = auto()
    EXPORT_ACTIVE_POWER_KWH = auto()
    IMPORT_REACTIVE_POWER_KVARH = auto()
    EXPORT_REACTIVE_POWER_KVARH = auto()


TOTAL_PRICING_READING_TYPES = len(PricingReadingType)  # The total number of PricingReadingType enums


class PricingReadingTypeMapper:
    @staticmethod
    def pricing_reading_type_href(rt: PricingReadingType) -> str:
        return f"/pricing/rt/{rt}"

    @staticmethod
    def extract_price(rt: PricingReadingType, rate: TariffGeneratedRate) -> Decimal:
        if (rt == PricingReadingType.IMPORT_ACTIVE_POWER_KWH):
            return rate.import_active_price
        elif (rt == PricingReadingType.EXPORT_ACTIVE_POWER_KWH):
            return rate.export_active_price
        elif (rt == PricingReadingType.IMPORT_REACTIVE_POWER_KVARH):
            return rate.import_reactive_price
        elif (rt == PricingReadingType.EXPORT_REACTIVE_POWER_KVARH):
            return rate.export_reactive_price
        else:
            raise InvalidMappingError(f"Unknown reading type {rt}")

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
            "mRID": generate_mrid(tariff_id, site_id, start_timestamp, pricing_reading),
            "description": pricing_reading.name,
            "roleFlags": RoleFlagsType(0),
            "ReadingTypeLink": Link(href=PricingReadingTypeMapper.pricing_reading_type_href(pricing_reading)),
            "TimeTariffIntervalListLink": ListLink(href=rc_href + "/tti", all_=total_rates)
        })

    @staticmethod
    def map_to_list_response(daily_rate_stats: TariffGeneratedRateDailyStats, skip_start: int, skip_end: int, tariff_id: int,
                             site_id: int) -> RateComponentListResponse:
        """Maps/creates a set of rate components under a RateComponentListResponse for a set of rate totals
        organised by date"""
        rc_list = []
        iterator = islice(
            product(daily_rate_stats.single_date_counts, PricingReadingType),  # Iterator
            skip_start,  # Start index
            (len(daily_rate_stats.single_date_counts) * TOTAL_PRICING_READING_TYPES) - skip_end  # End
        )
        for ((day, rate_count), pricing_type) in iterator:
            rc_list.append(RateComponentMapper.map_to_response(rate_count, tariff_id, site_id, pricing_type, day))

        return RateComponentListResponse.validate({
            "all_": daily_rate_stats.total_distinct_dates * TOTAL_PRICING_READING_TYPES,
            "results": len(rc_list),
            "RateComponent": rc_list
        })


class ConsumptionTariffIntervalMapper:
    """This is a fully 'Virtual' entity that doesnt exist in the DB. Instead we create them based on a fixed price"""
    @staticmethod
    def database_price_to_sep2(price: Decimal) -> int:
        """Converts a database price ($1.2345) to a sep2 price integer by multiplying it by the price power of 10
        according to the value of PRICE_DECIMAL_PLACES"""
        return int(price * PRICE_DECIMAL_POWER)

    @staticmethod
    def instance_href(tariff_id: int, site_id: int, pricing_reading: PricingReadingType, day: date,
                      time_of_day: time, price: Decimal):
        """Returns the href for a single instance of a ConsumptionTariffIntervalResponse at a set price"""
        base = ConsumptionTariffIntervalMapper.list_href(tariff_id, site_id, pricing_reading, day, time_of_day, price)
        return f"{base}/1"

    @staticmethod
    def list_href(tariff_id: int, site_id: int, pricing_reading: PricingReadingType, day: date,
                  time_of_day: time, price: Decimal):
        """Returns the href for a list that will hold a single instance of a ConsumptionTariffIntervalResponse at a
        set price"""
        start_date = day.isoformat()
        start_time = time_of_day.isoformat("minutes")
        sep2_price = ConsumptionTariffIntervalMapper.database_price_to_sep2(price)
        return f"/tp/{tariff_id}/{site_id}/rc/{start_date}/{pricing_reading}/tti/{start_time}/cti/{sep2_price}"

    @staticmethod
    def map_to_response(tariff_id: int, site_id: int, pricing_rt: PricingReadingType, day: date,
                        time_of_day: time, price: Decimal) -> ConsumptionTariffIntervalResponse:
        """Returns a ConsumptionTariffIntervalResponse with price being set to an integer by adjusting to
        PRICE_DECIMAL_PLACES"""
        href = ConsumptionTariffIntervalMapper.instance_href(tariff_id, site_id, pricing_rt, day, time_of_day, price)
        return ConsumptionTariffIntervalResponse.validate({
            "href": href,
            "consumptionBlock": ConsumptionBlockType.NOT_APPLICABLE,
            "price": ConsumptionTariffIntervalMapper.database_price_to_sep2(price),
            "startValue": 0,
        })


class TimeTariffIntervalMapper:
    @staticmethod
    def instance_href(tariff_id: int, site_id: int, day: date,
                      pricing_reading: PricingReadingType, time_of_day: time):
        """Creates a href that identify a single TimeTariffIntervalResponse with the specified values"""
        start_date = day.isoformat()
        start_time = time_of_day.isoformat("minutes")
        return f"/tp/{tariff_id}/{site_id}/rc/{start_date}/{pricing_reading}/tti/{start_time}"

    @staticmethod
    def map_to_response(rate: TariffGeneratedRate, pricing_reading: PricingReadingType) -> TimeTariffIntervalResponse:
        """Creates a new TimeTariffIntervalResponse for the given rate and specific price reading"""
        start_d = rate.start_time.date()
        start_t = rate.start_time.time()
        price = PricingReadingTypeMapper.extract_price(pricing_reading, rate)
        href = TimeTariffIntervalMapper.instance_href(rate.tariff_id, rate.site_id, start_d, pricing_reading, start_t)
        list_href = ConsumptionTariffIntervalMapper.list_href(rate.tariff_id, rate.site_id, pricing_reading, start_d,
                                                              start_t, price)
        return TimeTariffIntervalResponse.validate({
            "href": href,
            "mRID": f"{rate.tariff_generated_rate_id:x}",
            "version": 0,
            "description": rate.start_time.isoformat(),
            "touTier": TOUType.NOT_APPLICABLE,
            "creationTime": int(rate.changed_time.timestamp()),
            "interval": DateTimeIntervalType(start=int(rate.start_time.timestamp()), duration=rate.duration_seconds),
            "ConsumptionTariffIntervalListLink": ListLink(href=list_href, all_=1),  # single rate
        })

    @staticmethod
    def map_to_list_response(rates: list[TariffGeneratedRate], pricing_reading: PricingReadingType,
                             total: int) -> TimeTariffIntervalListResponse:
        """Creates a TimeTariffIntervalListResponse for a single page of entities."""
        return TimeTariffIntervalListResponse.validate({
            "all_": total,
            "results": len(rates),
            "TimeTariffInterval": [TimeTariffIntervalMapper.map_to_response(rate, pricing_reading) for rate in rates]
        })
