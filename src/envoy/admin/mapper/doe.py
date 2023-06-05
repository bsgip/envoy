from datetime import datetime
from zoneinfo import ZoneInfo

from envoy.admin.schema.doe import DynamicOperatingEnvelopeAdminRequest, DynamicOperatingEnvelopeAdminResponse
from envoy.server.model.doe import DynamicOperatingEnvelope


class DoeMapper:
    @staticmethod
    def map_from_request(doe: DynamicOperatingEnvelopeAdminRequest) -> DynamicOperatingEnvelope:
        return DynamicOperatingEnvelope(
            site_id=doe.site_id,
            changed_time=datetime.now(tz=ZoneInfo("UTC")),
            duration_seconds=doe.duration_seconds,
            import_limit_active_watts=doe.import_limit_active_watts,
            export_limit_watts=doe.export_limit_watts,
        )

    @staticmethod
    def map_to_response(doe: DynamicOperatingEnvelope) -> DynamicOperatingEnvelopeAdminResponse:
        return DynamicOperatingEnvelopeAdminResponse(
            dynamic_operating_envelope_id=doe.dynamic_operating_envelope_id,
            site_id=doe.site_id,
            changed_time=doe.changed_time,
            duration_seconds=doe.duration_seconds,
            import_limit_active_watts=doe.import_limit_active_watts,
            export_limit_watts=doe.export_limit_watts,
        )
