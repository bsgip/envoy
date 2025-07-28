from datetime import datetime, timedelta
from typing import Iterable, Optional

from envoy_schema.admin.schema.site_control import (
    SiteControlGroupPageResponse,
    SiteControlGroupRequest,
    SiteControlGroupResponse,
    SiteControlPageResponse,
    SiteControlRequest,
    SiteControlResponse,
)

from envoy.server.model.doe import DynamicOperatingEnvelope, SiteControlGroup


class SiteControlGroupListMapper:
    @staticmethod
    def map_from_request(request: SiteControlGroupRequest, changed_time: datetime) -> SiteControlGroup:
        return SiteControlGroup(
            description=request.description[:32],
            primacy=request.primacy,
            changed_time=changed_time,
            fsa_id=request.fsa_id,
        )

    @staticmethod
    def map_to_response(site_control_group: SiteControlGroup) -> SiteControlGroupResponse:
        return SiteControlGroupResponse(
            site_control_group_id=site_control_group.site_control_group_id,
            description=site_control_group.description,
            primacy=site_control_group.primacy,
            created_time=site_control_group.created_time,
            changed_time=site_control_group.changed_time,
            fsa_id=site_control_group.fsa_id,
        )

    @staticmethod
    def map_to_paged_response(
        total_count: int, limit: int, start: int, after: Optional[datetime], groups: Iterable[SiteControlGroup]
    ) -> SiteControlGroupPageResponse:
        return SiteControlGroupPageResponse(
            total_count=total_count,
            limit=limit,
            start=start,
            after=after,
            site_control_groups=[SiteControlGroupListMapper.map_to_response(g) for g in groups],
        )


class SiteControlListMapper:
    @staticmethod
    def map_from_request(
        site_control_group_id: int, changed_time: datetime, control_list: list[SiteControlRequest]
    ) -> list[DynamicOperatingEnvelope]:
        return [
            DynamicOperatingEnvelope(
                site_id=c.site_id,
                site_control_group_id=site_control_group_id,
                calculation_log_id=c.calculation_log_id,
                changed_time=changed_time,
                start_time=c.start_time,
                duration_seconds=c.duration_seconds,
                randomize_start_seconds=c.randomize_start_seconds,
                import_limit_active_watts=c.import_limit_watts,
                export_limit_watts=c.export_limit_watts,
                generation_limit_active_watts=c.generation_limit_watts,
                load_limit_active_watts=c.load_limit_watts,
                set_energized=c.set_energized,
                set_connected=c.set_connect,
                set_point_percentage=c.set_point_percentage,
                end_time=c.start_time + timedelta(seconds=c.duration_seconds),
                ramp_time_seconds=c.ramp_time_seconds,
                superseded=False,
            )
            for c in control_list
        ]

    @staticmethod
    def map_to_response(control: DynamicOperatingEnvelope) -> SiteControlResponse:
        return SiteControlResponse(
            site_control_id=control.dynamic_operating_envelope_id,
            created_time=control.created_time,
            changed_time=control.changed_time,
            site_id=control.site_id,
            calculation_log_id=control.calculation_log_id,
            duration_seconds=control.duration_seconds,
            import_limit_watts=control.import_limit_active_watts,
            export_limit_watts=control.export_limit_watts,
            start_time=control.start_time,
            randomize_start_seconds=control.randomize_start_seconds,
            generation_limit_watts=control.generation_limit_active_watts,
            load_limit_watts=control.load_limit_active_watts,
            set_energized=control.set_energized,
            set_connect=control.set_connected,
            set_point_percentage=control.set_point_percentage,
            ramp_time_seconds=control.ramp_time_seconds,
            superseded=control.superseded,
        )

    @staticmethod
    def map_to_paged_response(
        total_count: int, limit: int, start: int, after: Optional[datetime], does: Iterable[DynamicOperatingEnvelope]
    ) -> SiteControlPageResponse:
        return SiteControlPageResponse(
            total_count=total_count,
            limit=limit,
            start=start,
            after=after,
            controls=[SiteControlListMapper.map_to_response(d) for d in does],
        )
