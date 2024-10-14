from decimal import Decimal
from enum import IntEnum, auto
from typing import Optional, Sequence, Union

from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.der import (
    ActivePower,
    DefaultDERControl,
    DERControlBase,
    DERControlListResponse,
    DERControlResponse,
    DERProgramListResponse,
    DERProgramResponse,
)
from envoy_schema.server.schema.sep2.event import EventStatus
from envoy_schema.server.schema.sep2.identification import Link, ListLink
from envoy_schema.server.schema.sep2.pricing import PrimacyType
from envoy_schema.server.schema.sep2.types import DateTimeIntervalType, SubscribableType

from envoy.server.exception import InvalidMappingError
from envoy.server.mapper.common import generate_href, generate_mrid
from envoy.server.model.config.default_doe import DefaultDoeConfiguration
from envoy.server.model.doe import DOE_DECIMAL_PLACES, DOE_DECIMAL_POWER, DynamicOperatingEnvelope
from envoy.server.request_scope import AggregatorRequestScope, DeviceOrAggregatorRequestScope

DOE_PROGRAM_MRID_PREFIX: int = int("D0E", 16)
DOE_PROGRAM_ID: str = "doe"
DOE_DEFAULT_CONTROL_ID: int = int("DEF", 16)


class DERControlListSource(IntEnum):
    DER_CONTROL_LIST = auto()
    ACTIVE_DER_CONTROL_LIST = auto()


class DERControlMapper:
    @staticmethod
    def map_to_active_power(p: Decimal) -> ActivePower:
        """Creates an ActivePower instance from our own internal power decimal reading"""
        return ActivePower.model_validate(
            {
                "value": int(p * DOE_DECIMAL_POWER),
                "multiplier": -DOE_DECIMAL_PLACES,  # We negate as we are encoding 1.23 as 123 * 10^-2
            }
        )

    @staticmethod
    def map_to_response(
        scope: Union[DeviceOrAggregatorRequestScope, AggregatorRequestScope], doe: DynamicOperatingEnvelope
    ) -> DERControlResponse:
        """Creates a csip aus compliant DERControlResponse from the specific doe"""
        return DERControlResponse.model_validate(
            {
                "href": generate_href(
                    uri.DERControlAndListByDateUri,
                    scope,
                    site_id=scope.display_site_id,
                    der_program_id=DOE_PROGRAM_ID,
                    derc_id_or_date=doe.dynamic_operating_envelope_id,
                ),
                "mRID": generate_mrid(DOE_PROGRAM_MRID_PREFIX, doe.site_id, doe.dynamic_operating_envelope_id),
                "version": 1,
                "description": doe.start_time.isoformat(),
                "interval": DateTimeIntervalType.model_validate(
                    {
                        "duration": doe.duration_seconds,
                        "start": int(doe.start_time.timestamp()),
                    }
                ),
                "creationTime": int(doe.changed_time.timestamp()),
                "EventStatus_": EventStatus.model_validate(
                    {
                        "currentStatus": 0,  # Set to 'scheduled'
                        "dateTime": int(doe.changed_time.timestamp()),  # Set to when the doe is created
                        "potentiallySuperseded": False,
                    }
                ),
                "DERControlBase_": DERControlBase.model_validate(
                    {
                        "opModImpLimW": DERControlMapper.map_to_active_power(doe.import_limit_active_watts),
                        "opModExpLimW": DERControlMapper.map_to_active_power(doe.export_limit_watts),
                    }
                ),
            }
        )

    @staticmethod
    def map_to_default_response(default_doe: DefaultDoeConfiguration) -> DefaultDERControl:
        """Creates a csip aus compliant DefaultDERControl from the specified defaults"""
        return DefaultDERControl.model_validate(
            {
                "mRID": generate_mrid(DOE_PROGRAM_MRID_PREFIX, DOE_DEFAULT_CONTROL_ID),
                "DERControlBase_": DERControlBase.model_validate(
                    {
                        "opModImpLimW": DERControlMapper.map_to_active_power(default_doe.import_limit_active_watts),
                        "opModExpLimW": DERControlMapper.map_to_active_power(default_doe.export_limit_active_watts),
                    }
                ),
            }
        )

    @staticmethod
    def doe_list_href(request_scope: DeviceOrAggregatorRequestScope) -> str:
        """Returns a href for a particular site's set of DER Controls"""
        return generate_href(
            uri.DERControlListUri, request_scope, site_id=request_scope.display_site_id, der_program_id=DOE_PROGRAM_ID
        )

    @staticmethod
    def active_doe_list_href(request_scope: DeviceOrAggregatorRequestScope) -> str:
        """Returns a href for a particular site's set of DER Controls"""
        return generate_href(
            uri.ActiveDERControlListUri,
            request_scope,
            site_id=request_scope.display_site_id,
            der_program_id=DOE_PROGRAM_ID,
        )

    @staticmethod
    def default_doe_href(request_scope: DeviceOrAggregatorRequestScope) -> str:
        """Returns a href for a particular site's set of DER Controls"""
        return generate_href(
            uri.DefaultDERControlUri,
            request_scope,
            site_id=request_scope.display_site_id,
            der_program_id=DOE_PROGRAM_ID,
        )

    @staticmethod
    def map_to_list_response(
        request_scope: DeviceOrAggregatorRequestScope,
        does: Sequence[DynamicOperatingEnvelope],
        total_does: int,
        source: DERControlListSource,
    ) -> DERControlListResponse:
        """Maps a page of DOEs into a DERControlListResponse. total_does should be the total of all DOEs accessible
        to a particular site

        source - What is this requesting this mapping? It will determine the href generated for the derc list"""

        href: str
        if source == DERControlListSource.DER_CONTROL_LIST:
            href = DERControlMapper.doe_list_href(request_scope)
        elif source == DERControlListSource.ACTIVE_DER_CONTROL_LIST:
            href = DERControlMapper.active_doe_list_href(request_scope)
        else:
            raise InvalidMappingError(f"Unsupported source {source} for calculating href")

        return DERControlListResponse.model_validate(
            {
                "href": href,
                "all_": total_does,
                "results": len(does),
                "subscribable": SubscribableType.resource_supports_non_conditional_subscriptions,
                "DERControl": [DERControlMapper.map_to_response(request_scope, site) for site in does],
            }
        )


class DERProgramMapper:
    @staticmethod
    def doe_href(rq_scope: DeviceOrAggregatorRequestScope) -> str:
        """Returns a href for a particular site's DER Program for Dynamic Operating Envelopes"""
        return generate_href(
            uri.DERProgramUri, rq_scope, site_id=rq_scope.display_site_id, der_program_id=DOE_PROGRAM_ID
        )

    @staticmethod
    def doe_list_href(rq_scope: DeviceOrAggregatorRequestScope) -> str:
        """Returns a href for a particular site's DER Program list"""
        return generate_href(uri.DERProgramListUri, rq_scope, site_id=rq_scope.display_site_id)

    @staticmethod
    def doe_program_response(
        rq_scope: DeviceOrAggregatorRequestScope, total_does: int, default_doe: Optional[DefaultDoeConfiguration]
    ) -> DERProgramResponse:
        """Returns a static Dynamic Operating Envelope program response"""

        # The default DOE link will only be included if we have a default DOE configured for this site
        default_der_link: Optional[Link] = None
        if default_doe is not None:
            default_der_link = Link.model_validate(
                {
                    "href": DERControlMapper.default_doe_href(rq_scope),
                }
            )

        return DERProgramResponse.model_validate(
            {
                "href": DERProgramMapper.doe_href(rq_scope),
                "mRID": generate_mrid(DOE_PROGRAM_MRID_PREFIX, rq_scope.display_site_id),
                "primacy": PrimacyType.IN_HOME_ENERGY_MANAGEMENT_SYSTEM,
                "description": "Dynamic Operating Envelope",
                "DefaultDERControlLink": default_der_link,
                "ActiveDERControlListLink": ListLink.model_validate(
                    {
                        "href": DERControlMapper.active_doe_list_href(rq_scope),
                        "all_": 1 if total_does > 0 else 0,
                    }
                ),
                "DERControlListLink": ListLink.model_validate(
                    {
                        "href": DERControlMapper.doe_list_href(rq_scope),
                        "all_": total_does,
                    }
                ),
            }
        )

    @staticmethod
    def doe_program_list_response(
        rq_scope: DeviceOrAggregatorRequestScope, total_does: int, default_doe: Optional[DefaultDoeConfiguration]
    ) -> DERProgramListResponse:
        """Returns a fixed list of just the DOE Program"""
        return DERProgramListResponse.model_validate(
            {
                "href": DERProgramMapper.doe_list_href(rq_scope),
                "DERProgram": [DERProgramMapper.doe_program_response(rq_scope, total_does, default_doe)],
                "all_": 1,
                "results": 1,
            }
        )
