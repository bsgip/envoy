from datetime import UTC, datetime

import pytest
from assertical.fixtures.postgres import generate_async_session
from sqlalchemy import select, update

from envoy.server.crud.site_group import assign_default_site_groups_to_site
from envoy.server.model.site import SiteGroup, SiteGroupAssignment

CHANGED_TIME = datetime(2024, 11, 1, 2, 3, 4, tzinfo=UTC)


@pytest.mark.anyio
async def test_assign_default_site_groups_to_site_no_defaults(pg_base_config):
    """If no SiteGroup is marked default_group - assigning a new site shouldn't create any assignments"""

    async with generate_async_session(pg_base_config) as session:
        before = (await session.execute(select(SiteGroupAssignment.site_group_assignment_id))).scalars().all()

        await assign_default_site_groups_to_site(session, 4, CHANGED_TIME)
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        after = (await session.execute(select(SiteGroupAssignment.site_group_assignment_id))).scalars().all()
        assert len(after) == len(before), "No default groups exist - no assignments should be created"


@pytest.mark.anyio
async def test_assign_default_site_groups_to_site_with_defaults(pg_base_config):
    """SiteGroups marked default_group=True should all pick up a new site as a member. Groups that aren't marked
    default should be left untouched."""

    async with generate_async_session(pg_base_config) as session:
        # Group 3 and 4 become "default" groups - group 1/2/5 remain untouched
        await session.execute(update(SiteGroup).where(SiteGroup.site_group_id.in_([3, 4])).values(default_group=True))
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        # Site 4 isn't currently a member of any group (see base_config.sql)
        await assign_default_site_groups_to_site(session, 4, CHANGED_TIME)
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        site_4_group_ids = set(
            (await session.execute(select(SiteGroupAssignment.site_group_id).where(SiteGroupAssignment.site_id == 4)))
            .scalars()
            .all()
        )
        assert site_4_group_ids == {3, 4}

        new_assignment = (
            await session.execute(
                select(SiteGroupAssignment).where(
                    (SiteGroupAssignment.site_id == 4) & (SiteGroupAssignment.site_group_id == 3)
                )
            )
        ).scalar_one()
        assert new_assignment.changed_time == CHANGED_TIME

        # Group 1 (not marked default) should be untouched - site 4 shouldn't have joined it
        group_1_site_ids = set(
            (await session.execute(select(SiteGroupAssignment.site_id).where(SiteGroupAssignment.site_group_id == 1)))
            .scalars()
            .all()
        )
        assert group_1_site_ids == {1, 2, 3}
