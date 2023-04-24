

from decimal import Decimal

from envoy.server.model.doe import DOE_DECIMAL_PLACES, DOE_DECIMAL_POWER, DynamicOperatingEnvelope
from envoy.server.schema.csip_aus.doe import CSIPAusDERControlBase
from envoy.server.schema.sep2.der import ActivePower, DERControlListResponse, DERControlResponse
from envoy.server.schema.sep2.time import DateTimeIntervalType


class DERControlMapper:
    @staticmethod
    def map_to_active_power(p: Decimal) -> ActivePower:
        """Creates an ActivePower instance from our own internal power decimal reading"""
        return ActivePower.validate({
            "value": int(p * DOE_DECIMAL_POWER),
            "multiplier": DOE_DECIMAL_PLACES,
        })

    @staticmethod
    def map_to_response(doe: DynamicOperatingEnvelope) -> DERControlResponse:
        """Creates a csip aus compliant DERControlResponse from the specific doe"""
        return DERControlResponse.validate({
            "mRID": f"{doe.dynamic_operating_envelope_id:x}",
            "version": 1,
            "description": doe.start_time.isoformat(),
            "interval": DateTimeIntervalType.validate({
                "duration": doe.duration_seconds,
                "start": int(doe.start_time.timestamp()),
            }),
            "creationTime": doe.changed_time.timestamp(),

            "DERControlBase_": CSIPAusDERControlBase.validate({
                "opModImpLimW": DERControlMapper.map_to_active_power(doe.import_limit_active_watts),
                "opModExpLimW": DERControlMapper.map_to_active_power(doe.export_limit_watts),
            })
        })

    @staticmethod
    def map_to_list_response(does: list[DynamicOperatingEnvelope], total_does: int,
                             site_id: int) -> DERControlListResponse:
        """Maps a page of DOEs into a DERControlListResponse. total_does should be the total of all DOEs accessible
        to a particular site"""
        return DERControlListResponse.validate(
            {
                "href": f"/derp/{site_id}/doe/derc",
                "all_": total_does,
                "results": len(does),
                "DERControl": [
                    DERControlMapper.map_to_response(site) for site in does
                ],
            }
        )
