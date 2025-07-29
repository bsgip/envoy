from datetime import datetime, timezone
from typing import Callable, Optional, Sequence, cast

from intervaltree import Interval, IntervalTree  # type: ignore
from sqlalchemy import Delete, and_, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.archive import copy_rows_into_archive, delete_rows_into_archive
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.doe import DynamicOperatingEnvelope, SiteControlGroup


async def delete_does_with_start_time_in_range(
    session: AsyncSession,
    site_control_group_id: int,
    site_id: Optional[int],
    period_start: datetime,
    period_end: datetime,
    deleted_time: datetime,
) -> None:
    """Deletes (with archive) all does whose **start_time** is in the range period_start to period_end. Does not perform
    any checks for aggregator_id scoping

    site_control_group_id: Only this site control group's controls will be considered
    site_id: if specified - scope the deletion to just controls for this site
    period_start: inclusive start of range to search
    period_end: exclusive end of range to search"""

    query: Callable[[Delete], Delete]
    if site_id is None:
        query = lambda q: q.where(  # noqa: E731
            (DynamicOperatingEnvelope.site_control_group_id == site_control_group_id)
            & (DynamicOperatingEnvelope.start_time >= period_start)
            & (DynamicOperatingEnvelope.start_time < period_end)
        )
    else:
        query = lambda q: q.where(  # noqa: E731
            (DynamicOperatingEnvelope.site_control_group_id == site_control_group_id)
            & (DynamicOperatingEnvelope.site_id == site_id)
            & (DynamicOperatingEnvelope.start_time >= period_start)
            & (DynamicOperatingEnvelope.start_time < period_end)
        )

    # Perform the archival delete
    await delete_rows_into_archive(
        session, DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope, deleted_time, query
    )


async def cancel_then_insert_does(
    session: AsyncSession, doe_list: list[DynamicOperatingEnvelope], deleted_time: datetime
) -> None:
    """Adds a multiple DynamicOperatingEnvelope into the db. If any DOE conflict on site/start time, those
    conflicts will first be archived and then the new DOE values will take their place.

    This will have the effect of "cancelling" the conflicting controls and creating a new control"""

    # Start by deleting all conflicts (archiving them as we go)
    where_clause_and_elements = (
        and_(
            DynamicOperatingEnvelope.site_id == doe.site_id,
            DynamicOperatingEnvelope.start_time == doe.start_time,
        )
        for doe in doe_list
    )
    or_clause = or_(*where_clause_and_elements)
    await delete_rows_into_archive(
        session, DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope, deleted_time, lambda q: q.where(or_clause)
    )

    # Now we can do the inserts
    table = DynamicOperatingEnvelope.__table__
    update_cols = [c.name for c in table.c if c not in list(table.primary_key.columns) and not c.server_default]  # type: ignore [attr-defined] # noqa: E501
    await session.execute(
        insert(DynamicOperatingEnvelope).values(([{k: getattr(doe, k) for k in update_cols} for doe in doe_list]))
    )


async def supersede_then_insert_does(
    session: AsyncSession, doe_list: list[DynamicOperatingEnvelope], changed_time: datetime
) -> None:
    """Inserts the specified list of doe's. Any existing doe in the database will have their superseded flag updated
    if they overlap in time (taking into account primacy / creation time)

    Will generate archive records for updated controls"""

    if len(doe_list) == 0:
        return

    # start by caching all primacy values from the parent SiteControlGroup's
    primacy_by_group_id = dict(
        (await session.execute(select(SiteControlGroup.site_control_group_id, SiteControlGroup.primacy))).tuples().all()
    )

    # Organise the incoming DOE's by site_id to better chunk the lookups (and utilise existing indexes)
    does_by_site_id: dict[int, list[DynamicOperatingEnvelope]] = {}
    for doe in doe_list:
        existing = does_by_site_id.get(doe.site_id, None)
        if existing is None:
            does_by_site_id[doe.site_id] = [doe]
        else:
            existing.append(doe)

    # Start making the requests to the database to update the existing DOEs as superseded
    for site_id, site_doe_list in does_by_site_id.items():
        await supersede_matching_does_for_site(session, site_doe_list, site_id, primacy_by_group_id, changed_time)

    # Now we can do the inserts
    table = DynamicOperatingEnvelope.__table__
    update_cols = [c.name for c in table.c if c not in list(table.primary_key.columns) and not c.server_default]  # type: ignore [attr-defined] # noqa: E501
    await session.execute(
        insert(DynamicOperatingEnvelope).values(([{k: getattr(doe, k) for k in update_cols} for doe in doe_list]))
    )


async def supersede_matching_does_for_site(
    session: AsyncSession,
    doe_list: list[DynamicOperatingEnvelope],
    site_id: int,
    primacy_by_group_id: dict[int, int],
    changed_time: datetime,
) -> None:
    """Marks existing DynamicOperatingEnvelopes in the db as superseded If they are overlapped by any value in doe_list
    (and the overlapping control has a equal/higher priority). Partial overlaps will still be treated as superseding
    as per 2030.5 event rules and guidelines.

    doe_list: Should ONLY contain sites with the specified site_id
    site_id: The site_id that this request will be scoped to
    primacy_by_group_id: Cache of primacy values for every SiteControlGroup's ID
    changed_time: Will be applied to all existing DOE's that are updated

    This will appropriately archive all updated records

    This will NOT insert doe_list to the database"""

    if len(doe_list) == 0:
        return

    # Figure out the date range of the incoming controls so we can narrow our search space
    min_date = datetime.max.replace(tzinfo=timezone.utc)
    max_date = datetime.min.replace(tzinfo=timezone.utc)
    for control in doe_list:
        if control.start_time < min_date:
            min_date = control.start_time
        if control.end_time > max_date:
            max_date = control.end_time

    # Now go to the database to find existing controls that *might* overlap with the controls in doe_list
    # We deliberately avoid fetching the full models to avoid polluting the session with a ton of entities
    potential_matches = (
        (
            await session.execute(
                select(
                    DynamicOperatingEnvelope.dynamic_operating_envelope_id,
                    DynamicOperatingEnvelope.site_control_group_id,
                    DynamicOperatingEnvelope.start_time,
                    DynamicOperatingEnvelope.end_time,
                ).where(
                    # We include site_control_group to ensure we can utilise our indexes
                    (DynamicOperatingEnvelope.site_control_group_id.in_(primacy_by_group_id.keys()))
                    & (DynamicOperatingEnvelope.site_id == site_id)
                    & (DynamicOperatingEnvelope.end_time > min_date)
                    & (DynamicOperatingEnvelope.start_time < max_date)
                    & (DynamicOperatingEnvelope.superseded.is_(False))  # Can't supersede something twice
                )
            )
        )
        .tuples()
        .all()
    )

    # Build an efficient tree for quick lookups based on start/end time
    doe_list_tree = IntervalTree((Interval(doe.start_time, doe.end_time, doe) for doe in doe_list))

    # validate each potential match against the new controls - the aim is to find existing controls at the same/higher
    # primacy (i.e. candidates for superseding)
    superseded_doe_ids: list[int] = []
    for existing_doe_id, existing_site_control_id, existing_start_time, existing_end_time in potential_matches:
        existing_doe_primacy = primacy_by_group_id[existing_site_control_id]
        for interval in cast(set[Interval], doe_list_tree[existing_start_time:existing_end_time]):  # type: ignore
            incoming_doe: DynamicOperatingEnvelope = interval.data
            # At this point we know this incoming DOE intersects our existing_doe - next step is to work out whether
            # its at a lower/higher priority
            incoming_doe_primacy = primacy_by_group_id[incoming_doe.site_control_group_id]

            # Lower primacy means higher priority
            # Equal primacy means checking the creation time and we know incoming_doe is newer
            if incoming_doe_primacy <= existing_doe_primacy:
                superseded_doe_ids.append(existing_doe_id)
                break

    await copy_rows_into_archive(
        session,
        DynamicOperatingEnvelope,
        ArchiveDynamicOperatingEnvelope,
        lambda q: q.where(DynamicOperatingEnvelope.dynamic_operating_envelope_id.in_(superseded_doe_ids)),
    )

    await session.execute(
        update(DynamicOperatingEnvelope)
        .where(DynamicOperatingEnvelope.dynamic_operating_envelope_id.in_(superseded_doe_ids))
        .values(superseded=True, changed_time=changed_time)
    )


async def count_all_does(session: AsyncSession, site_control_group_id: int, changed_after: Optional[datetime]) -> int:
    """Admin counting of does - no filtering on aggregator is made. If changed_after is specified, only
    does that have their changed_time >= changed_after will be included"""
    stmt = (
        select(func.count())
        .select_from(DynamicOperatingEnvelope)
        .where(DynamicOperatingEnvelope.site_control_group_id == site_control_group_id)
    )

    if changed_after and changed_after != datetime.min:
        stmt = stmt.where(DynamicOperatingEnvelope.changed_time >= changed_after)

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_does(
    session: AsyncSession,
    site_control_group_id: int,
    start: int,
    limit: int,
    changed_after: Optional[datetime],
) -> Sequence[DynamicOperatingEnvelope]:
    """Admin selecting of does - no filtering on aggregator is made. Returns ordered by dynamic_operating_envelope_id

    changed_after is INCLUSIVE"""

    stmt = (
        select(DynamicOperatingEnvelope)
        .offset(start)
        .limit(limit)
        .where(DynamicOperatingEnvelope.site_control_group_id == site_control_group_id)
        .order_by(
            DynamicOperatingEnvelope.dynamic_operating_envelope_id.asc(),
        )
    )

    if changed_after and changed_after != datetime.min:
        stmt = stmt.where(DynamicOperatingEnvelope.changed_time >= changed_after)

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def count_all_site_control_groups(session: AsyncSession, changed_after: Optional[datetime]) -> int:
    """Admin counting of site control groups. If changed_after is specified, only groups that have their
    changed_time >= changed_after will be included"""
    stmt = select(func.count()).select_from(SiteControlGroup)

    if changed_after and changed_after != datetime.min:
        stmt = stmt.where(SiteControlGroup.changed_time >= changed_after)

    resp = await session.execute(stmt)
    return resp.scalar_one()


async def select_all_site_control_groups(
    session: AsyncSession,
    start: int,
    limit: int,
    changed_after: Optional[datetime],
) -> Sequence[SiteControlGroup]:
    """Admin selecting of site control groups - no filtering on aggregator is made. Returns ordered by
    site_control_group_id ASC

    changed_after is INCLUSIVE"""

    stmt = (
        select(SiteControlGroup)
        .offset(start)
        .limit(limit)
        .order_by(
            SiteControlGroup.site_control_group_id.asc(),
        )
    )

    if changed_after and changed_after != datetime.min:
        stmt = stmt.where(SiteControlGroup.changed_time >= changed_after)

    resp = await session.execute(stmt)
    return resp.scalars().all()
