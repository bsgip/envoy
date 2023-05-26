from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.pricing import insert_single_tariff, update_single_tariff
from envoy.admin.schema.pricing import TariffGeneratedRateRequest, TariffRequest
from envoy.server.model.tariff import Tariff, TariffGeneratedRate
from envoy.admin.mapper.pricing import TariffMapper


class TariffManager:
    @staticmethod
    async def add_new_tariff(session: AsyncSession, tariff: TariffRequest) -> int:
        """TODO"""

        await insert_single_tariff(session, TariffMapper.map_from_request(tariff))
        await session.commit()
        return tariff.tariff_id

    @staticmethod
    async def update_existing_tariff(session: AsyncSession, tariff: TariffRequest) -> int:
        """TODO"""

        await update_single_tariff(session, TariffMapper.map_from_request(tariff))
        await session.commit()
        return tariff.tariff_id


# class TariffGeneratedRateManager:
#     @staticmethod
#     async def add_or_update_tariff(session: AsyncSession, tariff_genrate: TariffGeneratedRateRequest) -> bool:
#         """TODO"""

#         return await upsert_single_return_primkey(
#             session, TariffGeneratedRate, tariff_genrate, "tariff_generated_rate_id"
#         )
