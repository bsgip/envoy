from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.function_set_assignments import (
    FunctionSetAssignmentsListResponse,
    FunctionSetAssignmentsResponse,
)
from envoy_schema.server.schema.sep2.identification import Link, ListLink
from envoy_schema.server.schema.sep2.types import SubscribableType

from envoy.server.mapper.common import generate_href
from envoy.server.mapper.sep2.mrid import MridMapper
from envoy.server.request_scope import SiteRequestScope


class FunctionSetAssignmentsMapper:
    @staticmethod
    def map_to_response(scope: SiteRequestScope, fsa_id: int) -> FunctionSetAssignmentsResponse:
        return FunctionSetAssignmentsResponse.model_validate(
            {
                "href": generate_href(
                    uri.FunctionSetAssignmentsUri,
                    scope,
                    fsa_id=fsa_id,
                    site_id=scope.site_id,
                ),
                "mRID": MridMapper.encode_function_set_assignment_mrid(scope, scope.site_id, fsa_id),
                "description": "",
                "TimeLink": Link(href=generate_href(uri.TimeUri, scope)),
                "TariffProfileListLink": ListLink(
                    href=generate_href(uri.TariffProfileFSAListUri, scope, site_id=scope.site_id, fsa_id=fsa_id),
                    all_=None,
                ),
                "DERProgramListLink": ListLink(
                    href=generate_href(uri.DERProgramFSAListUri, scope, site_id=scope.site_id, fsa_id=fsa_id), all_=None
                ),
            }
        )

    @staticmethod
    def map_to_list_response(
        scope: SiteRequestScope, fsa_ids: list[int], total_fsa_ids: int, pollrate_seconds: int
    ) -> FunctionSetAssignmentsListResponse:
        return FunctionSetAssignmentsListResponse(
            href=generate_href(uri.FunctionSetAssignmentsListUri, scope, site_id=scope.site_id),
            subscribable=SubscribableType.resource_supports_non_conditional_subscriptions,
            pollRate=pollrate_seconds,
            all_=total_fsa_ids,
            results=len(fsa_ids),
            FunctionSetAssignments=[FunctionSetAssignmentsMapper.map_to_response(scope, fsa_id) for fsa_id in fsa_ids],
        )
