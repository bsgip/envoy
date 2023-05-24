from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.schema.pricing import TariffRequest, TariffGeneratedRateRequest
from envoy.server.model.tariff import Tariff, TariffGeneratedRate
from envoy.admin.crud.generic import upsert_single_return_primkey


class TariffManager:
    @staticmethod
    async def add_or_update_tariff(session: AsyncSession, tariff: TariffRequest) -> bool:
        """TODO"""

        return await upsert_single_return_primkey(session, Tariff, tariff, "tariff_id")


class TariffGeneratedRateManager:
    @staticmethod
    async def add_or_update_tariff(session: AsyncSession, tariff_genrate: TariffGeneratedRateRequest) -> bool:
        """TODO"""

        return await upsert_single_return_primkey(
            session, TariffGeneratedRate, tariff_genrate, "tariff_generated_rate_id"
        )
