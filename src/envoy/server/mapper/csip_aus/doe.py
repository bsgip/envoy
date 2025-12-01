from datetime import datetime
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
from envoy_schema.server.schema.sep2.event import EventStatus, EventStatusType
from envoy_schema.server.schema.sep2.identification import Link, ListLink
from envoy_schema.server.schema.sep2.types import DateTimeIntervalType, SubscribableType

from envoy.server.exception import InvalidMappingError
from envoy.server.mapper.common import generate_href
from envoy.server.mapper.sep2.mrid import MridMapper, ResponseSetType
from envoy.server.mapper.sep2.response import SPECIFIC_RESPONSE_REQUIRED, ResponseListMapper
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope, ArchiveSiteControlGroup
from envoy.server.model.doe import DynamicOperatingEnvelope, SiteControlGroup
from envoy.server.model.site import DefaultSiteControl
from envoy.server.request_scope import AggregatorRequestScope, BaseRequestScope, DeviceOrAggregatorRequestScope


class DERControlListSource(IntEnum):
    DER_CONTROL_LIST = auto()
    ACTIVE_DER_CONTROL_LIST = auto()


class DERControlMapper:
    @staticmethod
    def map_to_active_power(p: Decimal, pow10_multiplier: int) -> ActivePower:
        """Creates an ActivePower instance from our own internal power decimal reading"""
        decimal_power = int(pow(10, -pow10_multiplier))
        return ActivePower(
            value=int(p * decimal_power),
            multiplier=pow10_multiplier,
        )

    @staticmethod
    def map_to_hundredths(p: Decimal) -> int:
        """Maps to the 2030.5 SignedPercent (or any other type represented in hundredths)

        Percent values should be in the range -10000 - 10000. (10000 = 100%)

        Other values can be interpreted as (123.45 = 12345)"""
        return int(p * 100)

    @staticmethod
    def map_to_response(
        scope: Union[DeviceOrAggregatorRequestScope, AggregatorRequestScope],
        site_control_group_id: int,
        doe: Union[DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope],
        pow10_multiplier: int,
        now: datetime,
    ) -> DERControlResponse:
        """Creates a csip aus compliant DERControlResponse from the specific doe. Needs to know current datetime
        in order to determine if the control is active or scheduled"""

        is_intersecting_now = doe.start_time <= now and doe.end_time > now
        event_status: int
        event_status_time: datetime
        if isinstance(doe, ArchiveDynamicOperatingEnvelope) and doe.deleted_time is not None:
            # This is a deleted DOE
            event_status = (
                EventStatusType.Cancelled
                if doe.randomize_start_seconds is None
                else EventStatusType.CancelledWithRandomization
            )
            event_status_time = doe.deleted_time
        elif doe.superseded:
            event_status = EventStatusType.Superseded
            event_status_time = doe.changed_time
        else:
            # This is either a schedule / active DOE
            event_status = EventStatusType.Active if is_intersecting_now else EventStatusType.Scheduled
            event_status_time = doe.changed_time

        return DERControlResponse.model_validate(
            {
                "href": generate_href(
                    uri.DERControlUri,
                    scope,
                    site_id=scope.display_site_id,
                    der_program_id=site_control_group_id,
                    derc_id=doe.dynamic_operating_envelope_id,
                ),
                "mRID": MridMapper.encode_doe_mrid(scope, doe.dynamic_operating_envelope_id),
                "version": 1,
                "description": doe.start_time.isoformat(),
                "replyTo": ResponseListMapper.response_list_href(
                    scope, scope.display_site_id, ResponseSetType.SITE_CONTROLS
                ),  # Response function set
                "responseRequired": SPECIFIC_RESPONSE_REQUIRED,  # Response function set
                "interval": DateTimeIntervalType.model_validate(
                    {
                        "duration": doe.duration_seconds,
                        "start": int(doe.start_time.timestamp()),
                    }
                ),
                "randomizeStart": doe.randomize_start_seconds,
                "creationTime": int(doe.changed_time.timestamp()),
                "EventStatus_": EventStatus.model_validate(
                    {
                        "currentStatus": event_status,
                        "dateTime": int(event_status_time.timestamp()),
                        "potentiallySuperseded": False,
                    }
                ),
                "DERControlBase_": DERControlBase(
                    opModImpLimW=(
                        DERControlMapper.map_to_active_power(doe.import_limit_active_watts, pow10_multiplier)
                        if doe.import_limit_active_watts is not None
                        else None
                    ),
                    opModExpLimW=(
                        DERControlMapper.map_to_active_power(doe.export_limit_watts, pow10_multiplier)
                        if doe.export_limit_watts is not None
                        else None
                    ),
                    opModLoadLimW=(
                        DERControlMapper.map_to_active_power(doe.load_limit_active_watts, pow10_multiplier)
                        if doe.load_limit_active_watts is not None
                        else None
                    ),
                    opModGenLimW=(
                        DERControlMapper.map_to_active_power(doe.generation_limit_active_watts, pow10_multiplier)
                        if doe.generation_limit_active_watts is not None
                        else None
                    ),
                    opModEnergize=doe.set_energized if doe.set_energized is not None else None,
                    opModConnect=doe.set_connected if doe.set_connected is not None else None,
                    opModFixedW=(
                        DERControlMapper.map_to_hundredths(doe.set_point_percentage)
                        if doe.set_point_percentage is not None
                        else None
                    ),
                    rampTms=(
                        DERControlMapper.map_to_hundredths(doe.ramp_time_seconds)
                        if doe.ramp_time_seconds is not None
                        else None
                    ),
                ),
            }
        )

    @staticmethod
    def map_to_default_response(
        scope: BaseRequestScope,
        default_doe: DefaultSiteControl,
        display_site_id: int,
        der_program_id: int,
        pow10_multipier: int,
    ) -> DefaultDERControl:
        """Creates a csip aus compliant DefaultDERControl from the specified defaults"""

        return DefaultDERControl(
            href=DERControlMapper.default_control_href(scope, display_site_id, der_program_id),
            version=default_doe.version,
            subscribable=SubscribableType.resource_supports_non_conditional_subscriptions,
            mRID=MridMapper.encode_default_doe_mrid(scope),
            setGradW=default_doe.ramp_rate_percent_per_second,
            DERControlBase_=DERControlBase(
                opModImpLimW=(
                    DERControlMapper.map_to_active_power(default_doe.import_limit_active_watts, pow10_multipier)
                    if default_doe.import_limit_active_watts is not None
                    else None
                ),
                opModExpLimW=(
                    DERControlMapper.map_to_active_power(default_doe.export_limit_active_watts, pow10_multipier)
                    if default_doe.export_limit_active_watts is not None
                    else None
                ),
                opModLoadLimW=(
                    DERControlMapper.map_to_active_power(default_doe.load_limit_active_watts, pow10_multipier)
                    if default_doe.load_limit_active_watts is not None
                    else None
                ),
                opModGenLimW=(
                    DERControlMapper.map_to_active_power(default_doe.generation_limit_active_watts, pow10_multipier)
                    if default_doe.generation_limit_active_watts is not None
                    else None
                ),
            ),
        )

    @staticmethod
    def site_control_list_href(
        request_scope: Union[AggregatorRequestScope, DeviceOrAggregatorRequestScope], site_control_group_id: int
    ) -> str:
        """Returns a href for a particular site's set of DER Controls"""
        return generate_href(
            uri.DERControlListUri,
            request_scope,
            site_id=request_scope.display_site_id,
            der_program_id=site_control_group_id,
        )

    @staticmethod
    def active_control_list_href(
        request_scope: Union[AggregatorRequestScope, DeviceOrAggregatorRequestScope], site_control_group_id: int
    ) -> str:
        """Returns a href for a particular site's set of DER Controls"""
        return generate_href(
            uri.ActiveDERControlListUri,
            request_scope,
            site_id=request_scope.display_site_id,
            der_program_id=site_control_group_id,
        )

    @staticmethod
    def default_control_href(request_scope: BaseRequestScope, site_id: int, site_control_group_id: int) -> str:
        """Returns a href for a particular site's set of DER Controls"""
        return generate_href(
            uri.DefaultDERControlUri,
            request_scope,
            site_id=site_id,
            der_program_id=site_control_group_id,
        )

    @staticmethod
    def map_to_list_response(
        request_scope: DeviceOrAggregatorRequestScope,
        site_control_group_id: int,
        site_controls: Sequence[Union[DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope]],
        total_controls: int,
        source: DERControlListSource,
        power10_multiplier: int,
        now: datetime,
    ) -> DERControlListResponse:
        """Maps a page of DOEs into a DERControlListResponse. total_controls should be the total of all controls
        accessible to a particular site

        source - What is this requesting this mapping? It will determine the href generated for the derc list"""

        href: str
        if source == DERControlListSource.DER_CONTROL_LIST:
            href = DERControlMapper.site_control_list_href(request_scope, site_control_group_id)
        elif source == DERControlListSource.ACTIVE_DER_CONTROL_LIST:
            href = DERControlMapper.active_control_list_href(request_scope, site_control_group_id)
        else:
            raise InvalidMappingError(f"Unsupported source {source} for calculating href")

        return DERControlListResponse.model_validate(
            {
                "href": href,
                "all_": total_controls,
                "results": len(site_controls),
                "subscribable": SubscribableType.resource_supports_non_conditional_subscriptions,
                "DERControl": [
                    DERControlMapper.map_to_response(
                        request_scope, site_control_group_id, site, power10_multiplier, now
                    )
                    for site in site_controls
                ],
            }
        )


class DERProgramMapper:
    @staticmethod
    def derp_href(
        rq_scope: Union[AggregatorRequestScope, DeviceOrAggregatorRequestScope], site_control_group_id: int
    ) -> str:
        """Returns a href for a particular site's DER Program for the specified site control group"""
        return generate_href(
            uri.DERProgramUri,
            rq_scope,
            site_id=rq_scope.display_site_id,
            der_program_id=site_control_group_id,
        )

    @staticmethod
    def doe_list_href(rq_scope: DeviceOrAggregatorRequestScope, fsa_id: Optional[int]) -> str:
        """Returns a href for a particular site's DER Program list"""
        if fsa_id is None:
            return generate_href(uri.DERProgramListUri, rq_scope, site_id=rq_scope.display_site_id)
        else:
            return generate_href(uri.DERProgramFSAListUri, rq_scope, site_id=rq_scope.display_site_id, fsa_id=fsa_id)

    @staticmethod
    def doe_program_response(
        rq_scope: Union[AggregatorRequestScope, DeviceOrAggregatorRequestScope],
        total_controls: Optional[int],
        site_control_group: Union[SiteControlGroup, ArchiveSiteControlGroup],
        default_doe: Optional[DefaultSiteControl],
    ) -> DERProgramResponse:
        """Returns a DERProgram response for a SiteControlGroup"""

        # The default control link will only be included if we have a default DOE configured for this site
        default_der_link: Optional[Link] = None
        if default_doe is not None:
            default_der_link = Link.model_validate(
                {
                    "href": DERControlMapper.default_control_href(
                        rq_scope, rq_scope.display_site_id, site_control_group.site_control_group_id
                    ),
                }
            )

        active_der_control_count: Optional[int] = None
        if total_controls is not None:
            active_der_control_count = 1 if total_controls > 0 else 0

        return DERProgramResponse.model_validate(
            {
                "href": DERProgramMapper.derp_href(rq_scope, site_control_group.site_control_group_id),
                "mRID": MridMapper.encode_doe_program_mrid(
                    rq_scope, site_control_group.site_control_group_id, rq_scope.display_site_id
                ),
                "primacy": site_control_group.primacy,
                "description": site_control_group.description,
                "DefaultDERControlLink": default_der_link,
                "ActiveDERControlListLink": ListLink.model_validate(
                    {
                        "href": DERControlMapper.active_control_list_href(
                            rq_scope, site_control_group.site_control_group_id
                        ),
                        "all_": active_der_control_count,
                    }
                ),
                "DERControlListLink": ListLink.model_validate(
                    {
                        "href": DERControlMapper.site_control_list_href(
                            rq_scope, site_control_group.site_control_group_id
                        ),
                        "all_": total_controls,
                    }
                ),
            }
        )

    @staticmethod
    def doe_program_list_response(
        rq_scope: DeviceOrAggregatorRequestScope,
        site_control_groups_with_control_count: list[tuple[SiteControlGroup, int]],
        total_site_control_groups: int,
        default_doe: Optional[DefaultSiteControl],
        pollrate_seconds: int,
        fsa_id: Optional[int],
    ) -> DERProgramListResponse:
        """Returns a list of all DERPrograms.

        site_control_groups_with_control_count: List of groups to encode tupled with the count of upcoming controls"""
        return DERProgramListResponse.model_validate(
            {
                "href": DERProgramMapper.doe_list_href(rq_scope, fsa_id),
                "pollRate": pollrate_seconds,
                "subscribable": SubscribableType.resource_supports_non_conditional_subscriptions,
                "DERProgram": [
                    DERProgramMapper.doe_program_response(rq_scope, control_count, group, default_doe)
                    for group, control_count in site_control_groups_with_control_count
                ],
                "all_": total_site_control_groups,
                "results": len(site_control_groups_with_control_count),
            }
        )
