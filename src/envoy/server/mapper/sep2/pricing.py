from datetime import datetime
from typing import Iterator, Optional, Sequence, Union

from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.event import EventStatus, EventStatusType
from envoy_schema.server.schema.sep2.identification import Link, ListLink
from envoy_schema.server.schema.sep2.metering import ReadingType
from envoy_schema.server.schema.sep2.pricing import (
    ConsumptionTariffIntervalListResponse,
    ConsumptionTariffIntervalListSummaryResponse,
    ConsumptionTariffIntervalResponse,
    RateComponentListResponse,
    RateComponentResponse,
    TariffProfileListResponse,
    TariffProfileResponse,
    TimeTariffIntervalListResponse,
    TimeTariffIntervalResponse,
)
from envoy_schema.server.schema.sep2.types import (
    ConsumptionBlockType,
    DateTimeIntervalType,
    ServiceKind,
    SubscribableType,
    TOUType,
)

from envoy.server.exception import NotFoundError
from envoy.server.mapper.common import generate_href
from envoy.server.mapper.constants import ResponseSetType
from envoy.server.mapper.sep2.der import to_hex_binary
from envoy.server.mapper.sep2.mrid import MridMapper
from envoy.server.mapper.sep2.response import SPECIFIC_RESPONSE_REQUIRED, ResponseListMapper
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
from envoy.server.model.tariff import Tariff, TariffComponent, TariffGeneratedRate
from envoy.server.request_scope import AggregatorRequestScope, DeviceOrAggregatorRequestScope, SiteRequestScope


class TariffProfileMapper:
    @staticmethod
    def map_to_response(
        scope: Union[DeviceOrAggregatorRequestScope, AggregatorRequestScope],
        tariff: Tariff,
        total_components: int,
        total_active_rates: int,
    ) -> TariffProfileResponse:
        """Returns a mapped sep2 entity TariffProfileResponse.

        total_components: The total number of RateComponent (TariffComponent) instances that sit under this tariff
        total_active_rates: Total of active TimeTariffInterval (TariffGeneratedRate) instances under this tariff"""
        tp_href = generate_href(uri.TariffProfileUri, scope, tariff_id=tariff.tariff_id, site_id=scope.display_site_id)
        rc_href = generate_href(
            uri.RateComponentListUri, scope, tariff_id=tariff.tariff_id, site_id=scope.display_site_id
        )
        ctti_href = generate_href(
            uri.CombinedTimeTariffIntervalListUri, scope, tariff_id=tariff.tariff_id, site_id=scope.display_site_id
        )
        return TariffProfileResponse(
            href=tp_href,
            mRID=MridMapper.encode_tariff_profile_mrid(scope, tariff.tariff_id),
            version=tariff.version,
            description=tariff.name,
            currency=tariff.currency_code,
            pricePowerOfTenMultiplier=tariff.price_power_of_ten_multiplier,
            rateCode=tariff.dnsp_code,
            primacyType=tariff.primacy,  # We don't want to block primacies outside zero and one
            serviceCategoryKind=ServiceKind.ELECTRICITY,
            RateComponentListLink=ListLink(href=rc_href, all_=total_components),
            CombinedTimeTariffIntervalListLink=ListLink(href=ctti_href, all_=total_active_rates),
        )

    @staticmethod
    def map_to_list_response(
        scope: DeviceOrAggregatorRequestScope,
        tariffs: Iterator[tuple[Tariff, int, int]],
        total_tariffs: int,
        fsa_id: Optional[int],
    ) -> TariffProfileListResponse:
        """Returns a list containing multiple sep2 entities. The href's will be to the site specific
        TimeTariffProfile and RateComponentListLink

        tariffs should be a list of tuples combining the individual tariffs with the underlying count
        of rate components and active tariff rates

        This endpoint is designed to operate independent of a particular scope to allow encoding of multiple
        different sites. It's the responsibility of the caller to validate the scope before calling this.

        tariffs: Tuple in the form (tariff, rate_component_count, time_tariff_interval_count)"""
        tariff_profiles: list[TariffProfileResponse] = []
        tariffs_count: int = 0
        for tariff, rc_count, active_rates in tariffs:
            tariff_profiles.append(TariffProfileMapper.map_to_response(scope, tariff, rc_count, active_rates))
            tariffs_count = tariffs_count + 1

        if fsa_id is None:
            href = generate_href(uri.TariffProfileListUri, scope, site_id=scope.display_site_id)
        else:
            href = generate_href(
                uri.TariffProfileFSAListUri,
                scope,
                site_id=scope.display_site_id,
                fsa_id=fsa_id,
            )

        return TariffProfileListResponse(
            href=href,
            all_=total_tariffs,
            results=tariffs_count,
            TariffProfile=tariff_profiles,
            subscribable=SubscribableType.resource_supports_non_conditional_subscriptions,
        )


class RateComponentMapper:
    @staticmethod
    def create_reading_type(scope: DeviceOrAggregatorRequestScope, tc: TariffComponent) -> ReadingType:
        """Creates a named reading type that represents the uom associated with TariffComponent"""
        href = generate_href(
            uri.PricingReadingTypeUri,
            scope,
            site_id=scope.display_site_id,
            tariff_id=tc.tariff_id,
            rate_component_id=tc.tariff_component_id,
        )
        return ReadingType(
            href=href,
            accumulationBehaviour=tc.accumulation_behaviour,
            commodity=tc.commodity,
            dataQualifier=tc.data_qualifier,
            flowDirection=tc.flow_direction,
            kind=tc.kind,
            phase=tc.phase,
            powerOfTenMultiplier=tc.power_of_ten_multiplier,
            uom=tc.uom,
        )

    @staticmethod
    def map_to_response(
        scope: Union[DeviceOrAggregatorRequestScope, AggregatorRequestScope], tc: TariffComponent, total_rates: int
    ) -> RateComponentResponse:
        """Maps/Creates a single rate component response describing a commodity being priced"""

        rate_component_href = generate_href(
            uri.RateComponentUri,
            scope,
            site_id=scope.display_site_id,
            tariff_id=tc.tariff_id,
            rate_component_id=tc.tariff_component_id,
        )
        reading_type_link = generate_href(
            uri.PricingReadingTypeUri,
            scope,
            site_id=scope.display_site_id,
            tariff_id=tc.tariff_id,
            rate_component_id=tc.tariff_component_id,
        )
        tti_link = generate_href(
            uri.TimeTariffIntervalListUri,
            scope,
            site_id=scope.display_site_id,
            tariff_id=tc.tariff_id,
            rate_component_id=tc.tariff_component_id,
        )

        role_flags = to_hex_binary(tc.role_flags)
        if role_flags is None:
            role_flags = "00"

        return RateComponentResponse(
            href=rate_component_href,
            mRID=MridMapper.encode_rate_component_mrid(scope, tc.tariff_component_id, scope.display_site_id),
            description=tc.description,
            roleFlags=role_flags,
            ReadingTypeLink=Link(href=reading_type_link),
            TimeTariffIntervalListLink=ListLink(href=tti_link, all_=total_rates),
        )

    @staticmethod
    def map_to_list_response(
        scope: SiteRequestScope,
        tariff_id: int,
        tariff_components_with_count: list[tuple[TariffComponent, int]],
        total_tariff_components: int,
    ) -> RateComponentListResponse:
        """Maps/creates a set of rate components under a RateComponentListResponse for a set of TariffComponents with
        their associated count of child TariffGeneratedRate"""

        list_href = generate_href(
            uri.RateComponentListUri,
            scope,
            site_id=scope.display_site_id,
            tariff_id=tariff_id,
        )

        return RateComponentListResponse(
            href=list_href,
            all_=total_tariff_components,
            results=len(tariff_components_with_count),
            subscribable=SubscribableType.resource_supports_non_conditional_subscriptions,
            RateComponent=[
                RateComponentMapper.map_to_response(scope, tc, rate_count)
                for tc, rate_count in tariff_components_with_count
            ],
        )


class ConsumptionTariffIntervalMapper:
    """This is a fully 'Virtual' entity that doesn't exist in the DB. Instead we create them based on a
    TariffGeneratedRate (i.e. each TariffGeneratedRate is just a single price)"""

    @staticmethod
    def extract_block_start_price(
        rate: TariffGeneratedRate | ArchiveTariffGeneratedRate, cti_id: int
    ) -> tuple[int, int]:
        """Extracts the (start, price) for the specified cti_id (block_id). The first block is cti_id=1. Raises a
        NotFoundError if the rate does NOT have a price/start value at that block."""

        match (cti_id):
            case 1:
                return (0, rate.price_pow10_encoded)
            case 2:
                if rate.block_1_start_pow10_encoded is None or rate.price_pow10_encoded_block_1 is None:
                    raise NotFoundError(f"There is no {cti_id} block for the specified TimeTariffInterval")
                return (rate.block_1_start_pow10_encoded, rate.price_pow10_encoded_block_1)
            case _:
                raise NotFoundError(f"There is no {cti_id} block for the specified TimeTariffInterval")

    @staticmethod
    def map_to_response(
        scope: Union[DeviceOrAggregatorRequestScope, AggregatorRequestScope],
        rate: TariffGeneratedRate | ArchiveTariffGeneratedRate,
        cti_id: int,
    ) -> ConsumptionTariffIntervalResponse:
        """Returns a ConsumptionTariffIntervalResponse with the nominated ID"""
        href = generate_href(
            uri.ConsumptionTariffIntervalUri,
            scope,
            site_id=scope.display_site_id,
            tariff_id=rate.tariff_id,
            rate_component_id=rate.tariff_component_id,
            tti_id=rate.tariff_generated_rate_id,
            cti_id=cti_id,
        )

        # We have multiple block prices in a single rate - this will select the correct value
        start, price = ConsumptionTariffIntervalMapper.extract_block_start_price(rate, cti_id)

        return ConsumptionTariffIntervalResponse(
            href=href,
            consumptionBlock=ConsumptionBlockType(cti_id),
            price=price,
            startValue=start,
        )

    @staticmethod
    def map_to_list_response(
        scope: DeviceOrAggregatorRequestScope, rate: TariffGeneratedRate | ArchiveTariffGeneratedRate
    ) -> ConsumptionTariffIntervalListResponse:
        """Returns a singleton list containing the one ConsumptionTariffIntervalResponse representing rate"""
        href = generate_href(
            uri.ConsumptionTariffIntervalListUri,
            scope,
            site_id=scope.display_site_id,
            tariff_id=rate.tariff_id,
            rate_component_id=rate.tariff_component_id,
            tti_id=rate.tariff_generated_rate_id,
        )

        # We will either have 1 or 2 price blocks depending on whether the rate has the fields set
        if rate.block_1_start_pow10_encoded is not None and rate.price_pow10_encoded_block_1 is not None:
            cti_block_0 = ConsumptionTariffIntervalMapper.map_to_response(scope, rate, 1)
            cti_block_1 = ConsumptionTariffIntervalMapper.map_to_response(scope, rate, 2)
            return ConsumptionTariffIntervalListResponse(
                href=href, all_=2, results=2, ConsumptionTariffInterval=[cti_block_0, cti_block_1]
            )
        else:
            cti_block_0 = ConsumptionTariffIntervalMapper.map_to_response(scope, rate, 1)
            return ConsumptionTariffIntervalListResponse(
                href=href, all_=1, results=1, ConsumptionTariffInterval=[cti_block_0]
            )

    @staticmethod
    def map_to_summary_list_response(
        scope: Union[DeviceOrAggregatorRequestScope, AggregatorRequestScope],
        rate: TariffGeneratedRate | ArchiveTariffGeneratedRate,
    ) -> ConsumptionTariffIntervalListSummaryResponse:
        """Returns a list containing the ConsumptionTariffIntervalResponse(s) representing rate"""

        if rate.block_1_start_pow10_encoded is not None and rate.price_pow10_encoded_block_1 is not None:
            cti_block_0 = ConsumptionTariffIntervalMapper.map_to_response(scope, rate, 1)
            cti_block_1 = ConsumptionTariffIntervalMapper.map_to_response(scope, rate, 2)
            return ConsumptionTariffIntervalListSummaryResponse(
                all_=2, results=2, ConsumptionTariffInterval=[cti_block_0, cti_block_1]
            )
        else:
            cti_block_0 = ConsumptionTariffIntervalMapper.map_to_response(scope, rate, 1)
            return ConsumptionTariffIntervalListSummaryResponse(
                all_=1, results=1, ConsumptionTariffInterval=[cti_block_0]
            )


class TimeTariffIntervalMapper:

    @staticmethod
    def map_to_response(
        scope: Union[DeviceOrAggregatorRequestScope, AggregatorRequestScope],
        now: datetime,
        rate: TariffGeneratedRate | ArchiveTariffGeneratedRate,
    ) -> TimeTariffIntervalResponse:
        """Creates a new TimeTariffIntervalResponse for the given rate"""
        href = generate_href(
            uri.TimeTariffIntervalUri,
            scope,
            site_id=rate.site_id,
            tariff_id=rate.tariff_id,
            rate_component_id=rate.tariff_component_id,
            tti_id=rate.tariff_generated_rate_id,
        )
        cti_list_href = generate_href(
            uri.ConsumptionTariffIntervalListUri,
            scope,
            site_id=rate.site_id,
            tariff_id=rate.tariff_id,
            rate_component_id=rate.tariff_component_id,
            tti_id=rate.tariff_generated_rate_id,
        )
        rate_component_href = generate_href(
            uri.RateComponentUri,
            scope,
            site_id=rate.site_id,
            tariff_id=rate.tariff_id,
            rate_component_id=rate.tariff_component_id,
        )

        is_active = rate.start_time <= now
        event_status: int
        event_status_time: datetime
        if isinstance(rate, ArchiveTariffGeneratedRate) and rate.deleted_time is not None:
            # This is a deleted rate
            event_status = EventStatusType.Cancelled
            event_status_time = rate.deleted_time
        else:
            # This is either a schedule / active DOE
            event_status = EventStatusType.Active if is_active else EventStatusType.Scheduled
            event_status_time = rate.changed_time

        if rate.block_1_start_pow10_encoded is None or rate.price_pow10_encoded_block_1 is None:
            total_consumption_blocks = 1
        else:
            total_consumption_blocks = 2

        return TimeTariffIntervalResponse(
            href=href,
            mRID=MridMapper.encode_time_tariff_interval_mrid(scope, rate.tariff_generated_rate_id),
            version=0,
            touTier=TOUType.NOT_APPLICABLE,
            creationTime=int(rate.changed_time.timestamp()),
            replyTo=ResponseListMapper.response_list_href(
                scope, rate.site_id, ResponseSetType.TARIFF_GENERATED_RATES
            ),  # Response function set
            responseRequired=SPECIFIC_RESPONSE_REQUIRED,  # Response function set
            interval=DateTimeIntervalType(
                start=int(rate.start_time.timestamp()),
                duration=rate.duration_seconds,
            ),
            EventStatus_=EventStatus(
                currentStatus=event_status,
                dateTime=int(event_status_time.timestamp()),
                potentiallySuperseded=False,
            ),
            ConsumptionTariffIntervalListLink=ListLink(href=cti_list_href, all_=total_consumption_blocks),
            RateComponentLink=Link(href=rate_component_href),  # csip-aus v1.3 extension
            ConsumptionTariffIntervalListSummary=ConsumptionTariffIntervalMapper.map_to_summary_list_response(
                scope, rate
            ),  # csip-aus v1.3 extension
        )

    @staticmethod
    def map_to_list_response(
        scope: DeviceOrAggregatorRequestScope,
        tariff_id: int,
        tariff_component_id: Optional[int],
        now: datetime,
        rates: Sequence[Union[TariffGeneratedRate, ArchiveTariffGeneratedRate]],
        total: int,
    ) -> TimeTariffIntervalListResponse:
        """Creates a TimeTariffIntervalListResponse for a single set of rates."""

        if tariff_component_id is None:
            href = generate_href(
                uri.CombinedTimeTariffIntervalListUri, scope, site_id=scope.display_site_id, tariff_id=tariff_id
            )
        else:
            href = generate_href(
                uri.TimeTariffIntervalListUri,
                scope,
                site_id=scope.display_site_id,
                tariff_id=tariff_id,
                rate_component_id=tariff_component_id,
            )

        return TimeTariffIntervalListResponse(
            href=href,
            subscribable=SubscribableType.resource_supports_non_conditional_subscriptions,
            all_=total,
            results=len(rates),
            TimeTariffInterval=[TimeTariffIntervalMapper.map_to_response(scope, now, rate) for rate in rates],
        )
