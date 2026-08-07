from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any, TypeVar

from sqlalchemy import Select, func, insert, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.archive import copy_rows_into_archive, delete_rows_into_archive
from envoy.server.model.archive.tariff import (
    ArchiveTariff,
    ArchiveTariffComponent,
    ArchiveTariffGeneratedRate,
)
from envoy.server.model.tariff import Tariff, TariffComponent, TariffGeneratedRate


async def insert_single_tariff(session: AsyncSession, tariff: Tariff) -> None:
    """Inserts a single tariff entry into the DB. Returns None"""
    if tariff.created_time:
        del tariff.created_time
    session.add(tariff)


async def update_single_tariff(session: AsyncSession, updated_tariff: Tariff, changed_time: datetime) -> None:
    """Updates a single existing tariff entry in the DB. The old version will be archived"""

    await copy_rows_into_archive(
        session,
        Tariff,
        ArchiveTariff,
        lambda q: q.where(Tariff.tariff_id == updated_tariff.tariff_id),
    )

    resp = await session.execute(select(Tariff).where(Tariff.tariff_id == updated_tariff.tariff_id))
    tariff = resp.scalar_one()

    tariff.dnsp_code = updated_tariff.dnsp_code
    tariff.name = updated_tariff.name
    tariff.currency_code = updated_tariff.currency_code
    tariff.required_site_group_id = updated_tariff.required_site_group_id
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
    session: AsyncSession, tariff_genrates: list[TariffGeneratedRate]
) -> Sequence[int]:
    """Inserts multiple tariff generated rate entries into the DB. There will be NO marking of superseded / updating
    of existing records as CSIP-Aus v1.3 requires all prices to overlap."""

    # Now we can do the inserts
    table = TariffGeneratedRate.__table__
    update_cols = [c.name for c in table.c if c not in list(table.primary_key.columns) and not c.server_default]  # ty:ignore[unresolved-attribute]
    insert_ids = await session.execute(
        insert(TariffGeneratedRate)
        .values([{k: getattr(r, k) for k in update_cols} for r in tariff_genrates])
        .returning(TariffGeneratedRate.tariff_generated_rate_id)
    )

    return insert_ids.scalars().all()


async def insert_many_tariff_genrate_ignore_collisions(
    session: AsyncSession, tariff_genrates: list[TariffGeneratedRate]
) -> list[int | None]:
    """Inserts multiple tariff generated rate entries into the DB. Any entry that collides with an existing record
    on the (tariff_component_id, start_time, site_group_id) unique constraint will be silently skipped (NOT
    inserted/updated).

    Returns a list of IDs that is the same length/order as tariff_genrates - each element being EITHER the newly
    inserted tariff_generated_rate_id OR COLLISION_ID_PLACEHOLDER if that entry collided with an existing record
    and was therefore skipped."""

    if not tariff_genrates:
        return []

    table = TariffGeneratedRate.__table__
    insert_cols = [c.name for c in table.c if c not in list(table.primary_key.columns) and not c.server_default]  # ty:ignore[unresolved-attribute]

    stmt = (
        pg_insert(TariffGeneratedRate)
        .values([{k: getattr(r, k) for k in insert_cols} for r in tariff_genrates])
        .on_conflict_do_nothing(index_elements=["tariff_component_id", "start_time", "site_group_id"])
        .returning(
            TariffGeneratedRate.tariff_generated_rate_id,
            TariffGeneratedRate.tariff_component_id,
            TariffGeneratedRate.start_time,
            TariffGeneratedRate.site_group_id,
        )
    )
    inserted_rows = (await session.execute(stmt)).all()

    # Rows that collided simply won't appear in inserted_rows - we match returned rows back to their originating
    # request (by natural key) to preserve the 1-1 correspondence expected by the caller.
    ids_by_key: dict[tuple[int, datetime, int], list[int]] = defaultdict(list)
    for rate_id, tariff_component_id, start_time, site_group_id in inserted_rows:
        ids_by_key[(tariff_component_id, start_time, site_group_id)].append(rate_id)

    result: list[int | None] = []
    for r in tariff_genrates:
        candidate_ids = ids_by_key.get((r.tariff_component_id, r.start_time, r.site_group_id))
        if candidate_ids:
            result.append(candidate_ids.pop(0))
        else:
            result.append(None)

    return result


async def cancel_colliding_tariff_generated_rates(
    session: AsyncSession, tariff_genrates: Iterable[TariffGeneratedRate], deleted_time: datetime
) -> None:
    """Finds any existing TariffGeneratedRate that collides (on the (tariff_component_id, start_time, site_group_id)
    unique constraint) with any of the specified tariff_genrates and cancels (deletes/archives) it with the
    specified deleted_time.

    If no rows collide - this will have no effect."""

    keys = [(r.tariff_component_id, r.start_time, r.site_group_id) for r in tariff_genrates]
    if not keys:
        return

    await delete_rows_into_archive(
        session,
        TariffGeneratedRate,
        ArchiveTariffGeneratedRate,
        deleted_time,
        lambda q: q.where(
            tuple_(
                TariffGeneratedRate.tariff_component_id,
                TariffGeneratedRate.start_time,
                TariffGeneratedRate.site_group_id,
            ).in_(keys)
        ),
    )


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
) -> TariffGeneratedRate | None:
    """Admin lookup of a single TariffGeneratedRate by ID - no scoping for aggregators"""
    resp = await session.execute(
        select(TariffGeneratedRate).where(TariffGeneratedRate.tariff_generated_rate_id == tariff_generated_rate_id)
    )
    return resp.scalar_one_or_none()


T = TypeVar("T", bound=tuple[Any, ...])


def _filtered_tariff_generated_rates(
    stmt: Select[T],
    tariff_component_id: int,
    start_time_since: datetime | None,
    start_time_until: datetime | None,
    site_group_ids: set[int] | None,
) -> Select[T]:

    stmt = stmt.where(TariffGeneratedRate.tariff_component_id == tariff_component_id)
    if start_time_since is not None:
        stmt = stmt.where(TariffGeneratedRate.start_time >= start_time_since)
    if start_time_until is not None:
        stmt = stmt.where(TariffGeneratedRate.start_time < start_time_until)
    if site_group_ids is not None:
        stmt = stmt.where(TariffGeneratedRate.site_group_id.in_(site_group_ids))
    return stmt


async def select_filtered_tariff_generated_rates(
    session: AsyncSession,
    tariff_component_id: int,
    start_time_since: datetime | None,
    start_time_until: datetime | None,
    site_group_ids: set[int] | None,
    start: int,
    limit: int,
) -> Sequence[TariffGeneratedRate]:
    """Fetches TariffGeneratedRate that meet the specified criteria"""

    stmt = select(TariffGeneratedRate).order_by(TariffGeneratedRate.tariff_generated_rate_id).limit(limit).offset(start)
    stmt = _filtered_tariff_generated_rates(
        stmt,
        tariff_component_id=tariff_component_id,
        start_time_since=start_time_since,
        start_time_until=start_time_until,
        site_group_ids=site_group_ids,
    )
    return (await session.execute(stmt)).scalars().all()


async def count_filtered_tariff_generated_rates(
    session: AsyncSession,
    tariff_component_id: int,
    start_time_since: datetime | None,
    start_time_until: datetime | None,
    site_group_ids: set[int] | None,
) -> int:
    """Provides the count of records returned from select_filtered_tariff_generated_rates"""

    stmt = select(func.count()).select_from(TariffGeneratedRate)
    stmt = _filtered_tariff_generated_rates(
        stmt,
        tariff_component_id=tariff_component_id,
        start_time_since=start_time_since,
        start_time_until=start_time_until,
        site_group_ids=site_group_ids,
    )
    return (await session.execute(stmt)).scalar_one()


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


async def select_tariff_components_for_tariff(
    session: AsyncSession,
    tariff_id: int,
) -> Sequence[TariffComponent]:
    """Select all TariffComponents belonging to a Tariff, ordered by tariff_component_id for stability."""
    result = await session.execute(
        select(TariffComponent)
        .where(TariffComponent.tariff_id == tariff_id)
        .order_by(TariffComponent.tariff_component_id.asc())
    )
    return result.scalars().all()
