from datetime import datetime
from typing import List

from sqlalchemy import and_, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.archive import copy_rows_into_archive, delete_rows_into_archive
from envoy.server.model.archive.tariff import ArchiveTariff, ArchiveTariffGeneratedRate
from envoy.server.model.tariff import Tariff, TariffGeneratedRate


async def insert_single_tariff(session: AsyncSession, tariff: Tariff) -> None:
    """Inserts a single tariff entry into the DB. Returns None"""
    if tariff.created_time:
        del tariff.created_time
    session.add(tariff)


async def update_single_tariff(session: AsyncSession, updated_tariff: Tariff) -> None:
    """Updates a single existing tariff entry in the DB. The old version will be archived"""

    await copy_rows_into_archive(
        session, Tariff, ArchiveTariff, lambda q: q.where(Tariff.tariff_id == updated_tariff.tariff_id)
    )

    resp = await session.execute(select(Tariff).where(Tariff.tariff_id == updated_tariff.tariff_id))
    tariff = resp.scalar_one()

    tariff.changed_time = updated_tariff.changed_time
    tariff.dnsp_code = updated_tariff.dnsp_code
    tariff.name = updated_tariff.name
    tariff.currency_code = updated_tariff.currency_code
    tariff.fsa_id = updated_tariff.fsa_id


async def upsert_many_tariff_genrate(
    session: AsyncSession, tariff_genrates: List[TariffGeneratedRate], deleted_time: datetime
) -> None:
    """Inserts multiple tariff generated rate entries into the DB. If any rates conflict on site/start_time, they
    will replace those values (with the old values being archived)"""

    # Start by deleting all conflicts (archiving them as we go)
    where_clause_and_elements = (
        and_(
            TariffGeneratedRate.tariff_id == r.tariff_id,
            TariffGeneratedRate.site_id == r.site_id,
            TariffGeneratedRate.start_time == r.start_time,
        )
        for r in tariff_genrates
    )
    or_clause = or_(*where_clause_and_elements)
    await delete_rows_into_archive(
        session, TariffGeneratedRate, ArchiveTariffGeneratedRate, deleted_time, lambda q: q.where(or_clause)
    )

    # Now we can do the inserts
    table = TariffGeneratedRate.__table__
    update_cols = [c.name for c in table.c if c not in list(table.primary_key.columns) and not c.server_default]  # type: ignore [attr-defined] # noqa: E501
    await session.execute(
        insert(TariffGeneratedRate).values(([{k: getattr(r, k) for k in update_cols} for r in tariff_genrates]))
    )
