from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.pricing import insert_single_tariff, update_single_tariff
from envoy.admin.schema.pricing import TariffGeneratedRateRequest, TariffRequest
from envoy.server.model.tariff import Tariff, TariffGeneratedRate
from envoy.server.crud.pricing import select_single_tariff, select_all_tariffs
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

    @staticmethod
    async def fetch_tariff(session: AsyncSession, tariff_id: int):
        """TODO"""
        tariff = await select_single_tariff(session, tariff_id)
        return TariffMapper.map_to_response(tariff)


class TariffListManager:
    @staticmethod
    async def fetch_many_tariffs(session: AsyncSession, start: int, limit: int):
        tariff_list = await select_all_tariffs(session, start, datetime.min, limit)
        return [TariffMapper.map_to_response(t) for t in tariff_list]


# class TariffGeneratedRateManager:
#     @staticmethod
#     async def add_or_update_tariff(session: AsyncSession, tariff_genrate: TariffGeneratedRateRequest) -> bool:
#         """TODO"""

#         return await upsert_single_return_primkey(
#             session, TariffGeneratedRate, tariff_genrate, "tariff_generated_rate_id"
#         )
