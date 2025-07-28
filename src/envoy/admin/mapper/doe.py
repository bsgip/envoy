from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable, Optional

from envoy_schema.admin.schema.doe import (
    DoePageResponse,
    DynamicOperatingEnvelopeRequest,
    DynamicOperatingEnvelopeResponse,
)

from envoy.server.model.doe import DynamicOperatingEnvelope

# This is a legacy hangover from before we had site control groups
# Expect this all to be removed in a future release
DEFAULT_DOE_SITE_CONTROL_GROUP_ID = 1


class DoeListMapper:
    @staticmethod
    def map_from_request(
        changed_time: datetime, doe_list: list[DynamicOperatingEnvelopeRequest]
    ) -> list[DynamicOperatingEnvelope]:
        return [
            DynamicOperatingEnvelope(
                site_id=doe.site_id,
                site_control_group_id=DEFAULT_DOE_SITE_CONTROL_GROUP_ID,
                calculation_log_id=doe.calculation_log_id,
                changed_time=changed_time,
                start_time=doe.start_time,
                duration_seconds=doe.duration_seconds,
                import_limit_active_watts=doe.import_limit_active_watts,
                export_limit_watts=doe.export_limit_watts,
                end_time=doe.start_time + timedelta(seconds=doe.duration_seconds),
                superseded=False,  # Set to False - we won't be checking against existing DOEs here
            )
            for doe in doe_list
        ]

    @staticmethod
    def map_to_response(doe: DynamicOperatingEnvelope) -> DynamicOperatingEnvelopeResponse:
        return DynamicOperatingEnvelopeResponse(
            dynamic_operating_envelope_id=doe.dynamic_operating_envelope_id,
            created_time=doe.created_time,
            changed_time=doe.changed_time,
            site_id=doe.site_id,
            calculation_log_id=doe.calculation_log_id,
            duration_seconds=doe.duration_seconds,
            import_limit_active_watts=(
                doe.import_limit_active_watts if doe.import_limit_active_watts is not None else Decimal(0)
            ),
            export_limit_watts=doe.export_limit_watts if doe.export_limit_watts is not None else Decimal(0),
            start_time=doe.start_time,
        )

    @staticmethod
    def map_to_paged_response(
        total_count: int, limit: int, start: int, after: Optional[datetime], does: Iterable[DynamicOperatingEnvelope]
    ) -> DoePageResponse:
        return DoePageResponse(
            total_count=total_count,
            limit=limit,
            start=start,
            after=after,
            does=[DoeListMapper.map_to_response(d) for d in does],
        )
