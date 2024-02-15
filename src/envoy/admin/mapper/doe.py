from datetime import datetime

from envoy_schema.admin.schema.doe import DynamicOperatingEnvelopeRequest

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
