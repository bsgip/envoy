from datetime import datetime
from typing import Iterable, List, Sequence

from sqlalchemy import and_, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.archive import copy_rows_into_archive, delete_rows_into_archive
from envoy.server.model.archive.tariff import ArchiveTariff, ArchiveTariffGeneratedRate
from envoy.server.model.tariff import Tariff, TariffComponent, TariffGeneratedRate


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


async def insert_many_tariff_genrate(
    session: AsyncSession, tariff_genrates: List[TariffGeneratedRate]
) -> Sequence[int]:
    """Inserts multiple tariff generated rate entries into the DB. There will be NO marking of superseded / updating
    of existing records as CSIP-Aus v1.3 requires all prices to overlap."""

    # Now we can do the inserts
    table = TariffGeneratedRate.__table__
    update_cols = [c.name for c in table.c if c not in list(table.primary_key.columns) and not c.server_default]  # type: ignore [attr-defined] # noqa: E501
    insert_ids = await session.execute(
        insert(TariffGeneratedRate)
        .values(([{k: getattr(r, k) for k in update_cols} for r in tariff_genrates]))
        .returning(TariffGeneratedRate.tariff_generated_rate_id)
    )

    return insert_ids.scalars().all()


async def select_tariff_ids_for_component_ids(
    session: AsyncSession, tariff_component_ids: Iterable[int]
) -> dict[int, int]:
    """Given a set of TariffComponent.tariff_component_id values - return a dictionary keyed by those ids whose value
    is the associated Tariff.tariff_id on the record.
    """
    resp = await session.execute(
        select(TariffComponent.tariff_component_id, TariffComponent.tariff_id).where(
            TariffComponent.tariff_component_id.in_(tariff_component_ids)
        )
    )
    return dict(resp.tuples().all())
