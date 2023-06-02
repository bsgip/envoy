from envoy.admin.schema.doe import DynamicOperatingEnvelopeAdmin
from envoy.server.model.doe import DynamicOperatingEnvelope


class DoeMapper:
    @staticmethod
    def map_from_request(doe: DynamicOperatingEnvelopeAdmin) -> DynamicOperatingEnvelope:
        return DynamicOperatingEnvelope(
            dynamic_operating_envelope_id=doe.dynamic_operating_envelope_id,
            site_id=doe.site_id,  # TODO ?
            changed_time=doe.changed_time,
            duration_seconds=doe.duration_seconds,
            import_limit_active_watts=doe.import_limit_active_watts,
            export_limit_watts=doe.export_limit_watts,
        )
