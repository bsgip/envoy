""" Managers for pricing/tariff endpoints
"""
from datetime import datetime
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import NoResultFound

from envoy.admin.crud.pricing import insert_single_tariff, update_single_tariff, upsert_many_tariff_genrate
from envoy.admin.schema.pricing import (
    TariffRequest,
    TariffResponse,
    TariffGeneratedRateRequest,
)
from envoy.server.crud.pricing import select_single_tariff, select_all_tariffs
from envoy.admin.mapper.pricing import TariffMapper, TariffGeneratedRateListMapper


class TariffManager:
    @staticmethod
    async def add_new_tariff(session: AsyncSession, tariff: TariffRequest) -> int:
        """Map a TariffRequest object to a Tariff model and insert into DB. Return the tariff_id only."""

        tariff_model = TariffMapper.map_from_request(tariff)
        await insert_single_tariff(session, tariff_model)
        await session.commit()
        return tariff_model.tariff_id

    @staticmethod
    async def update_existing_tariff(
        session: AsyncSession,
        tariff_id: int,
        tariff: TariffRequest,
    ) -> None:
        """Map a TariffRequest object to a Tariff model and update DB entry."""
        tariff_model = TariffMapper.map_from_request(tariff)
        tariff_model.tariff_id = tariff_id
        await update_single_tariff(session, tariff_model)
        await session.commit()

    @staticmethod
    async def fetch_tariff(session: AsyncSession, tariff_id: int) -> TariffResponse:
        """Select a singular tariff entry from the DB and map to a TariffResponse object."""
        tariff = await select_single_tariff(session, tariff_id)
        if tariff is None:
            raise NoResultFound
        return TariffMapper.map_to_response(tariff)


class TariffListManager:
    @staticmethod
    async def fetch_many_tariffs(session: AsyncSession, start: int, limit: int):
        """Select many tariff entries from the DB and map to a list of TariffResponse objects"""
        tariff_list = await select_all_tariffs(session, start, datetime.min, limit)
        return [TariffMapper.map_to_response(t) for t in tariff_list]


class TariffGeneratedRateListManager:
    @staticmethod
    async def add_many_tariff_genrate(session: AsyncSession, tariff_genrates: List[TariffGeneratedRateRequest]) -> None:
        """Map a TariffGeneratedRateRequest object to a TariffGeneratedRate model and insert into DB.
        Return the tariff_generated_rate_id only."""
        tariff_genrate_models = TariffGeneratedRateListMapper.map_from_request(tariff_genrates)
        await upsert_many_tariff_genrate(session, tariff_genrate_models)
        await session.commit()
