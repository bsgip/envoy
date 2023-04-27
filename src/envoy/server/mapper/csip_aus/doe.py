

from decimal import Decimal

from envoy.server.model.doe import DOE_DECIMAL_PLACES, DOE_DECIMAL_POWER, DynamicOperatingEnvelope
from envoy.server.schema import uri
from envoy.server.schema.sep2.base import ListLink
from envoy.server.schema.sep2.der import (
    ActivePower,
    DERControlBase,
    DERControlListResponse,
    DERControlResponse,
    DERProgramListResponse,
    DERProgramResponse,
)
from envoy.server.schema.sep2.pricing import PrimacyType
from envoy.server.schema.sep2.time import DateTimeIntervalType

DOE_PROGRAM_MRID: str = 'd0e'
DOE_PROGRAM_ID: str = 'doe'


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

            "DERControlBase_": DERControlBase.validate({
                "opModImpLimW": DERControlMapper.map_to_active_power(doe.import_limit_active_watts),
                "opModExpLimW": DERControlMapper.map_to_active_power(doe.export_limit_watts),
            })
        })

    @staticmethod
    def doe_list_href(site_id: int) -> str:
        """Returns a href for a particular site's set of DER Controls"""
        return uri.DERControlListUri.format(site_id=site_id, der_program_id=DOE_PROGRAM_ID)

    @staticmethod
    def map_to_list_response(does: list[DynamicOperatingEnvelope], total_does: int,
                             site_id: int) -> DERControlListResponse:
        """Maps a page of DOEs into a DERControlListResponse. total_does should be the total of all DOEs accessible
        to a particular site"""
        return DERControlListResponse.validate(
            {
                "href": DERControlMapper.doe_list_href(site_id),
                "all_": total_does,
                "results": len(does),
                "DERControl": [
                    DERControlMapper.map_to_response(site) for site in does
                ],
            }
        )


class DERProgramMapper:
    @staticmethod
    def doe_href(site_id: int) -> str:
        """Returns a href for a particular site's DER Program for Dynamic Operating Envelopes"""
        return uri.DERProgramUri.format(site_id=site_id, der_program_id=DOE_PROGRAM_ID)

    @staticmethod
    def doe_list_href(site_id: int) -> str:
        """Returns a href for a particular site's DER Program list"""
        return uri.DERProgramListUri.format(site_id=site_id)

    @staticmethod
    def doe_program_response(site_id: int, total_does: int) -> DERProgramResponse:
        """Returns a static Dynamic Operating Envelope program response"""
        return DERProgramResponse.validate({
            "href": DERProgramMapper.doe_href(site_id),
            "mRID": f"{DOE_PROGRAM_MRID}{site_id:x}",
            "primacy": PrimacyType.IN_HOME_ENERGY_MANAGEMENT_SYSTEM,
            "description": "Dynamic Operating Envelope",
            "DERControlListLink": ListLink.validate({
                "href": DERControlMapper.doe_list_href(site_id),
                "all_": total_does,
            })
        })

    @staticmethod
    def doe_program_list_response(site_id: int, total_does: int) -> DERProgramListResponse:
        """Returns a fixed list of just the DOE Program"""
        return DERProgramListResponse.validate({
            "href": DERProgramMapper.doe_list_href(site_id),
            "DERProgram": [DERProgramMapper.doe_program_response(site_id, total_does)],
            "all_": 1,
            "results": 1,
        })
