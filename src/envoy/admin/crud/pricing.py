from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as psql_insert

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


async def upsert_many_tariff_genrate(session: AsyncSession, tariff_generates: List[TariffGeneratedRate]) -> None:
    """Inserts multiple tariff generated rate entries into the DB. Returns None"""

    table = TariffGeneratedRate.__table__
    update_cols = [c.name for c in table.c if c not in list(table.primary_key.columns)]  # type: ignore [attr-defined]
    stmt = psql_insert(TariffGeneratedRate).values(
        [{k: getattr(tr, k) for k in update_cols} for tr in tariff_generates]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[TariffGeneratedRate.site_id, TariffGeneratedRate.tariff_id, TariffGeneratedRate.start_time],
        set_={k: getattr(stmt.excluded, k) for k in update_cols},
    )

    await session.execute(stmt)
