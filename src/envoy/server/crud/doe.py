from datetime import datetime
from typing import Optional, Sequence, Union

from sqlalchemy import Select, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.common import localize_start_time, localize_start_time_for_entity
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope as ArchiveDOE
from envoy.server.model.doe import DynamicOperatingEnvelope as DOE
from envoy.server.model.doe import SiteControlGroup
from envoy.server.model.site import Site


async def select_doe_include_deleted(
    session: AsyncSession,
    aggregator_id: int,
    site_id: int,
    doe_id: int,
) -> Optional[Union[DOE, ArchiveDOE]]:
    """Attempts to fetch a doe using its' DOE id, also scoping it to a particular aggregator/site. The archive
    table will also be checked for deleted instances (of which the most recent deletion will be matched).

    site_control_group_id: The SiteControlGroup to select doe's from
    aggregator_id: The aggregator id to constrain the lookup to
    site_id: the query will apply a filter on site_id using this value"""

    # Start by confirming the referenced site_id exists within the specified aggregator.
    site_timezone_id = (
        await session.execute(
            select(Site.timezone_id).where((Site.site_id == site_id) & (Site.aggregator_id == aggregator_id))
        )
    ).scalar_one_or_none()
    if not site_timezone_id:
        return None

    # Check primary table first
    primary_table_doe = (
        await session.execute(
            select(DOE).where((DOE.dynamic_operating_envelope_id == doe_id) & (DOE.site_id == site_id))
        )
    ).scalar_one_or_none()
    if primary_table_doe is not None:
        return localize_start_time_for_entity(primary_table_doe, site_timezone_id)

    # Check archive otherwise
    archive_table_doe = (
        await session.execute(
            (
                select(ArchiveDOE)
                .where((ArchiveDOE.dynamic_operating_envelope_id == doe_id) & (ArchiveDOE.deleted_time.is_not(None)))
                .order_by(ArchiveDOE.deleted_time.desc())
            )
        )
    ).scalar_one_or_none()
    if archive_table_doe is not None:
        return localize_start_time_for_entity(archive_table_doe, site_timezone_id)

    return None


async def _does_at_timestamp(
    is_counting: bool,
    session: AsyncSession,
    site_control_group_id: int,
    aggregator_id: int,
    site_id: Optional[int],
    timestamp: datetime,
    start: int,
    changed_after: datetime,
    limit: Optional[int],
) -> Union[Sequence[DOE], int]:
    """Internal utility for fetching doe's that are active for the specific timestamp

    aggregator_id: The aggregator to scope all DOEs to
    site_control_group_id: The SiteControlGroup to select doe's from
    site_id: If None - no site_id filter applied, otherwise filter on site_id = Value

    Orders by 2030.5 requirements on DERControl which is start ASC, creation DESC, id DESC"""

    select_clause: Union[Select[tuple[int]], Select[tuple[DOE, str]]]
    if is_counting:
        select_clause = select(func.count()).select_from(DOE)
    else:
        select_clause = select(DOE, Site.timezone_id)

    stmt = (
        select_clause.join(DOE.site)
        .where(
            (DOE.site_control_group_id == site_control_group_id)
            & (DOE.end_time > timestamp)
            & (DOE.start_time <= timestamp)
            & (Site.aggregator_id == aggregator_id)
        )
        .offset(start)
        .limit(limit)
    )

    if changed_after != datetime.min:
        stmt = stmt.where((DOE.changed_time >= changed_after))

    if site_id is not None:
        stmt = stmt.where(DOE.site_id == site_id)

    if not is_counting:
        stmt = stmt.order_by(DOE.start_time.asc(), DOE.changed_time.desc(), DOE.dynamic_operating_envelope_id.desc())

    resp = await session.execute(stmt)
    if is_counting:
        return resp.scalar_one()
    else:
        return [localize_start_time(doe_and_tz) for doe_and_tz in resp.all()]


async def count_active_does_include_deleted(
    session: AsyncSession,
    site_control_group_id: int,
    site: Site,
    now: datetime,
    changed_after: datetime,
) -> int:
    """Provides the count of records returned from select_active_does_include_deleted (assuming no pagination).

    site_control_group_id: The SiteControlGroup to select doe's from
    site: The site that the counted DOE's will be all be scoped from
    now: The timestamp that excludes any DOE whose end_time precedes this (i.e. they are expired and no longer relevant)
    changed_after: Only DOE's modified after this time will be counted."""

    count_active_does_stmt = (
        select(func.count())
        .select_from(DOE)
        .where(
            (DOE.site_control_group_id == site_control_group_id) & (DOE.end_time > now) & (DOE.site_id == site.site_id)
        )
    )
    count_archive_does_stmt = (
        select(func.count())
        .select_from(ArchiveDOE)
        .where(
            (ArchiveDOE.site_control_group_id == site_control_group_id)
            & (ArchiveDOE.end_time > now)
            & (ArchiveDOE.site_id == site.site_id)
            & (ArchiveDOE.deleted_time.is_not(None))
        )
    )

    if changed_after != datetime.min:
        # The "changed_time" for archives is actually the "deleted_time"
        count_active_does_stmt = count_active_does_stmt.where(DOE.changed_time >= changed_after)
        count_archive_does_stmt = count_archive_does_stmt.where(ArchiveDOE.deleted_time >= changed_after)

    count_active = (await session.execute(count_active_does_stmt)).scalar_one()
    count_archive = (await session.execute(count_archive_does_stmt)).scalar_one()

    return count_active + count_archive


async def select_active_does_include_deleted(
    session: AsyncSession,
    site_control_group_id: int,
    site: Site,
    now: datetime,
    start: int,
    changed_after: datetime,
    limit: Optional[int],
) -> list[Union[DOE, ArchiveDOE]]:
    """Fetches DOEs from dynamic_operating_envelope AND its archive according to the specified filter criteria. Only
    DOE's whose end_time is after "now" will be returned.

    site_control_group_id: The SiteControlGroup to select doe's from
    site: Only DOEs from this site will be included
    now: The timestamp that excludes any DOE whose end_time precedes this (i.e. they are expired and no longer relevant)
    start: How many DOEs to skip
    limit: Max number of DOEs to return
    changed_after: Only DOE's modified after this time will be included.

    Orders by 2030.5 requirements on DERControl which is start ASC, creation DESC, id DESC"""

    select_active_does = select(
        DOE.dynamic_operating_envelope_id,
        DOE.site_control_group_id,
        DOE.site_id,
        DOE.calculation_log_id,
        DOE.created_time,
        DOE.changed_time,
        DOE.end_time,
        DOE.start_time,
        DOE.duration_seconds,
        DOE.randomize_start_seconds,
        DOE.import_limit_active_watts,
        DOE.export_limit_watts,
        DOE.generation_limit_active_watts,
        DOE.load_limit_active_watts,
        DOE.set_energized,
        DOE.set_connected,
        literal_column("NULL").label("archive_id"),
        literal_column("NULL").label("archive_time"),
        literal_column("NULL").label("deleted_time"),
        literal_column("0").label("is_archive"),
    ).where((DOE.site_control_group_id == site_control_group_id) & (DOE.end_time > now) & (DOE.site_id == site.site_id))

    select_archive_does = select(
        ArchiveDOE.dynamic_operating_envelope_id,
        ArchiveDOE.site_control_group_id,
        ArchiveDOE.site_id,
        ArchiveDOE.calculation_log_id,
        ArchiveDOE.created_time,
        ArchiveDOE.deleted_time.label(ArchiveDOE.changed_time.name),  # Changed time will be using "deleted_time"
        ArchiveDOE.end_time,
        ArchiveDOE.start_time,
        ArchiveDOE.duration_seconds,
        ArchiveDOE.randomize_start_seconds,
        ArchiveDOE.import_limit_active_watts,
        ArchiveDOE.export_limit_watts,
        ArchiveDOE.generation_limit_active_watts,
        ArchiveDOE.load_limit_active_watts,
        ArchiveDOE.set_energized,
        ArchiveDOE.set_connected,
        ArchiveDOE.archive_id,
        ArchiveDOE.archive_time,
        ArchiveDOE.deleted_time,
        literal_column("1").label("is_archive"),
    ).where(
        (ArchiveDOE.site_control_group_id == site_control_group_id)
        & (ArchiveDOE.end_time > now)
        & (ArchiveDOE.site_id == site.site_id)
        & (ArchiveDOE.deleted_time.is_not(None))
    )

    if changed_after != datetime.min:
        # The "changed_time" for archives is actually the "deleted_time"
        select_active_does = select_active_does.where(DOE.changed_time >= changed_after)
        select_archive_does = select_archive_does.where(ArchiveDOE.deleted_time >= changed_after)

    stmt = (
        select_active_does.union_all(select_archive_does)
        .limit(limit)
        .offset(start)
        .order_by(DOE.start_time.asc(), DOE.changed_time.desc(), DOE.dynamic_operating_envelope_id.desc())
    )

    resp = await session.execute(stmt)

    # This is (annoyingly) the only real way to take the UNION ALL query and return multiple element types
    # We use the literal "is_archive" from our query to differentiate archive from normal rows
    return [
        (
            localize_start_time_for_entity(
                ArchiveDOE(
                    dynamic_operating_envelope_id=t.dynamic_operating_envelope_id,
                    site_control_group_id=t.site_control_group_id,
                    site_id=t.site_id,
                    calculation_log_id=t.calculation_log_id,
                    created_time=t.created_time,
                    changed_time=t.changed_time,
                    start_time=t.start_time,
                    duration_seconds=t.duration_seconds,
                    end_time=t.end_time,
                    randomize_start_seconds=t.randomize_start_seconds,
                    import_limit_active_watts=t.import_limit_active_watts,
                    export_limit_watts=t.export_limit_watts,
                    generation_limit_active_watts=t.generation_limit_active_watts,
                    load_limit_active_watts=t.load_limit_active_watts,
                    set_energized=t.set_energized,
                    set_connected=t.set_connected,
                    archive_id=t.archive_id,
                    archive_time=t.archive_time,
                    deleted_time=t.deleted_time,
                ),
                site.timezone_id,
            )
            if t.is_archive
            else localize_start_time_for_entity(
                DOE(
                    dynamic_operating_envelope_id=t.dynamic_operating_envelope_id,
                    site_control_group_id=t.site_control_group_id,
                    site_id=t.site_id,
                    calculation_log_id=t.calculation_log_id,
                    created_time=t.created_time,
                    changed_time=t.changed_time,
                    start_time=t.start_time,
                    duration_seconds=t.duration_seconds,
                    end_time=t.end_time,
                    randomize_start_seconds=t.randomize_start_seconds,
                    import_limit_active_watts=t.import_limit_active_watts,
                    export_limit_watts=t.export_limit_watts,
                    generation_limit_active_watts=t.generation_limit_active_watts,
                    load_limit_active_watts=t.load_limit_active_watts,
                    set_energized=t.set_energized,
                    set_connected=t.set_connected,
                ),
                site.timezone_id,
            )
        )
        for t in resp.all()
    ]


async def count_does_at_timestamp(
    session: AsyncSession,
    site_control_group_id: int,
    aggregator_id: int,
    site_id: Optional[int],
    timestamp: datetime,
    changed_after: datetime,
) -> int:
    """Fetches the number of DynamicOperatingEnvelope's stored that contain timestamp.

    site_control_group_id: The SiteControlGroup to select doe's from
    aggregator_id: The aggregator ID to filter sites/does against
    site_id: If None, no filter on site_id otherwise filters the results to this specific site_id
    timestamp: The actual timestamp that a DOE range must contain in order to be considered
    changed_after: Only doe's with a changed_time greater than this value will be counted (0 will count everything)"""

    return await _does_at_timestamp(
        True, session, site_control_group_id, aggregator_id, site_id, timestamp, 0, changed_after, None
    )  # type: ignore [return-value]  # Test coverage will ensure that it's an entity list


async def select_does_at_timestamp(
    session: AsyncSession,
    site_control_group_id: int,
    aggregator_id: int,
    site_id: Optional[int],
    timestamp: datetime,
    start: int,
    changed_after: datetime,
    limit: int,
) -> Sequence[DOE]:
    """Selects DynamicOperatingEnvelope entities (with pagination) that contain timestamp. Date will be assessed in the
    local timezone for the site

    site_control_group_id: The SiteControlGroup to select doe's from
    aggregator_id: The aggregator ID to filter sites/does against
    site_id: If None, no filter on site_id otherwise filters the results to this specific site_id
    timestamp: The actual timestamp that a DOE range must contain in order to be considered
    start: The number of matching entities to skip
    limit: The maximum number of entities to return
    changed_after: removes any entities with a changed_date BEFORE this value (set to datetime.min to not filter)

    Orders by 2030.5 requirements on DERControl which is start ASC, creation DESC, id DESC"""

    return await _does_at_timestamp(
        False, session, site_control_group_id, aggregator_id, site_id, timestamp, start, changed_after, limit
    )  # type: ignore [return-value]  # Test coverage will ensure that it's an entity list


async def _site_control_groups(
    is_counting: bool,
    session: AsyncSession,
    start: Optional[int],
    changed_after: datetime,
    limit: Optional[int],
) -> Union[Sequence[SiteControlGroup], int]:
    """Internal utility for fetching/counting SiteControlGroup's

    Orders by 2030.5 requirements on DERProgram which is primacy ASC, primary key DESC"""

    stmt: Union[Select[tuple[int]], Select[tuple[SiteControlGroup]]]
    if is_counting:
        stmt = select(func.count()).select_from(SiteControlGroup)
    else:
        stmt = select(SiteControlGroup).offset(start).limit(limit)

    if changed_after != datetime.min:
        stmt = stmt.where((SiteControlGroup.changed_time >= changed_after))

    if not is_counting:
        stmt = stmt.order_by(SiteControlGroup.primacy.asc(), SiteControlGroup.site_control_group_id.desc())

    resp = await session.execute(stmt)
    if is_counting:
        return resp.scalar_one()
    else:
        return resp.scalars().all()


async def select_site_control_groups(
    session: AsyncSession,
    start: Optional[int],
    changed_after: datetime,
    limit: Optional[int],
) -> Sequence[SiteControlGroup]:
    """Fetches SiteControlGroup with some basic pagination / filtering on change time.

    Orders by 2030.5 requirements on DERProgram which is primacy ASC, primary key DESC"""

    # Test coverage will ensure that it's an entity list
    return await _site_control_groups(False, session, start, changed_after, limit)  # type: ignore [return-value]


async def count_site_control_groups(
    session: AsyncSession,
    changed_after: datetime,
) -> int:
    """Counts SiteControlGroups that have been modified after the specified change time."""

    # Test coverage will ensure that it's an int
    return await _site_control_groups(True, session, 0, changed_after, None)  # type: ignore [return-value]


async def select_site_control_group_by_id(
    session: AsyncSession, site_control_group_id: int
) -> Optional[SiteControlGroup]:
    """Fetches a single SiteControlGroup with the specified site_control_group_id. Returns None if it can't be found."""

    stmt = select(SiteControlGroup).where(SiteControlGroup.site_control_group_id == site_control_group_id).limit(1)
    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()
