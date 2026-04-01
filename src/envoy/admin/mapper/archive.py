from datetime import datetime
from typing import Sequence

from envoy_schema.admin.schema.archive import (
    ArchivePageResponse,
    ArchiveSiteControlResponse,
    ArchiveSiteResponse,
    ArchiveTariffGeneratedRateResponse,
)

from envoy.server.manager.time import utc_now
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.archive.site import ArchiveSite
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate


class ArchiveMapper:
    @staticmethod
    def map_to_site_response(site: ArchiveSite) -> ArchiveSiteResponse:
        archive_time = site.archive_time
        if archive_time is None:
            archive_time = utc_now()  # Should never happen - the default in the DB will set this
        return ArchiveSiteResponse(
            archive_id=site.archive_id,
            archive_time=archive_time,
            deleted_time=site.deleted_time,
            site_id=site.site_id,
            nmi=site.nmi,
            aggregator_id=site.aggregator_id,
            timezone_id=site.timezone_id,
            created_time=site.created_time,
            changed_time=site.changed_time,
            lfdi=site.lfdi,
            sfdi=site.sfdi,
            device_category=site.device_category,
            post_rate_seconds=site.post_rate_seconds,
            groups=[],
            der_config=None,
            der_availability=None,
            der_status=None,
        )

    @staticmethod
    def map_to_doe_response(doe: ArchiveDynamicOperatingEnvelope) -> ArchiveSiteControlResponse:
        archive_time = doe.archive_time
        if archive_time is None:
            archive_time = utc_now()  # Should never happen - the default in the DB will set this

        return ArchiveSiteControlResponse(
            archive_id=doe.archive_id,
            archive_time=archive_time,
            deleted_time=doe.deleted_time,
            site_control_id=doe.dynamic_operating_envelope_id,
            site_id=doe.site_id,
            superseded=doe.superseded,
            calculation_log_id=doe.calculation_log_id,
            duration_seconds=doe.duration_seconds,
            import_limit_watts=doe.import_limit_active_watts,
            export_limit_watts=doe.export_limit_watts,
            generation_limit_watts=doe.generation_limit_active_watts,
            load_limit_watts=doe.load_limit_active_watts,
            set_point_percentage=doe.set_point_percentage,
            ramp_time_seconds=doe.ramp_time_seconds,
            start_time=doe.start_time,
            changed_time=doe.changed_time,
            created_time=doe.created_time,
            set_energized=doe.set_energized,
            set_connect=doe.set_connected,
            randomize_start_seconds=doe.randomize_start_seconds,
            storage_target_watts=None,
        )

    @staticmethod
    def map_to_rate_response(rate: ArchiveTariffGeneratedRate) -> ArchiveTariffGeneratedRateResponse:
        archive_time = rate.archive_time
        if archive_time is None:
            archive_time = utc_now()  # Should never happen - the default in the DB will set this

        return ArchiveTariffGeneratedRateResponse(
            archive_id=rate.archive_id,
            archive_time=archive_time,
            deleted_time=rate.deleted_time,
            tariff_id=rate.tariff_id,
            tariff_component_id=rate.tariff_component_id,
            site_id=rate.site_id,
            calculation_log_id=rate.calculation_log_id,
            tariff_generated_rate_id=rate.tariff_generated_rate_id,
            start_time=rate.start_time,
            duration_seconds=rate.duration_seconds,
            price_pow10_encoded=rate.price_pow10_encoded,
            block_1_start_pow10_encoded=rate.block_1_start_pow10_encoded,
            price_pow10_encoded_block_1=rate.price_pow10_encoded_block_1,
            changed_time=rate.changed_time,
            created_time=rate.created_time,
        )


class ArchiveListMapper:
    @staticmethod
    def map_to_sites_response(
        total_count: int,
        sites: Sequence[ArchiveSite],
        start: int,
        limit: int,
        period_start: datetime,
        period_end: datetime,
    ) -> ArchivePageResponse[ArchiveSiteResponse]:
        return ArchivePageResponse(
            start=start,
            limit=limit,
            total_count=total_count,
            period_start=period_start,
            period_end=period_end,
            entities=[ArchiveMapper.map_to_site_response(e) for e in sites],
        )

    @staticmethod
    def map_to_does_response(
        total_count: int,
        does: Sequence[ArchiveDynamicOperatingEnvelope],
        start: int,
        limit: int,
        period_start: datetime,
        period_end: datetime,
    ) -> ArchivePageResponse[ArchiveSiteControlResponse]:
        return ArchivePageResponse(
            start=start,
            limit=limit,
            total_count=total_count,
            period_start=period_start,
            period_end=period_end,
            entities=[ArchiveMapper.map_to_doe_response(e) for e in does],
        )

    @staticmethod
    def map_to_rates_response(
        total_count: int,
        rates: Sequence[ArchiveTariffGeneratedRate],
        start: int,
        limit: int,
        period_start: datetime,
        period_end: datetime,
    ) -> ArchivePageResponse[ArchiveTariffGeneratedRateResponse]:
        return ArchivePageResponse(
            start=start,
            limit=limit,
            total_count=total_count,
            period_start=period_start,
            period_end=period_end,
            entities=[ArchiveMapper.map_to_rate_response(e) for e in rates],
        )
