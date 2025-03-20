from typing import Sequence, Union

import envoy_schema.server.schema.uri as uri
from envoy_schema.server.schema.sep2.identification import ListLink
from envoy_schema.server.schema.sep2.response import (
    DERControlResponse,
    PriceResponse,
    Response,
    ResponseListResponse,
    ResponseSet,
    ResponseSetList,
)

from envoy.server.mapper.common import generate_href
from envoy.server.mapper.constants import PricingReadingType, ResponseSetType
from envoy.server.mapper.sep2.mrid import MridMapper
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.response import DynamicOperatingEnvelopeResponse, TariffGeneratedRateResponse
from envoy.server.model.tariff import TariffGeneratedRate
from envoy.server.request_scope import BaseRequestScope, DeviceOrAggregatorRequestScope

# From sep2 Table 27 - This will indicate that response to each SPECIFIC event is requested
SPECIFIC_RESPONSE_REQUIRED = "03"


def response_set_type_to_href(t: ResponseSetType) -> str:
    """Converts a ResponseSetType to a href id/slug that will uniquely identify the type as a short identifier"""
    if t == ResponseSetType.TARIFF_GENERATED_RATES:
        return "price"
    elif t == ResponseSetType.DYNAMIC_OPERATING_ENVELOPES:
        return "doe"
    else:
        raise ValueError(f"Unsupported ResponseSetType {t} ({int(t)})")


def href_to_response_set_type(href_part: str) -> ResponseSetType:
    """Converts the output of response_set_type_to_href back to the original ResponseSetType"""
    if href_part == "price":
        return ResponseSetType.TARIFF_GENERATED_RATES
    elif href_part == "doe":
        return ResponseSetType.DYNAMIC_OPERATING_ENVELOPES
    else:
        raise ValueError(f"Unrecognised response set '{href_part}'")


class ResponseMapper:

    @staticmethod
    def price_response_href(scope: BaseRequestScope, rate_response: TariffGeneratedRateResponse) -> str:
        """Generates the href for the specified TariffGeneratedRateResponse. Requires the primary key to be set"""
        return generate_href(
            uri.ResponseUri,
            scope,
            site_id=rate_response.site_id,
            response_id=rate_response.tariff_generated_rate_response_id,
            response_list_id=response_set_type_to_href(ResponseSetType.TARIFF_GENERATED_RATES),
        )

    @staticmethod
    def doe_response_href(scope: BaseRequestScope, doe_response: DynamicOperatingEnvelopeResponse) -> str:
        """Generates the href for the specified DynamicOperatingEnvelopeResponse. Requires the primary key to be set"""
        return generate_href(
            uri.ResponseUri,
            scope,
            site_id=doe_response.site_id,
            response_id=doe_response.dynamic_operating_envelope_response_id,
            response_list_id=response_set_type_to_href(ResponseSetType.DYNAMIC_OPERATING_ENVELOPES),
        )

    @staticmethod
    def map_to_price_response(scope: BaseRequestScope, rate_response: TariffGeneratedRateResponse) -> PriceResponse:
        """Generates a sep2 PriceResponse for a given TariffGeneratedRateResponse.

        rate_response: Will need the site relationship populated"""
        return PriceResponse(
            href=ResponseMapper.price_response_href(scope, rate_response),
            createdDateTime=int(rate_response.created_time.timestamp()),
            endDeviceLFDI=rate_response.site.lfdi,
            status=rate_response.response_type,
            subject=MridMapper.encode_time_tariff_interval_mrid(
                scope, rate_response.tariff_generated_rate_id, rate_response.pricing_reading_type
            ),
        )

    @staticmethod
    def map_from_price_request(
        r: Union[PriceResponse, Response],
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
        return DERControlResponse(
            href=ResponseMapper.doe_response_href(scope, doe_response),
            createdDateTime=int(doe_response.created_time.timestamp()),
            endDeviceLFDI=doe_response.site.lfdi,
            status=doe_response.response_type,
            subject=MridMapper.encode_doe_mrid(scope, doe_response.dynamic_operating_envelope_id),
        )

    @staticmethod
    def map_from_doe_request(
        r: Union[DERControlResponse, Response], dynamic_operating_envelope: DynamicOperatingEnvelope
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
    def response_list_href(scope: BaseRequestScope, display_site_id: int, response_set_type: ResponseSetType) -> str:
        """Returns a href for a ResponseList resource of the specified type (for the specified scope)"""
        return generate_href(
            uri.ResponseListUri,
            scope,
            site_id=display_site_id,
            response_list_id=response_set_type_to_href(response_set_type),
        )

    @staticmethod
    def map_to_price_response(
        scope: DeviceOrAggregatorRequestScope,
        responses: Sequence[TariffGeneratedRateResponse],
        total_responses: int,
    ) -> ResponseListResponse:
        """Generates a list response for a price response list"""
        return ResponseListResponse(
            href=ResponseListMapper.response_list_href(
                scope, scope.display_site_id, ResponseSetType.TARIFF_GENERATED_RATES
            ),
            all_=total_responses,
            results=len(responses),
            Response_=[ResponseMapper.map_to_price_response(scope, r) for r in responses],
        )

    @staticmethod
    def map_to_doe_response(
        scope: DeviceOrAggregatorRequestScope,
        responses: Sequence[DynamicOperatingEnvelopeResponse],
        total_responses: int,
    ) -> ResponseListResponse:
        """Generates a list response for a doe response list"""
        return ResponseListResponse(
            href=ResponseListMapper.response_list_href(
                scope, scope.display_site_id, ResponseSetType.DYNAMIC_OPERATING_ENVELOPES
            ),
            all_=total_responses,
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
    def map_to_list_response(
        scope: DeviceOrAggregatorRequestScope, response_sets: list[ResponseSet], total_response_sets: int
    ) -> ResponseSetList:
        """Constructs a list response from a list of existing sets"""
        href = generate_href(
            uri.ResponseSetListUri,
            scope,
            site_id=scope.display_site_id,
        )
        return ResponseSetList(
            href=href, all_=total_response_sets, results=len(response_sets), ResponseSet_=response_sets
        )
