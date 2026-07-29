from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql import ColumnElement
from sqlalchemy.sql.selectable import Exists

from envoy.server.model.site import Site, SiteGroup, SiteGroupAssignment


def site_is_member_of_group(site_group_id_col: InstrumentedAttribute[int], site_id: int) -> Exists:
    """Builds a correlated EXISTS clause checking that site_id is a member (via SiteGroupAssignment) of the
    SiteGroup referenced by site_group_id_col (typically an entity's site_group_id column from the enclosing
    statement). Does not join/fan-out - safe to use regardless of how many sites are in the group."""

    return site_group_membership_exists(site_group_id_col, aggregator_id=None, site_id=site_id)


def site_group_membership_exists(
    site_group_id_col: InstrumentedAttribute[int], aggregator_id: int | None, site_id: int | None
) -> Exists:
    """Builds a correlated EXISTS clause checking SiteGroupAssignment (+ Site, if aggregator_id is specified)
    membership for the SiteGroup referenced by site_group_id_col.

    aggregator_id: if given, requires a matching member site to belong to this aggregator (scoped to site_id's
        aggregator specifically, if site_id is also given)
    site_id: if given, requires this specific site to be a member of the group

    Never joins against the enclosing statement, so an entity row can never fan out into multiple result rows
    regardless of how many sites are in its SiteGroup."""

    conditions: list[ColumnElement[bool]] = [SiteGroupAssignment.site_group_id == site_group_id_col]

    stmt = select(SiteGroupAssignment.site_group_assignment_id)
    if aggregator_id is not None:
        stmt = stmt.join(Site, Site.site_id == SiteGroupAssignment.site_id)
        conditions.append(Site.aggregator_id == aggregator_id)

    if site_id is not None:
        conditions.append(SiteGroupAssignment.site_id == site_id)

    return stmt.where(and_(*conditions)).exists()


def required_site_group_visible_to_site(
    required_site_group_id_col: InstrumentedAttribute[int | None], site_id: int
) -> ColumnElement[bool]:
    """Builds a filter clause for an optional "required_site_group_id" column (SiteControlGroup/Tariff): True if
    the column is NULL (no restriction - globally visible) or if site_id is a member (via SiteGroupAssignment) of
    the SiteGroup it references.

    Never joins against the enclosing statement, so an entity row can never fan out into multiple result rows
    regardless of how many sites are in the required SiteGroup."""

    member_exists = (
        select(SiteGroupAssignment.site_group_assignment_id)
        .where(
            (SiteGroupAssignment.site_group_id == required_site_group_id_col) & (SiteGroupAssignment.site_id == site_id)
        )
        .exists()
    )
    return or_(required_site_group_id_col.is_(None), member_exists)


async def assign_default_site_groups_to_site(session: AsyncSession, site_id: int, changed_time: datetime) -> None:
    """Adds a SiteGroupAssignment linking site_id to every SiteGroup marked as default_group=True. Intended to be
    called immediately after a new Site is created so it automatically becomes a member of the "default" groups.

    Does not flush/commit - it's expected the caller will do so as part of the enclosing transaction."""

    default_group_ids = (
        (await session.execute(select(SiteGroup.site_group_id).where(SiteGroup.default_group.is_(True))))
        .scalars()
        .all()
    )

    for site_group_id in default_group_ids:
        session.add(SiteGroupAssignment(site_id=site_id, site_group_id=site_group_id, changed_time=changed_time))
