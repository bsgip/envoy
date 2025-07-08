from datetime import datetime
from decimal import Decimal
from typing import Sequence
from envoy_schema.server.schema.sep2.types import UomType

from envoy_schema.admin.schema.site_reading import (
    CSIPAusSiteReading,
    CSIPAusSiteReadingPageResponse,
    CSIPAusSiteReadingUnit,
    PhaseEnum,
)
from envoy.server.model.site_reading import SiteReading
from envoy_schema.server.schema.sep2.types import FlowDirectionType


class AdminSiteReadingMapper:
    """Mapper for converting between domain models and CSIP AUS schema objects."""

    # Mapping from phase codes to PhaseEnum to handle other phases as unknown (non-csip compliant)
    PHASE_CODE_TO_ENUM_MAP = {
        0: PhaseEnum.NA,
        129: PhaseEnum.AN,
        65: PhaseEnum.BN,
        33: PhaseEnum.CN,
    }

    @staticmethod
    def map_to_csip_aus_reading(
        site_reading: SiteReading, requested_unit: CSIPAusSiteReadingUnit
    ) -> CSIPAusSiteReading:

        reading_type = site_reading.site_reading_type

        # Convert raw value using power of ten multiplier
        adjusted_value = Decimal(site_reading.value) * (Decimal("10") ** reading_type.power_of_ten_multiplier)

        # Apply flow direction (load convention: positive = import from grid)
        if reading_type.flow_direction == FlowDirectionType.REVERSE:
            adjusted_value *= -1

        # Map phase code to PhaseEnum with fallback to NA for unknown values
        phase_enum = AdminSiteReadingMapper.PHASE_CODE_TO_ENUM_MAP.get(reading_type.phase, PhaseEnum.NA)

        return CSIPAusSiteReading(
            reading_start_time=site_reading.time_period_start,
            duration_seconds=site_reading.time_period_seconds,
            phase=phase_enum,
            value=adjusted_value,
            csip_aus_unit=requested_unit,
        )

    @staticmethod
    def map_to_csip_aus_reading_page_response(
        site_readings: Sequence[SiteReading],
        total_count: int,
        start: int,
        limit: int,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
        requested_unit: CSIPAusSiteReadingUnit,
    ) -> CSIPAusSiteReadingPageResponse:

        csip_readings = [
            AdminSiteReadingMapper.map_to_csip_aus_reading(reading, requested_unit) for reading in site_readings
        ]

        return CSIPAusSiteReadingPageResponse(
            total_count=total_count,
            limit=limit,
            start=start,
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
            readings=csip_readings,
        )

    @staticmethod
    def csip_unit_to_uom(csip_unit: CSIPAusSiteReadingUnit) -> UomType:

        uom_map = {
            CSIPAusSiteReadingUnit.ACTIVEPOWER: UomType.REAL_POWER_WATT,
            CSIPAusSiteReadingUnit.REACTIVEPOWER: UomType.REACTIVE_POWER_VAR,
            CSIPAusSiteReadingUnit.FREQUENCY: UomType.FREQUENCY_HZ,
            CSIPAusSiteReadingUnit.VOLTAGE: UomType.VOLTAGE,
        }
        return uom_map[csip_unit]  # Raises KeyError if invalid unit
