from datetime import datetime
from typing import Iterable, List, Optional, Sequence

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.archive import copy_rows_into_archive, delete_rows_into_archive
from envoy.server.model.archive.tariff import ArchiveTariff, ArchiveTariffComponent, ArchiveTariffGeneratedRate
from envoy.server.model.tariff import Tariff, TariffComponent, TariffGeneratedRate


async def insert_single_tariff(session: AsyncSession, tariff: Tariff) -> None:
    """Inserts a single tariff entry into the DB. Returns None"""
    if tariff.created_time:
        del tariff.created_time
    session.add(tariff)


async def update_single_tariff(session: AsyncSession, updated_tariff: Tariff, changed_time: datetime) -> None:
    """Updates a single existing tariff entry in the DB. The old version will be archived"""

    await copy_rows_into_archive(
        session, Tariff, ArchiveTariff, lambda q: q.where(Tariff.tariff_id == updated_tariff.tariff_id)
    )

    resp = await session.execute(select(Tariff).where(Tariff.tariff_id == updated_tariff.tariff_id))
    tariff = resp.scalar_one()

    tariff.dnsp_code = updated_tariff.dnsp_code
    tariff.name = updated_tariff.name
    tariff.currency_code = updated_tariff.currency_code
    tariff.fsa_id = updated_tariff.fsa_id
    tariff.primacy = updated_tariff.primacy
    tariff.price_power_of_ten_multiplier = updated_tariff.price_power_of_ten_multiplier
    tariff.changed_time = changed_time

    if tariff.version is None:
        tariff.version = 1
    else:
        tariff.version = tariff.version + 1


async def update_single_tariff_component(
    session: AsyncSession, updated_tc: TariffComponent, changed_time: datetime
) -> None:
    """Updates a single existing tariff component entry in the DB. The old version will be archived.

    Primary key / tariff ID will NOT be updated"""

    await copy_rows_into_archive(
        session,
        TariffComponent,
        ArchiveTariffComponent,
        lambda q: q.where(TariffComponent.tariff_component_id == updated_tc.tariff_component_id),
    )

    resp = await session.execute(
        select(TariffComponent).where(TariffComponent.tariff_component_id == updated_tc.tariff_component_id)
    )
    tc = resp.scalar_one()

    tc.description = updated_tc.description
    tc.role_flags = updated_tc.role_flags
    tc.accumulation_behaviour = updated_tc.accumulation_behaviour
    tc.commodity = updated_tc.commodity
    tc.data_qualifier = updated_tc.data_qualifier
    tc.flow_direction = updated_tc.flow_direction
    tc.kind = updated_tc.kind
    tc.phase = updated_tc.phase
    tc.power_of_ten_multiplier = updated_tc.power_of_ten_multiplier
    tc.uom = updated_tc.uom
    tc.changed_time = changed_time

    if tc.version is None:
        tc.version = 1
    else:
        tc.version = tc.version + 1


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


async def select_single_tariff_generated_rate(
    session: AsyncSession, tariff_generated_rate_id: int
) -> Optional[TariffGeneratedRate]:
    """Admin lookup of a single TariffGeneratedRate by ID - no scoping for aggregators"""
    resp = await session.execute(
        select(TariffGeneratedRate).where(TariffGeneratedRate.tariff_generated_rate_id == tariff_generated_rate_id)
    )
    return resp.scalar_one_or_none()


async def cancel_and_delete_tariff_component(
    session: AsyncSession, tariff_component_id: int, deleted_time: datetime
) -> None:
    """Deletes the specified TariffComponent and ALL descendent TariffGeneratedRate into the archive and
    marks them all with the specified deleted_time

    If the record DNE - this will have no effect."""
    await delete_rows_into_archive(
        session,
        TariffGeneratedRate,
        ArchiveTariffGeneratedRate,
        deleted_time,
        lambda q: q.where(TariffGeneratedRate.tariff_component_id == tariff_component_id),
    )

    await delete_rows_into_archive(
        session,
        TariffComponent,
        ArchiveTariffComponent,
        deleted_time,
        lambda q: q.where(TariffComponent.tariff_component_id == tariff_component_id),
    )


async def cancel_tariff_generated_rate(
    session: AsyncSession, tariff_generated_rate_id: int, deleted_time: datetime
) -> None:
    """Deletes the specified TariffGeneratedRate into the archive and marks it with the specified deleted_time

    If the record DNE - this will have no effect."""
    await delete_rows_into_archive(
        session,
        TariffGeneratedRate,
        ArchiveTariffGeneratedRate,
        deleted_time,
        lambda q: q.where(TariffGeneratedRate.tariff_generated_rate_id == tariff_generated_rate_id),
    )
