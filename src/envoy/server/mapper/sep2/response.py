from datetime import datetime
from typing import Optional, Sequence

import envoy_schema.server.schema.uri as uri
from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointLink
from envoy_schema.server.schema.sep2.identification import Link, ListLink
from envoy_schema.server.schema.sep2.response import (
    DERControlResponse,
    PriceResponse,
    ResponseListResponse,
    ResponseSet,
    ResponseType,
)
from envoy_schema.server.schema.sep2.types import SubscribableType

from envoy.server.crud.common import sum_digits
from envoy.server.mapper.common import generate_href, parse_device_category
from envoy.server.mapper.sep2.mrid import MridMapper, PricingReadingType, ResponseSetType
from envoy.server.model.response import DynamicOperatingEnvelopeResponse, TariffGeneratedRateResponse
from envoy.server.model.site import Site
from envoy.server.model.tariff import TariffGeneratedRate
from envoy.server.request_scope import BaseRequestScope, DeviceOrAggregatorRequestScope


def response_set_type_to_href(t: ResponseSetType) -> str:
    """Converts a ResponseSetType to a href id/slug that will uniquely identify the type as a short identifier"""
    if t == ResponseSetType.TARIFF_GENERATED_RATES:
        return "price"
    elif t == ResponseSetType.DYNAMIC_OPERATING_ENVELOPES:
        return "doe"
    else:
        raise ValueError(f"Unsupported ResponseSetType {t} ({int(t)})")


class ResponseMapper:
    @staticmethod
    def map_to_price_response(scope: BaseRequestScope, rate_response: TariffGeneratedRateResponse) -> PriceResponse:
        """Generates a sep2 PriceResponse for a given TariffGeneratedRateResponse.

        rate_response: Will need the site relationship populated"""
        href = generate_href(
            uri.ResponseUri,
            scope,
            site_id=rate_response.site_id,
            response_id=rate_response.tariff_generated_rate_response_id,
            response_list_id=response_set_type_to_href(ResponseSetType.TARIFF_GENERATED_RATES),
        )

        return PriceResponse(
            href=href,
            createdDateTime=int(rate_response.created_time.timestamp()),
            endDeviceLFDI=rate_response.site.lfdi,
            status=rate_response.response_type,
            subject=MridMapper.encode_time_tariff_interval_mrid(
                scope, rate_response.tariff_generated_rate_id, rate_response.pricing_reading_type
            ),
        )

    @staticmethod
    def map_from_price_request(
        r: PriceResponse,
        tariff_generated_rate: TariffGeneratedRate,
        pricing_reading_type: PricingReadingType,
    ) -> TariffGeneratedRateResponse:
        """Maps a sep2 PriceResponse to an internal TariffGeneratedRateResponse model that references a specific
        PricingReadingType within a TariffGeneratedRate"""

        # createdTime will be managed by the DB itself
        return TariffGeneratedRateResponse(
            tariff_generated_rate_id=tariff_generated_rate.tariff_generated_rate_id,
            site_id=tariff_generated_rate.site_id,
            response_type=r.status,
            pricing_reading_type=pricing_reading_type,
        )

    @staticmethod
    def map_to_doe_response(
        scope: BaseRequestScope, doe_response: DynamicOperatingEnvelopeResponse
    ) -> DERControlResponse:
        """Generates a sep2 DERControlResponse for a given DynamicOperatingEnvelopeResponse.

        doe_response: Will need the site relationship populated"""
        href = generate_href(
            uri.ResponseUri,
            scope,
            site_id=doe_response.site_id,
            response_id=doe_response.dynamic_operating_envelope_response_id,
            response_list_id=response_set_type_to_href(ResponseSetType.DYNAMIC_OPERATING_ENVELOPES),
        )

        return DERControlResponse(
            href=href,
            createdDateTime=int(doe_response.created_time.timestamp()),
            endDeviceLFDI=doe_response.site.lfdi,
            status=doe_response.response_type,
            subject=MridMapper.encode_doe_mrid(scope, doe_response.dynamic_operating_envelope_id),
        )

    @staticmethod
    def map_from_doe_request(
        r: DERControlResponse, dynamic_operating_envelope: DynamicOperatingEnvelopeResponse
    ) -> DynamicOperatingEnvelopeResponse:
        """Maps a sep2 DERControlResponse to an internal DynamicOperatingEnvelopeResponse model."""

        # createdTime will be managed by the DB itself
        return DynamicOperatingEnvelopeResponse(
            dynamic_operating_envelope_id=dynamic_operating_envelope.dynamic_operating_envelope_id,
            site_id=dynamic_operating_envelope.site_id,
            response_type=r.status,
        )


class ResponseListMapper:

    @staticmethod
    def map_to_price_response(
        scope: DeviceOrAggregatorRequestScope,
        responses: Sequence[TariffGeneratedRateResponse],
        response_count: int,
    ) -> ResponseListResponse:
        """Generates a list response for a price response list"""
        href = generate_href(
            uri.ResponseListUri,
            scope,
            site_id=scope.display_site_id,
            response_list_id=response_set_type_to_href(ResponseSetType.TARIFF_GENERATED_RATES),
        )

        return ResponseListResponse(
            href=href,
            all_=response_count,
            results=len(responses),
            Response_=[ResponseMapper.map_to_price_response(scope, r) for r in responses],
        )

    @staticmethod
    def map_to_doe_response(
        scope: DeviceOrAggregatorRequestScope,
        responses: Sequence[DynamicOperatingEnvelopeResponse],
        response_count: int,
    ) -> ResponseListResponse:
        """Generates a list response for a doe response list"""
        href = generate_href(
            uri.ResponseListUri,
            scope,
            site_id=scope.display_site_id,
            response_list_id=response_set_type_to_href(ResponseSetType.DYNAMIC_OPERATING_ENVELOPES),
        )

        return ResponseListResponse(
            href=href,
            all_=response_count,
            results=len(responses),
            Response_=[ResponseMapper.map_to_doe_response(scope, r) for r in responses],
        )


class ResponseSetMapper:
    @staticmethod
    def map_to_set_response(scope: DeviceOrAggregatorRequestScope, response_set_type: ResponseSetType) -> ResponseSet:
        """Encodes a specific ResponseSet for a fixed ResponseSetType"""
        set_href = generate_href(
            uri.ResponseSetUri,
            scope,
            site_id=scope.display_site_id,
            response_list_id=response_set_type_to_href(response_set_type),
        )

        list_href = generate_href(
            uri.ResponseListUri,
            scope,
            site_id=scope.display_site_id,
            response_list_id=response_set_type_to_href(response_set_type),
        )

        return ResponseSet(
            href=set_href,
            ResponseListLink=ListLink(href=list_href),
            mRID=MridMapper.encode_response_set_mrid(scope, response_set_type),
        )

    @staticmethod
    def map_to_list_response(scope: DeviceOrAggregatorRequestScope, skip: int, limit: int) -> ResponseSet: