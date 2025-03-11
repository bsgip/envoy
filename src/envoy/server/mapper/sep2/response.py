from datetime import datetime
from typing import Optional, Sequence

import envoy_schema.server.schema.uri as uri
from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointLink
from envoy_schema.server.schema.sep2.identification import Link, ListLink
from envoy_schema.server.schema.sep2.response import (
    DERControlResponse,
    PriceResponse,
    ResponseListResponse,
    ResponseType,
)
from envoy_schema.server.schema.sep2.types import SubscribableType

from envoy.server.crud.common import sum_digits
from envoy.server.mapper.common import generate_href, parse_device_category
from envoy.server.mapper.sep2.mrid import MridMapper, PricingReadingType
from envoy.server.model.response import TariffGeneratedRateResponse
from envoy.server.model.site import Site
from envoy.server.model.tariff import TariffGeneratedRate
from envoy.server.request_scope import BaseRequestScope, DeviceOrAggregatorRequestScope

RESPONSE_LIST_TARIFF_GENERATED_RATES = "price"
RESPONSE_LIST_DYNAMIC_OPERATING_ENVELOPES = "doe"


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
            response_list_id=RESPONSE_LIST_TARIFF_GENERATED_RATES,
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

        return TariffGeneratedRateResponse(
            tariff_generated_rate_id=tariff_generated_rate.tariff_generated_rate_id,
            site_id=tariff_generated_rate.site_id,
            response_type=r.status,
            pricing_reading_type=pricing_reading_type,
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
            response_list_id=RESPONSE_LIST_TARIFF_GENERATED_RATES,
        )

        return ResponseListResponse(
            href=href,
            all_=response_count,
            results=len(responses),
            Response_=[ResponseMapper.map_to_price_response(scope, r) for r in responses],
        )
