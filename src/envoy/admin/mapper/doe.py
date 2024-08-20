from datetime import datetime
from typing import Iterable, Optional

from envoy_schema.admin.schema.doe import (
    DoePageResponse,
    DynamicOperatingEnvelopeRequest,
    DynamicOperatingEnvelopeResponse,
)

from envoy.server.model.doe import DynamicOperatingEnvelope


class DoeListMapper:
    @staticmethod
    def map_from_request(
        changed_time: datetime, doe_list: list[DynamicOperatingEnvelopeRequest]
    ) -> list[DynamicOperatingEnvelope]:
        return [
            DynamicOperatingEnvelope(
                site_id=doe.site_id,
                changed_time=changed_time,
                start_time=doe.start_time,
                duration_seconds=doe.duration_seconds,
                import_limit_active_watts=doe.import_limit_active_watts,
                export_limit_watts=doe.export_limit_watts,
            )
            for doe in doe_list
        ]

    @staticmethod
    def map_to_response(doe: DynamicOperatingEnvelope) -> DynamicOperatingEnvelopeResponse:
        return DynamicOperatingEnvelopeResponse(
            dynamic_operating_envelope_id=doe.dynamic_operating_envelope_id,
            changed_time=doe.changed_time,
            site_id=doe.site_id,
            duration_seconds=doe.duration_seconds,
            import_limit_active_watts=doe.import_limit_active_watts,
            export_limit_watts=doe.export_limit_watts,
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
