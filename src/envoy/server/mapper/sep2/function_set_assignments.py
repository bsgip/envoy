from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.function_set_assignments import (
    FunctionSetAssignmentsListResponse,
    FunctionSetAssignmentsResponse,
)
from envoy_schema.server.schema.sep2.identification import Link, ListLink

from envoy.server.mapper.common import generate_href
from envoy.server.mapper.sep2.mrid import MridMapper
from envoy.server.request_scope import SiteRequestScope


class FunctionSetAssignmentsMapper:
    @staticmethod
    def map_to_response(
        scope: SiteRequestScope, fsa_id: int, doe_count: int, tariff_count: int
    ) -> FunctionSetAssignmentsResponse:
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
                    href=generate_href(uri.TariffProfileListUri, scope, site_id=scope.site_id), all_=tariff_count
                ),
                "DERProgramListLink": ListLink(
                    href=generate_href(uri.DERProgramListUri, scope, site_id=scope.site_id), all_=doe_count
                ),
            }
        )

    @staticmethod
    def map_to_list_response(
        scope: SiteRequestScope, function_set_assignments: list[FunctionSetAssignmentsResponse], pollrate_seconds: int
    ) -> FunctionSetAssignmentsListResponse:
        return FunctionSetAssignmentsListResponse(
            href=generate_href(uri.FunctionSetAssignmentsListUri, scope, site_id=scope.site_id),
            pollRate=pollrate_seconds,
            all_=1,
            results=1,
            FunctionSetAssignments=function_set_assignments,
        )
