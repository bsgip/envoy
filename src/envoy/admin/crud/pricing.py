from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from envoy.server.model.tariff import Tariff, TariffGeneratedRate


async def insert_single_tariff(session: AsyncSession, tariff: Tariff) -> None:
    """Inserts a single tariff entry into the DB. Returns None"""
    session.add(tariff)


async def update_single_tariff(session: AsyncSession, updated_tariff: Tariff) -> None:
    """Updates a single existing tariff entry in the DB."""
    resp = await session.execute(select(Tariff).where(Tariff.tariff_id == updated_tariff.tariff_id))
    tariff = resp.scalar_one()

    tariff.changed_time = updated_tariff.changed_time
    tariff.dnsp_code = updated_tariff.dnsp_code
    tariff.name = updated_tariff.name
    tariff.currency_code = updated_tariff.currency_code


async def insert_single_tariff_genrate(session: AsyncSession, tariff_genrate: TariffGeneratedRate) -> None:
    """Inserts a single tariff generated rate entry into the DB. Returns None"""
    session.add(tariff_genrate)


async def select_single_tariff_generate(
    session: AsyncSession, tariff_id: int, tariff_genrate_id: int
) -> TariffGeneratedRate:
    """Selects a single tariff generated rate entry using both tariff_id and tariff_generated_rate_id."""
    stmt = select(TariffGeneratedRate).where(
        (TariffGeneratedRate.tariff_id == tariff_id)
        & (TariffGeneratedRate.tariff_generated_rate_id == tariff_genrate_id)
    )

    resp = await session.execute(stmt)
    return resp.scalar_one()
