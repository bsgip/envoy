

from decimal import Decimal

from envoy.server.model.doe import DOE_DECIMAL_PLACES, DOE_DECIMAL_POWER, DynamicOperatingEnvelope
from envoy.server.schema.csip_aus.doe import CSIPAusDERControlBase
from envoy.server.schema.sep2.der import ActivePower, DERControlResponse
from envoy.server.schema.sep2.time import DateTimeIntervalType


class DynamicOperatingEnvelopeMapper:
    @staticmethod
    def map_to_active_power(p: Decimal) -> ActivePower:
        """Creates an ActivePower instance from our own internal power decimal reading"""
        return ActivePower.validate({
            "value": int(p * DOE_DECIMAL_POWER),
            "multiplier": DOE_DECIMAL_PLACES,
        })

    @staticmethod
    def map_to_response(doe: DynamicOperatingEnvelope) -> DERControlResponse:
        return DERControlResponse.validate({
            "mRID": f"{doe.dynamic_operating_envelope_id:x}",
            "interval": DateTimeIntervalType.validate({
                "duration": doe.duration_seconds,
                "start": int(doe.start_time.timestamp()),
            }),
            "creationTime": doe.changed_time.timestamp(),

            "DERControlBase_": CSIPAusDERControlBase.validate({
                "opModImpLimW": DynamicOperatingEnvelopeMapper.map_to_active_power(doe.import_limit_active_watts),
                "opModExpLimW": DynamicOperatingEnvelopeMapper.map_to_active_power(doe.export_limit_watts),
            })
        })
