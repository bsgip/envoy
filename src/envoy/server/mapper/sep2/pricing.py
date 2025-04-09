from datetime import date, datetime, time, timezone
from decimal import Decimal
from itertools import islice, product
from typing import Iterator, Sequence

from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.event import EventStatus
from envoy_schema.server.schema.sep2.identification import Link, ListLink
from envoy_schema.server.schema.sep2.metering import ReadingType
from envoy_schema.server.schema.sep2.pricing import (
    ConsumptionTariffIntervalListResponse,
    ConsumptionTariffIntervalResponse,
    RateComponentListResponse,
    RateComponentResponse,
    TariffProfileListResponse,
    TariffProfileResponse,
    TimeTariffIntervalListResponse,
    TimeTariffIntervalResponse,
)
from envoy_schema.server.schema.sep2.types import (
    CommodityType,
    ConsumptionBlockType,
    FlowDirectionType,
    PrimacyType,
    RoleFlagsType,
    ServiceKind,
    SubscribableType,
    TOUType,
    UomType,
)

from envoy.server.exception import InvalidMappingError
from envoy.server.mapper.common import generate_href
from envoy.server.mapper.constants import PricingReadingType, ResponseSetType
from envoy.server.mapper.sep2.der import to_hex_binary
from envoy.server.mapper.sep2.mrid import MridMapper
from envoy.server.mapper.sep2.response import SPECIFIC_RESPONSE_REQUIRED, ResponseListMapper
from envoy.server.model.tariff import PRICE_DECIMAL_PLACES, PRICE_DECIMAL_POWER, Tariff, TariffGeneratedRate
from envoy.server.request_scope import BaseRequestScope, DeviceOrAggregatorRequestScope, SiteRequestScope


class TariffProfileMapper:
    @staticmethod
    def _map_to_response(
        scope: BaseRequestScope, tariff: Tariff, tp_href: str, total_rates: int
    ) -> TariffProfileResponse:
        return TariffProfileResponse.model_validate(
            {
                "href": tp_href,
                "mRID": MridMapper.encode_tariff_profile_mrid(scope, tariff.tariff_id),
                "description": tariff.name,
                "currency": tariff.currency_code,
                "pricePowerOfTenMultiplier": -PRICE_DECIMAL_PLACES,  # Needs to negate - $1 is encoded as 10000 * 10^-4
                "rateCode": tariff.dnsp_code,
                "primacyType": PrimacyType.IN_HOME_ENERGY_MANAGEMENT_SYSTEM,
                "serviceCategoryKind": ServiceKind.ELECTRICITY,
                "RateComponentListLink": ListLink(href=tp_href + "/rc", all_=total_rates),
            }
        )

    @staticmethod
    def map_to_response(
        scope: DeviceOrAggregatorRequestScope, tariff: Tariff, total_rates: int
    ) -> TariffProfileResponse:
        """Returns a mapped sep2 entity.

        This endpoint is designed to operate independent of a particular scope to allow encoding of multiple
        different sites. It's the responsibility of the caller to validate the scope before calling this."""
        tp_href = generate_href(uri.TariffProfileUri, scope, tariff_id=tariff.tariff_id, site_id=scope.display_site_id)
        return TariffProfileMapper._map_to_response(scope, tariff, tp_href, total_rates)

    @staticmethod
    def map_to_nosite_response(scope: BaseRequestScope, tariff: Tariff) -> TariffProfileResponse:
        """Returns a mapped sep2 entity. The href to RateComponentListLink will be to an endpoint
        for returning rate components for an unspecified site id"""
        tp_href = generate_href(uri.TariffProfileUnscopedUri, scope, tariff_id=tariff.tariff_id)
        return TariffProfileMapper._map_to_response(scope, tariff, tp_href, 0)

    @staticmethod
    def map_to_list_nosite_response(
        scope: BaseRequestScope, tariffs: Sequence[Tariff], total_tariffs: int
    ) -> TariffProfileListResponse:
        """Returns a list containing multiple sep2 entities. The href to RateComponentListLink will be to an endpoint
        for returning rate components for an unspecified site id"""
        return TariffProfileListResponse.model_validate(
            {
                "all_": total_tariffs,
                "results": len(tariffs),
                "TariffProfile": [TariffProfileMapper.map_to_nosite_response(scope, t) for t in tariffs],
            }
        )

    @staticmethod
    def map_to_list_response(
        scope: DeviceOrAggregatorRequestScope, tariffs: Iterator[tuple[Tariff, int]], total_tariffs: int
    ) -> TariffProfileListResponse:
        """Returns a list containing multiple sep2 entities. The href's will be to the site specific
        TimeTariffProfile and RateComponentListLink

        tariffs should be a list of tuples combining the individual tariffs with the underlying count
        of rate components

        This endpoint is designed to operate independent of a particular scope to allow encoding of multiple
        different sites. It's the responsibility of the caller to validate the scope before calling this."""
        tariff_profiles: list[TariffProfileResponse] = []
        tariffs_count: int = 0
        for tariff, rc_count in tariffs:
            tariff_profiles.append(TariffProfileMapper.map_to_response(scope, tariff, rc_count))
            tariffs_count = tariffs_count + 1

        return TariffProfileListResponse.model_validate(
            {
                "all_": total_tariffs,
                "results": tariffs_count,
                "TariffProfile": tariff_profiles,
            }
        )


TOTAL_PRICING_READING_TYPES = len(PricingReadingType)  # The total number of PricingReadingType enums


class PricingReadingTypeMapper:
    @staticmethod
    def pricing_reading_type_href(scope: BaseRequestScope, rt: PricingReadingType) -> str:
        return generate_href(uri.PricingReadingTypeUri, scope, reading_type=rt)

    @staticmethod
    def extract_price(rt: PricingReadingType, rate: TariffGeneratedRate) -> Decimal:
        if rt == PricingReadingType.IMPORT_ACTIVE_POWER_KWH:
            return rate.import_active_price
        elif rt == PricingReadingType.EXPORT_ACTIVE_POWER_KWH:
            return rate.export_active_price
        elif rt == PricingReadingType.IMPORT_REACTIVE_POWER_KVARH:
            return rate.import_reactive_price
        elif rt == PricingReadingType.EXPORT_REACTIVE_POWER_KVARH:
            return rate.export_reactive_price
        else:
            raise InvalidMappingError(f"Unknown reading type {rt}")

    @staticmethod
    def create_reading_type(scope: BaseRequestScope, rt: PricingReadingType) -> ReadingType:
        """Creates a named reading type based on a fixed enum describing the readings associated
        with a particular type of pricing"""
        href = PricingReadingTypeMapper.pricing_reading_type_href(scope, rt)
        if rt == PricingReadingType.IMPORT_ACTIVE_POWER_KWH:
            return ReadingType.model_validate(
                {
                    "href": href,
                    "commodity": CommodityType.ELECTRICITY_PRIMARY_METERED_VALUE,
                    "flowDirection": FlowDirectionType.FORWARD,
                    "powerOfTenMultiplier": 3,  # kilowatt hours
                    "uom": UomType.REAL_ENERGY_WATT_HOURS,
                }
            )
        elif rt == PricingReadingType.EXPORT_ACTIVE_POWER_KWH:
            return ReadingType.model_validate(
                {
                    "href": href,
                    "commodity": CommodityType.ELECTRICITY_PRIMARY_METERED_VALUE,
                    "flowDirection": FlowDirectionType.REVERSE,
                    "powerOfTenMultiplier": 3,  # kilowatt hours
                    "uom": UomType.REAL_ENERGY_WATT_HOURS,
                }
            )
        elif rt == PricingReadingType.IMPORT_REACTIVE_POWER_KVARH:
            return ReadingType.model_validate(
                {
                    "href": href,
                    "commodity": CommodityType.ELECTRICITY_SECONDARY_METERED_VALUE,
                    "flowDirection": FlowDirectionType.FORWARD,
                    "powerOfTenMultiplier": 3,  # kvarh hours
                    "uom": UomType.REACTIVE_ENERGY_VARH,
                }
            )
        elif rt == PricingReadingType.EXPORT_REACTIVE_POWER_KVARH:
            return ReadingType.model_validate(
                {
                    "href": href,
                    "commodity": CommodityType.ELECTRICITY_SECONDARY_METERED_VALUE,
                    "flowDirection": FlowDirectionType.REVERSE,
                    "powerOfTenMultiplier": 3,  # kvarh hours
                    "uom": UomType.REACTIVE_ENERGY_VARH,
                }
            )
        else:
            raise InvalidMappingError(f"Unknown reading type {rt}")


class RateComponentMapper:
    @staticmethod
    def map_to_response(
        scope: SiteRequestScope,
        tariff_id: int,
        pricing_reading: PricingReadingType,
        day: date,
    ) -> RateComponentResponse:
        """Maps/Creates a single rate component response describing a single type of reading"""
        rate_component_id = day.isoformat()
        # Timezone doesn't really matter here - It just needs to be consistent
        start_time = datetime.combine(day, time(), tzinfo=timezone.utc)
        rc_href = generate_href(
            uri.RateComponentUri,
            scope,
            tariff_id=tariff_id,
            site_id=scope.site_id,
            rate_component_id=rate_component_id,
            pricing_reading=pricing_reading,
        )
        return RateComponentResponse.model_validate(
            {
                "href": rc_href,
                "mRID": MridMapper.encode_rate_component_mrid(
                    scope, tariff_id, scope.site_id, start_time, pricing_reading
                ),
                "description": pricing_reading.name,
                "roleFlags": to_hex_binary(RoleFlagsType.NONE),
                "ReadingTypeLink": Link(
                    href=PricingReadingTypeMapper.pricing_reading_type_href(scope, pricing_reading)
                ),
                "TimeTariffIntervalListLink": ListLink(href=rc_href + "/tti"),
            }
        )

    @staticmethod
    def map_to_list_response(
        scope: SiteRequestScope,
        unique_rate_days: list[date],
        total_unique_rate_days: int,
        skip_start: int,
        skip_end: int,
        tariff_id: int,
    ) -> RateComponentListResponse:
        """Maps/creates a set of rate components under a RateComponentListResponse for a set of rate totals
        organised by date"""
        rc_list = []
        iterator = islice(
            product(unique_rate_days, PricingReadingType),  # Iterator
            skip_start,  # Start index
            (len(unique_rate_days) * TOTAL_PRICING_READING_TYPES) - skip_end,  # End
        )
        for day, pricing_type in iterator:
            rc_list.append(RateComponentMapper.map_to_response(scope, tariff_id, pricing_type, day))

        return RateComponentListResponse.model_validate(
            {
                "all_": total_unique_rate_days * TOTAL_PRICING_READING_TYPES,
                "results": len(rc_list),
                "subscribable": SubscribableType.resource_supports_non_conditional_subscriptions,
                "RateComponent": rc_list,
            }
        )


class ConsumptionTariffIntervalMapper:
    """This is a fully 'Virtual' entity that doesn't exist in the DB. Instead we create them based on a fixed price"""

    @staticmethod
    def database_price_to_sep2(price: Decimal) -> int:
        """Converts a database price ($1.2345) to a sep2 price integer by multiplying it by the price power of 10
        according to the value of PRICE_DECIMAL_PLACES"""
        return int(price * PRICE_DECIMAL_POWER)

    @staticmethod
    def instance_href(
        scope: DeviceOrAggregatorRequestScope,
        tariff_id: int,
        pricing_reading: PricingReadingType,
        day: date,
        time_of_day: time,
        price: Decimal,
    ) -> str:
        """Returns the href for a single instance of a ConsumptionTariffIntervalResponse at a set price

        This endpoint is designed to operate independent of a particular scope to allow encoding of multiple
        different sites. It's the responsibility of the caller to validate the scope before calling this."""
        base = ConsumptionTariffIntervalMapper.list_href(
            scope, tariff_id, scope.display_site_id, pricing_reading, day, time_of_day, price
        )
        return f"{base}/1"

    @staticmethod
    def list_href(
        scope: BaseRequestScope,
        tariff_id: int,
        tariff_site_id: int,
        pricing_reading: PricingReadingType,
        day: date,
        time_of_day: time,
        price: Decimal,
    ) -> str:
        """Returns the href for a list that will hold a single instance of a ConsumptionTariffIntervalResponse at a
        set price

        This endpoint is designed to operate independent of a particular scope to allow encoding of multiple
        different sites. It's the responsibility of the caller to validate the scope before calling this."""
        rate_component_id = day.isoformat()
        tti_id = time_of_day.isoformat("minutes")
        sep2_price = ConsumptionTariffIntervalMapper.database_price_to_sep2(price)
        return generate_href(
            uri.ConsumptionTariffIntervalListUri,
            scope,
            tariff_id=tariff_id,
            site_id=tariff_site_id,
            rate_component_id=rate_component_id,
            pricing_reading=pricing_reading,
            tti_id=tti_id,
            sep2_price=sep2_price,
        )

    @staticmethod
    def map_to_response(
        scope: SiteRequestScope,
        tariff_id: int,
        pricing_rt: PricingReadingType,
        day: date,
        time_of_day: time,
        price: Decimal,
    ) -> ConsumptionTariffIntervalResponse:
        """Returns a ConsumptionTariffIntervalResponse with price being set to an integer by adjusting to
        PRICE_DECIMAL_PLACES"""
        href = ConsumptionTariffIntervalMapper.instance_href(scope, tariff_id, pricing_rt, day, time_of_day, price)
        return ConsumptionTariffIntervalResponse.model_validate(
            {
                "href": href,
                "consumptionBlock": ConsumptionBlockType.NOT_APPLICABLE,
                "price": ConsumptionTariffIntervalMapper.database_price_to_sep2(price),
                "startValue": 0,
            }
        )

    @staticmethod
    def map_to_list_response(
        scope: SiteRequestScope,
        tariff_id: int,
        pricing_rt: PricingReadingType,
        day: date,
        time_of_day: time,
        price: Decimal,
    ) -> ConsumptionTariffIntervalListResponse:
        """Returns a ConsumptionTariffIntervalListResponse with price being set to an integer by adjusting to
        PRICE_DECIMAL_PLACES"""
        href = ConsumptionTariffIntervalMapper.list_href(
            scope, tariff_id, scope.site_id, pricing_rt, day, time_of_day, price
        )
        cti = ConsumptionTariffIntervalMapper.map_to_response(scope, tariff_id, pricing_rt, day, time_of_day, price)
        return ConsumptionTariffIntervalListResponse.model_validate(
            {"href": href, "all_": 1, "results": 1, "ConsumptionTariffInterval": [cti]}
        )


class TimeTariffIntervalMapper:
    @staticmethod
    def instance_href(
        scope: BaseRequestScope,
        tariff_id: int,
        tariff_site_id: int,
        day: date,
        pricing_reading: PricingReadingType,
        time_of_day: time,
    ) -> str:
        """Creates a href that identifies a single TimeTariffIntervalResponse with the specified values.

        This endpoint is designed to operate independent of a particular scope to allow encoding of multiple
        different sites. It's the responsibility of the caller to validate the scope before calling this."""
        rate_component_id = day.isoformat()
        tti_id = time_of_day.isoformat("minutes")
        return generate_href(
            uri.TimeTariffIntervalUri,
            scope,
            tariff_id=tariff_id,
            site_id=tariff_site_id,
            rate_component_id=rate_component_id,
            pricing_reading=pricing_reading,
            tti_id=tti_id,
        )

    @staticmethod
    def map_to_response(
        scope: BaseRequestScope, rate: TariffGeneratedRate, pricing_reading: PricingReadingType
    ) -> TimeTariffIntervalResponse:
        """Creates a new TimeTariffIntervalResponse for the given rate and specific price reading"""
        start_d = rate.start_time.date()
        start_t = rate.start_time.time()
        price = PricingReadingTypeMapper.extract_price(pricing_reading, rate)
        href = TimeTariffIntervalMapper.instance_href(
            scope, rate.tariff_id, rate.site_id, start_d, pricing_reading, start_t
        )
        list_href = ConsumptionTariffIntervalMapper.list_href(
            scope, rate.tariff_id, rate.site_id, pricing_reading, start_d, start_t, price
        )

        return TimeTariffIntervalResponse.model_validate(
            {
                "href": href,
                "mRID": MridMapper.encode_time_tariff_interval_mrid(
                    scope,
                    rate.tariff_generated_rate_id,
                    pricing_reading,
                ),
                "version": 0,
                "description": rate.start_time.isoformat(),
                "touTier": TOUType.NOT_APPLICABLE,
                "creationTime": int(rate.changed_time.timestamp()),
                "replyTo": ResponseListMapper.response_list_href(
                    scope, rate.site_id, ResponseSetType.TARIFF_GENERATED_RATES
                ),  # Response function set
                "responseRequired": SPECIFIC_RESPONSE_REQUIRED,  # Response function set
                "interval": {
                    "start": int(rate.start_time.timestamp()),
                    "duration": rate.duration_seconds,
                },
                "EventStatus_": EventStatus.model_validate(
                    {
                        "currentStatus": 0,  # Set to 'scheduled'
                        "dateTime": int(rate.changed_time.timestamp()),  # Set to when it is created
                        "potentiallySuperseded": False,
                    }
                ),
                "ConsumptionTariffIntervalListLink": ListLink(href=list_href, all_=1),  # single rate
            }
        )

    @staticmethod
    def map_to_list_response(
        scope: DeviceOrAggregatorRequestScope,
        rates: Sequence[TariffGeneratedRate],
        pricing_reading: PricingReadingType,
        total: int,
    ) -> TimeTariffIntervalListResponse:
        """Creates a TimeTariffIntervalListResponse for a single set of rates."""
        return TimeTariffIntervalListResponse.model_validate(
            {
                "all_": total,
                "results": len(rates),
                "TimeTariffInterval": [
                    TimeTariffIntervalMapper.map_to_response(scope, rate, pricing_reading) for rate in rates
                ],
            }
        )
