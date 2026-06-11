from datetime import UTC, datetime
from decimal import Decimal
from itertools import product

import pytest
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from sqlalchemy.exc import InvalidRequestError

from envoy.admin.crud.site import (
    count_all_site_groups,
    count_all_sites,
    select_all_site_groups,
    select_all_sites,
    select_single_site_no_scoping,
)
from envoy.server.api.request import MAX_LIMIT
from envoy.server.model.site import (
    Site,
    SiteDERAvailability,
    SiteDERRating,
    SiteDERSetting,
    SiteDERStatus,
    SiteGroup,
)


@pytest.mark.parametrize(
    "group, changed_after, expected_count",
    [
        (None, None, 6),
        ("", None, 6),
        ("Group-1", None, 3),
        ("Group-2", None, 1),
        ("Group-3", None, 0),
        ("Group DNE", None, 0),
        ("", datetime(2020, 11, 1), 6),
        ("", datetime.min, 6),
        ("", datetime.max, 0),
        ("", datetime(2022, 2, 3, 4, 5, 6, tzinfo=UTC), 6),
        ("", datetime(2022, 2, 3, 5, 0, 0, tzinfo=UTC), 5),
        ("", datetime(2022, 2, 3, 8, 5, 6, tzinfo=UTC), 4),
        ("", datetime(2022, 2, 3, 10, 5, 6, tzinfo=UTC), 3),
        ("Group-1", datetime(2022, 2, 3, 0, 0, 0, tzinfo=UTC), 3),
        ("Group-1", datetime(2022, 2, 3, 5, 0, 0, tzinfo=UTC), 2),
        ("Group-1", datetime(2022, 2, 3, 8, 0, 0, tzinfo=UTC), 1),
    ],
)
@pytest.mark.anyio
async def test_count_all_sites(pg_base_config, group: str | None, changed_after: datetime | None, expected_count: int):
    async with generate_async_session(pg_base_config) as session:
        assert (await count_all_sites(session, group, changed_after)) == expected_count


@pytest.mark.anyio
async def test_count_all_sites_empty(pg_empty_config):
    async with generate_async_session(pg_empty_config) as session:
        assert (await count_all_sites(session, None, None)) == 0
        assert (await count_all_sites(session, "Group-1", None)) == 0
        assert (await count_all_sites(session, "Group-1", datetime(2022, 11, 1))) == 0


@pytest.mark.parametrize(
    "start, limit, group, changed_after, expected_site_ids, expected_group_ids, expected_der_ids",
    [
        (
            0,
            500,
            None,
            None,
            [1, 2, 3, 4, 5, 6],
            [[1, 2], [1], [1], [], [], []],
            [(1, 1, 1, 1), None, None, None, None, None],
        ),
        (
            0,
            500,
            None,
            datetime(2022, 2, 3, 8, 5, 6, tzinfo=UTC),
            [3, 4, 5, 6],
            [[1], [], [], []],
            [None, None, None, None],
        ),
        (
            0,
            500,
            "",
            None,
            [1, 2, 3, 4, 5, 6],
            [[1, 2], [1], [1], [], [], []],
            [(1, 1, 1, 1), None, None, None, None, None],
        ),
        (0, 500, "Group-1", None, [1, 2, 3], [[1, 2], [1], [1]], [(1, 1, 1, 1), None, None]),
        (0, 500, "Group-1", datetime(2022, 2, 3, 8, 5, 6, tzinfo=UTC), [3], [[1]], [None]),
        (0, 500, "Group-2", None, [1], [[1, 2]], [(1, 1, 1, 1)]),
        (0, 500, "Group-3", None, [], [], []),
        (0, 500, "Group-DNE", None, [], [], []),
        (
            1,
            500,
            None,
            None,
            [2, 3, 4, 5, 6],
            [[1], [1], [], [], []],
            [None, None, None, None, None],
        ),
        (2, 500, None, None, [3, 4, 5, 6], [[1], [], [], []], [None, None, None, None]),
        (3, 500, None, None, [4, 5, 6], [[], [], []], [None, None, None]),
        (6, 500, None, None, [], [], []),
        (1, 2, None, None, [2, 3], [[1], [1]], [None, None]),
        (2, 2, None, None, [3, 4], [[1], []], [None, None]),
        (0, 0, None, None, [], [], []),
        (1, 1, "Group-1", None, [2], [[1]], [None]),
    ],
)
@pytest.mark.anyio
async def test_select_all_sites(
    pg_base_config,
    start: int,
    limit: int,
    group: str | None,
    changed_after: datetime | None,
    expected_site_ids: list[int],
    expected_group_ids: list[list[int]],
    expected_der_ids: list[tuple[int | None, int | None, int | None, int | None] | None],
):
    """
    expected_der_ids: Tuple(DERAvailId, DERRatingId, DERSettingId, DERStatusId) or None if the site has no DER data"""

    assert len(expected_site_ids) == len(expected_group_ids), "Validating the test inputs all align"
    assert len(expected_der_ids) == len(expected_group_ids), "Validating the test inputs all align"

    async with generate_async_session(pg_base_config) as session:
        sites_no_groups_no_der = await select_all_sites(
            session, group, start, limit, changed_after, include_groups=False
        )

    async with generate_async_session(pg_base_config) as session:
        sites_with_groups_no_der = await select_all_sites(
            session, group, start, limit, changed_after, include_groups=True
        )

    async with generate_async_session(pg_base_config) as session:
        sites_no_groups_with_der = await select_all_sites(session, group, start, limit, changed_after, include_der=True)

    async with generate_async_session(pg_base_config) as session:
        sites_with_groups_der = await select_all_sites(
            session, group, start, limit, changed_after, include_der=True, include_groups=True
        )

    # Validate groups vs no groups are identical
    assert_list_type(Site, sites_no_groups_no_der, count=len(expected_site_ids))
    assert_list_type(Site, sites_with_groups_no_der, count=len(expected_site_ids))
    assert_list_type(Site, sites_no_groups_with_der, count=len(expected_site_ids))
    assert_list_type(Site, sites_with_groups_der, count=len(expected_site_ids))

    assert expected_site_ids == [s.site_id for s in sites_no_groups_no_der]
    assert expected_site_ids == [s.site_id for s in sites_with_groups_no_der]
    assert expected_site_ids == [s.site_id for s in sites_no_groups_with_der]
    assert expected_site_ids == [s.site_id for s in sites_with_groups_der]

    # Validate the groups were returned as expected
    assert expected_group_ids == [[a.group.site_group_id for a in s.assignments] for s in sites_with_groups_no_der]
    assert expected_group_ids == [[a.group.site_group_id for a in s.assignments] for s in sites_with_groups_der]

    # Validate the DER were returned as expected
    def der_to_expected_tuple(
        site: Site,
    ) -> tuple[int | None, int | None, int | None, int | None] | None:
        """Returns Tuple(DERAvailId, DERRatingId, DERSettingId, DERStatusId) or None if the site has no DER data"""
        ids = (
            site.site_der_availability.site_der_availability_id if site.site_der_availability else None,
            site.site_der_rating.site_der_rating_id if site.site_der_rating else None,
            site.site_der_setting.site_der_setting_id if site.site_der_setting else None,
            site.site_der_status.site_der_status_id if site.site_der_status else None,
        )
        return None if all(i is None for i in ids) else ids

    assert expected_der_ids == [der_to_expected_tuple(s) for s in sites_no_groups_with_der]
    assert expected_der_ids == [der_to_expected_tuple(s) for s in sites_with_groups_der]

    # And that sites without groups don't have any groups
    if len(sites_no_groups_no_der) > 0:
        with pytest.raises(InvalidRequestError):
            assert all([len(s.assignments) == 0 for s in sites_no_groups_no_der])
        with pytest.raises(InvalidRequestError):
            assert all([len(s.assignments) == 0 for s in sites_no_groups_with_der])

    # And that the DER relationships raise when they weren't eagerly loaded (include_der=False)
    if len(sites_no_groups_no_der) > 0:
        with pytest.raises(InvalidRequestError):
            assert all([s.site_der_rating is None for s in sites_no_groups_no_der])
        with pytest.raises(InvalidRequestError):
            assert all([s.site_der_rating is None for s in sites_with_groups_no_der])


@pytest.mark.anyio
async def test_max_limit_select_all_sites(pg_base_config):
    """select_all_sites does some heavy joins when including groups and DER - this tries to stress out
    a "worst case scenario" lookup"""
    async with generate_async_session(pg_base_config) as session:
        initial_site_count = await count_all_sites(session, None, None)
        for i in range(MAX_LIMIT):
            seed = i
            site: Site = generate_class_instance(Site, seed=seed, site_id=None, aggregator_id=3)
            site.site_der_rating = generate_class_instance(
                SiteDERRating, seed=seed, site_id=None, site_der_rating_id=None
            )
            site.site_der_status = generate_class_instance(
                SiteDERStatus, seed=seed, site_id=None, site_der_status_id=None, manufacturer_status=f"s{i}"
            )
            site.site_der_setting = generate_class_instance(
                SiteDERSetting, seed=seed, site_id=None, site_der_setting_id=None
            )
            site.site_der_availability = generate_class_instance(
                SiteDERAvailability, seed=seed, site_id=None, site_der_availability_id=None
            )
            session.add(site)
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        sites = await select_all_sites(
            session, None, initial_site_count, MAX_LIMIT, None, include_groups=True, include_der=True
        )
        assert_list_type(Site, sites, count=MAX_LIMIT)

        site_status_ids = [s.site_der_status.site_der_status_id for s in sites]  # ty:ignore[unresolved-attribute]
        site_avail_ids = [s.site_der_availability.site_der_availability_id for s in sites]  # ty:ignore[unresolved-attribute]
        site_rating_ids = [s.site_der_rating.site_der_rating_id for s in sites]  # ty:ignore[unresolved-attribute]
        site_settings_ids = [s.site_der_setting.site_der_setting_id for s in sites]  # ty:ignore[unresolved-attribute]

        assert len(site_rating_ids) == MAX_LIMIT
        assert len(site_rating_ids) == len(set(site_rating_ids)), "All Unique values"

        assert len(site_status_ids) == MAX_LIMIT
        assert len(site_status_ids) == len(set(site_status_ids)), "All Unique values"

        assert len(site_avail_ids) == MAX_LIMIT
        assert len(site_avail_ids) == len(set(site_avail_ids)), "All Unique values"

        assert len(site_rating_ids) == MAX_LIMIT
        assert len(site_rating_ids) == len(set(site_rating_ids)), "All Unique values"

        assert len(site_settings_ids) == MAX_LIMIT
        assert len(site_settings_ids) == len(set(site_settings_ids)), "All Unique values"


@pytest.mark.anyio
async def test_count_all_site_groups(pg_base_config):
    async with generate_async_session(pg_base_config) as session:
        assert (await count_all_site_groups(session)) == 3


@pytest.mark.anyio
async def test_count_all_site_groups_empty(pg_empty_config):
    async with generate_async_session(pg_empty_config) as session:
        assert (await count_all_site_groups(session)) == 0


@pytest.mark.parametrize(
    "start, limit, group, expected_id_count",
    [
        (0, 500, None, [(1, 3), (2, 1), (3, 0)]),
        (0, 2, None, [(1, 3), (2, 1)]),
        (1, 2, None, [(2, 1), (3, 0)]),
        (2, 2, None, [(3, 0)]),
        (0, 500, "Group-1", [(1, 3)]),
        (0, 500, "Group-2", [(2, 1)]),
        (0, 500, "Group-3", [(3, 0)]),
        (0, 500, "Group-DNE", []),
    ],
)
@pytest.mark.anyio
async def test_select_all_site_groups(
    pg_base_config, start: int, limit: int, group: str | None, expected_id_count: list[tuple[int, int]]
):
    """Selects groups with their counts and makes sure everything lines up"""
    async with generate_async_session(pg_base_config) as session:
        groups = await select_all_site_groups(session, group, start, limit)
        assert len(groups) == len(expected_id_count)

        assert all([isinstance(g, tuple) for g in groups])
        assert all([isinstance(g[0], SiteGroup) for g in groups])
        assert all([isinstance(g[1], int) for g in groups])
        assert expected_id_count == [(sg.site_group_id, count) for sg, count in groups]


@pytest.mark.parametrize("missing_site_id", [0, -1, 9999])
@pytest.mark.anyio
async def test_select_single_site_no_scoping_missing_site_ids(pg_base_config, missing_site_id: int):
    async with generate_async_session(pg_base_config) as session:
        for groups, der in product([True, False], [True, False]):
            assert (await select_single_site_no_scoping(session, missing_site_id, groups, der)) is None


@pytest.mark.parametrize(
    "site_id, expected_group_ids, expected_der_ids, expected_site_import_watts",
    [
        (1, [1, 2], (1, 1, 1, 1), Decimal("10.10")),
        (2, [1], None, None),
        (3, [1], None, Decimal("20.20")),
        (4, [], None, None),
        (5, [], None, None),
        (6, [], None, None),
    ],
)
@pytest.mark.anyio
async def test_select_single_site_no_scoping(
    pg_base_config,
    site_id,
    expected_group_ids: list[int],
    expected_der_ids: tuple[int, int | None, int | None, int | None, int | None] | None,
    expected_site_import_watts: Decimal | None,
):
    """
    expected_der_ids: Tuple(DERId, DERAvailId, DERRatingId, DERSettingId, DERStatusId)"""

    def der_to_expected_tuple(
        ders: list[SiteDER],
    ) -> tuple[int, int | None, int | None, int | None, int | None] | None:
        """Returns Tuple(DERId, DERAvailId, DERRatingId, DERSettingId, DERStatusId)"""
        if not ders:
            return None

        assert len(ders) == 1, "There should be ONLY be a single SiteDER per site "

        return (
            ders[0].site_der_id,
            ders[0].site_der_availability.site_der_availability_id if ders[0].site_der_availability else None,
            ders[0].site_der_rating.site_der_rating_id if ders[0].site_der_rating else None,
            ders[0].site_der_setting.site_der_setting_id if ders[0].site_der_setting else None,
            ders[0].site_der_status.site_der_status_id if ders[0].site_der_status else None,
        )

    for include_groups, include_der in product([True, False], [True, False]):
        async with generate_async_session(pg_base_config) as session:
            site = await select_single_site_no_scoping(
                session,
                site_id,
                include_groups=include_groups,
                include_der=include_der,
            )
            assert site is not None

            if include_groups:
                assert expected_group_ids == [a.group.site_group_id for a in site.assignments]
            else:
                with pytest.raises(InvalidRequestError):
                    assert len(site.assignments) == 0

            if include_der:
                assert expected_der_ids == der_to_expected_tuple(site.site_ders)
            else:
                with pytest.raises(InvalidRequestError):
                    assert len(site.site_ders) == 0
