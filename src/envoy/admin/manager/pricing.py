from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.schema.pricing import TariffRequest


class TariffProfileManager:
    @staticmethod
    async def fetch_tariff_profile(
        session: AsyncSession, aggregator_id: int, tariff_id: int, site_id: int
    ) -> Optional[TariffProfileResponse]:
        """Fetches a single tariff in the form of a sep2 TariffProfile thats specific to a single site."""

        tariff = await select_single_tariff(session, tariff_id)
        if tariff is None:
            return None

        unique_rate_days = await count_unique_rate_days(session, aggregator_id, tariff_id, site_id, datetime.min)
        return TariffProfileMapper.map_to_response(tariff, site_id, unique_rate_days * TOTAL_PRICING_READING_TYPES)
