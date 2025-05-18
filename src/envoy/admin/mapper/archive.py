from datetime import datetime
from decimal import Decimal
from typing import Sequence

from envoy_schema.admin.schema.archive import (
    ArchiveDynamicOperatingEnvelopeResponse,
    ArchivePageResponse,
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
            groups=[],
            der_config=None,
            der_availability=None,
            der_status=None,
        )

    @staticmethod
    def map_to_doe_response(doe: ArchiveDynamicOperatingEnvelope) -> ArchiveDynamicOperatingEnvelopeResponse:
        archive_time = doe.archive_time
        if archive_time is None:
            archive_time = utc_now()  # Should never happen - the default in the DB will set this

        return ArchiveDynamicOperatingEnvelopeResponse(
            archive_id=doe.archive_id,
            archive_time=archive_time,
            deleted_time=doe.deleted_time,
            dynamic_operating_envelope_id=doe.dynamic_operating_envelope_id,
            site_id=doe.site_id,
            calculation_log_id=doe.calculation_log_id,
            duration_seconds=doe.duration_seconds,
            import_limit_active_watts=(
                doe.import_limit_active_watts if doe.import_limit_active_watts is not None else Decimal(0)
            ),
            export_limit_watts=doe.export_limit_watts if doe.export_limit_watts is not None else Decimal(0),
            start_time=doe.start_time,
            changed_time=doe.changed_time,
            created_time=doe.created_time,
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
            site_id=rate.site_id,
            calculation_log_id=rate.calculation_log_id,
            tariff_generated_rate_id=rate.tariff_generated_rate_id,
            start_time=rate.start_time,
            duration_seconds=rate.duration_seconds,
            import_active_price=rate.import_active_price,
            export_active_price=rate.export_active_price,
            import_reactive_price=rate.import_reactive_price,
            export_reactive_price=rate.export_reactive_price,
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
    ) -> ArchivePageResponse[ArchiveDynamicOperatingEnvelopeResponse]:
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
