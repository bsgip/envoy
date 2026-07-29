import json
from datetime import UTC, datetime
from http import HTTPStatus
from urllib.parse import quote_plus

import pytest
from assertical.asserts.time import assert_nowish
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.site import SitePageResponse, SiteResponse, SiteUpdateRequest
from envoy_schema.admin.schema.site_group import (
    SiteGroupAssignmentPageResponse,
    SiteGroupAssignmentRequest,
    SiteGroupAssignmentResponse,
    SiteGroupPageResponse,
    SiteGroupRequest,
    SiteGroupResponse,
)
from envoy_schema.admin.schema.uri import (
    SiteGroupAssignmentsListUri,
    SiteGroupAssignmentsUri,
    SiteGroupListUri,
    SiteGroupUri,
    SiteListUri,
    SiteUri,
)
from envoy_schema.server.schema.sep2.types import DeviceCategory
from httpx import AsyncClient
from sqlalchemy import func, select

from envoy.admin.crud.site import count_all_site_group_assignments, count_all_site_groups, count_all_sites
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.archive.site import ArchiveSite
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
from envoy.server.model.site import Site, SiteGroup, SiteGroupAssignment
from tests.integration.response import read_response_body_string


def _build_query_string(start: int | None, limit: int | None, group_filter: str | None, after: datetime | None) -> str:
    query = "?"
    if start is not None:
        query = query + f"&start={start}"
    if limit is not None:
        query = query + f"&limit={limit}"
    if group_filter is not None:
        query = query + f"&group={group_filter}"
    if after is not None:
        query = query + f"&after={quote_plus(after.isoformat())}"
    return query


SITE_1_DER_CFG_CHANGED_TIME = datetime(2022, 2, 9, 11, 6, 44, 500000, tzinfo=UTC)  # This is from DERSetting
SITE_1_DER_AVAIL_CHANGED_TIME = datetime(2022, 7, 23, 10, 3, 23, 500000, tzinfo=UTC)  # This is from DERAvail
SITE_1_DER_STATUS_CHANGED_TIME = datetime(2022, 11, 1, 11, 5, 4, 500000, tzinfo=UTC)  # This is from DERStatus

SITE_1_DER_EXPECTED = (SITE_1_DER_CFG_CHANGED_TIME, SITE_1_DER_AVAIL_CHANGED_TIME, SITE_1_DER_STATUS_CHANGED_TIME)
SITE_X_NO_DER_EXPECTED = (None, None, None)


@pytest.mark.parametrize(
    "start, limit, group, after, expected_site_ids, expected_der_changed_times",
    [
        (
            None,
            None,
            None,
            None,
            [1, 2, 3, 4, 5, 6],
            [
                SITE_1_DER_EXPECTED,
                SITE_X_NO_DER_EXPECTED,
                SITE_X_NO_DER_EXPECTED,
                SITE_X_NO_DER_EXPECTED,
                SITE_X_NO_DER_EXPECTED,
                SITE_X_NO_DER_EXPECTED,
            ],
        ),
        (None, None, "Group-1", None, [1, 2, 3], [SITE_1_DER_EXPECTED, SITE_X_NO_DER_EXPECTED, SITE_X_NO_DER_EXPECTED]),
        (
            None,
            None,
            "Group-1",
            datetime(2022, 2, 3, 5, 6, 7, tzinfo=UTC),
            [2, 3],
            [SITE_X_NO_DER_EXPECTED, SITE_X_NO_DER_EXPECTED],
        ),
        (None, None, "Group-2", None, [1], [SITE_1_DER_EXPECTED]),
        (None, None, "Group-3", None, [], []),
        (None, None, "Group-DNE", None, [], []),
        (
            0,
            10,
            None,
            None,
            [1, 2, 3, 4, 5, 6],
            [
                SITE_1_DER_EXPECTED,
                SITE_X_NO_DER_EXPECTED,
                SITE_X_NO_DER_EXPECTED,
                SITE_X_NO_DER_EXPECTED,
                SITE_X_NO_DER_EXPECTED,
                SITE_X_NO_DER_EXPECTED,
            ],
        ),
        (
            2,
            10,
            None,
            None,
            [3, 4, 5, 6],
            [SITE_X_NO_DER_EXPECTED, SITE_X_NO_DER_EXPECTED, SITE_X_NO_DER_EXPECTED, SITE_X_NO_DER_EXPECTED],
        ),
        (None, 2, None, None, [1, 2], [SITE_1_DER_EXPECTED, SITE_X_NO_DER_EXPECTED]),
        (2, 2, None, None, [3, 4], [SITE_X_NO_DER_EXPECTED, SITE_X_NO_DER_EXPECTED]),
        (5, 2, None, None, [6], [SITE_X_NO_DER_EXPECTED]),
        (1, 1, "Group-1", None, [2], [SITE_X_NO_DER_EXPECTED]),
        (
            None,
            None,
            None,
            datetime(2022, 2, 3, 5, 6, 7, tzinfo=UTC),
            [2, 3, 4, 5, 6],
            [
                SITE_X_NO_DER_EXPECTED,
                SITE_X_NO_DER_EXPECTED,
                SITE_X_NO_DER_EXPECTED,
                SITE_X_NO_DER_EXPECTED,
                SITE_X_NO_DER_EXPECTED,
            ],
        ),
        (
            0,
            2,
            None,
            datetime(2022, 2, 3, 11, 12, 0, tzinfo=UTC),
            [4, 5],
            [SITE_X_NO_DER_EXPECTED, SITE_X_NO_DER_EXPECTED],
        ),
        (3, 2, None, datetime(2022, 2, 3, 11, 12, 0, tzinfo=UTC), [], []),
    ],
)
@pytest.mark.anyio
async def test_get_all_sites(
    admin_client_auth: AsyncClient,
    pg_base_config,
    start: int,
    limit: int,
    group: str | None,
    after: datetime | None,
    expected_site_ids: list[int],
    expected_der_changed_times: list[tuple[datetime | None, datetime | None, datetime | None]],
):
    """expected_der_changed_times is the combination of the changed_time properties from
    (der_config, der_availability, der_status) that correspond 1-1 with the sites with expected_site_ids.
    It's there to validate the DER metadata being correctly assigned"""
    assert len(expected_site_ids) == len(expected_der_changed_times), (
        "There should be a 1-1 correspondence or this test is invalid"
    )

    expected_total_sites: int
    async with generate_async_session(pg_base_config) as session:
        expected_total_sites = await count_all_sites(session, group, after)

    response = await admin_client_auth.get(SiteListUri + _build_query_string(start, limit, group, after))
    assert response.status_code == HTTPStatus.OK

    body = read_response_body_string(response)
    assert len(body) > 0
    site_page: SitePageResponse = SitePageResponse(**json.loads(body))

    assert isinstance(site_page.limit, int)
    assert isinstance(site_page.total_count, int)
    assert isinstance(site_page.start, int)
    assert len(site_page.sites) == len(expected_site_ids)
    assert all([isinstance(s, SiteResponse) for s in site_page.sites])

    assert site_page.total_count == expected_total_sites, (
        f"There are only {expected_total_sites} sites available in the current config for group {group}"
    )
    if limit is not None:
        assert site_page.limit == limit
    if start is not None:
        assert site_page.start == start

    assert [s.site_id for s in site_page.sites] == expected_site_ids

    assert [
        (
            s.der_config.changed_time if s.der_config else None,
            s.der_availability.changed_time if s.der_availability else None,
            s.der_status.changed_time if s.der_status else None,
        )
        for s in site_page.sites
    ] == expected_der_changed_times
    assert all(s.created_time == datetime(2000, 1, 1, tzinfo=UTC) for s in site_page.sites)


@pytest.mark.parametrize(
    "start, limit, expected_group_count",
    [
        (None, None, [(1, 3), (2, 1), (3, 0), (4, 1), (5, 1)]),
        (None, 10, [(1, 3), (2, 1), (3, 0), (4, 1), (5, 1)]),
        (None, 2, [(1, 3), (2, 1)]),
        (1, 2, [(2, 1), (3, 0)]),
        (2, 2, [(3, 0), (4, 1)]),
        (3, 2, [(4, 1), (5, 1)]),
        (3, None, [(4, 1), (5, 1)]),
    ],
)
@pytest.mark.anyio
async def test_get_all_site_groups(
    admin_client_auth: AsyncClient,
    pg_base_config,
    start: int,
    limit: int,
    expected_group_count: list[tuple[int, int]],
):
    expected_total_groups: int
    async with generate_async_session(pg_base_config) as session:
        expected_total_groups = await count_all_site_groups(session)

    response = await admin_client_auth.get(SiteGroupListUri + _build_query_string(start, limit, None, None))
    assert response.status_code == HTTPStatus.OK

    body = read_response_body_string(response)
    assert len(body) > 0
    group_page: SiteGroupPageResponse = SiteGroupPageResponse(**json.loads(body))

    assert isinstance(group_page.limit, int)
    assert isinstance(group_page.total_count, int)
    assert isinstance(group_page.start, int)
    assert len(group_page.groups) == len(expected_group_count)
    assert all([isinstance(s, SiteGroupResponse) for s in group_page.groups])

    assert group_page.total_count == expected_total_groups, (
        f"There are only {expected_total_groups} sites available in the current config"
    )
    if limit is not None:
        assert group_page.limit == limit
    if start is not None:
        assert group_page.start == start

    assert [(g.site_group_id, g.total_sites) for g in group_page.groups] == expected_group_count
    assert all(g.default_group is False for g in group_page.groups), "No groups are marked default in base_config"


@pytest.mark.parametrize(
    "group_name, expected_group_count",
    [
        ("Group-1", (1, 3)),
        ("Group-2", (2, 1)),
        ("Group-3", (3, 0)),
        ("Group-4", None),
    ],
)
@pytest.mark.anyio
async def test_get_site_groups(
    admin_client_auth: AsyncClient,
    group_name: str,
    expected_group_count: tuple[int, int] | None,
):

    response = await admin_client_auth.get(SiteGroupUri.format(group_name=group_name))

    if expected_group_count is None:
        assert response.status_code == HTTPStatus.NOT_FOUND
    else:
        assert response.status_code == HTTPStatus.OK

        body = read_response_body_string(response)
        assert len(body) > 0
        group: SiteGroupResponse = SiteGroupResponse(**json.loads(body))

        assert isinstance(group, SiteGroupResponse)
        assert group.site_group_id == expected_group_count[0]
        assert group.total_sites == expected_group_count[1]
        assert group.name == group_name
        assert group.default_group is False, "No groups are marked default in base_config"


@pytest.mark.parametrize(
    "site_id, expected_der_changed_time",
    [
        (1, SITE_1_DER_EXPECTED),
        (2, SITE_X_NO_DER_EXPECTED),
        (3, SITE_X_NO_DER_EXPECTED),
        (99, None),
    ],
)
@pytest.mark.anyio
async def test_get_site(
    admin_client_auth: AsyncClient,
    site_id: int,
    expected_der_changed_time: tuple[datetime | None, datetime | None, datetime | None] | None,
):
    """expected_der_changed_times is the combination of the changed_time properties from
    (der_config, der_availability, der_status) It's there to validate the DER metadata being correctly assigned"""

    response = await admin_client_auth.get(SiteUri.format(site_id=site_id))

    if expected_der_changed_time is None:
        assert response.status_code == HTTPStatus.NOT_FOUND
    else:
        body = read_response_body_string(response)
        assert len(body) > 0
        site_response: SiteResponse = SiteResponse(**json.loads(body))

        assert site_response.site_id == site_id
        assert (
            site_response.der_config.changed_time if site_response.der_config else None,
            site_response.der_availability.changed_time if site_response.der_availability else None,
            site_response.der_status.changed_time if site_response.der_status else None,
        ) == expected_der_changed_time


@pytest.mark.parametrize(
    "site_id, expected_status, archive_site_count, archive_doe_count, archive_price_count",
    [
        # DOEs/TariffGeneratedRates are no longer archived/deleted as a side effect of deleting a site - both now
        # target a SiteGroup (which may have other member sites still relying on it), not this Site directly.
        (1, HTTPStatus.NO_CONTENT, 1, 0, 0),
        (2, HTTPStatus.NO_CONTENT, 1, 0, 0),
        (3, HTTPStatus.NO_CONTENT, 1, 0, 0),
        (4, HTTPStatus.NO_CONTENT, 1, 0, 0),
        (5, HTTPStatus.NO_CONTENT, 1, 0, 0),
        (99, HTTPStatus.NOT_FOUND, 0, 0, 0),
    ],
)
@pytest.mark.anyio
async def test_delete_site_archives(
    admin_client_auth: AsyncClient,
    pg_base_config,
    site_id: int,
    expected_status: HTTPStatus,
    archive_site_count: int,
    archive_doe_count: int,
    archive_price_count: int,
):
    """Tests that deleting sites generates archive records"""

    response = await admin_client_auth.delete(SiteUri.format(site_id=site_id))
    assert response.status_code == expected_status

    # Count archive rows are generated
    async with generate_async_session(pg_base_config) as session:
        actual_archive_site_count = (
            await session.execute(
                select(func.count()).select_from(ArchiveSite).where(ArchiveSite.deleted_time.is_not(None))
            )
        ).scalar_one()
        actual_archive_doe_count = (
            await session.execute(
                select(func.count())
                .select_from(ArchiveDynamicOperatingEnvelope)
                .where(ArchiveDynamicOperatingEnvelope.deleted_time.is_not(None))
            )
        ).scalar_one()
        actual_archive_price_count = (
            await session.execute(
                select(func.count())
                .select_from(ArchiveTariffGeneratedRate)
                .where(ArchiveTariffGeneratedRate.deleted_time.is_not(None))
            )
        ).scalar_one()
        assert actual_archive_site_count == archive_site_count
        assert actual_archive_doe_count == archive_doe_count
        assert actual_archive_price_count == archive_price_count

    # Subsequent query will now 404
    response = await admin_client_auth.delete(SiteUri.format(site_id=site_id))
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    "site_id, update_request, expected_status, expected_nmi, expected_tz, expected_device_category, expected_post_rate",
    [
        (
            1,
            SiteUpdateRequest(nmi="", timezone_id="Australia/Perth", device_category=None, post_rate_seconds=0),
            HTTPStatus.NO_CONTENT,
            None,
            "Australia/Perth",
            0,
            None,
        ),
        (
            1,
            SiteUpdateRequest(nmi="abc456", timezone_id=None, device_category=None, post_rate_seconds=None),
            HTTPStatus.NO_CONTENT,
            "abc456",
            "Australia/Brisbane",
            0,
            111,
        ),
        (
            2,
            SiteUpdateRequest(
                nmi="abc123", timezone_id=None, device_category=DeviceCategory.FUEL_CELL, post_rate_seconds=23
            ),
            HTTPStatus.NO_CONTENT,
            "abc123",
            "Australia/Brisbane",
            DeviceCategory.FUEL_CELL,
            23,
        ),
        (
            2,
            SiteUpdateRequest(nmi="", timezone_id=None, device_category=None, post_rate_seconds=None),
            HTTPStatus.NO_CONTENT,
            None,
            "Australia/Brisbane",
            1,
            None,
        ),
        (
            5,
            SiteUpdateRequest(
                nmi=None,
                timezone_id="Australia/Sydney",
                device_category=DeviceCategory.ELECTRIC_VEHICLE | DeviceCategory.HOT_TUB,
                post_rate_seconds=-1,
            ),
            HTTPStatus.NO_CONTENT,
            "5555555555",
            "Australia/Sydney",
            DeviceCategory.ELECTRIC_VEHICLE | DeviceCategory.HOT_TUB,
            None,
        ),
        (
            99,
            SiteUpdateRequest(nmi="", timezone_id=None, device_category=None, post_rate_seconds=456),
            HTTPStatus.NOT_FOUND,
            None,
            None,
            None,
            None,
        ),
    ],
)
@pytest.mark.anyio
async def test_update_site_archives(
    admin_client_auth: AsyncClient,
    pg_base_config,
    site_id: int,
    update_request: SiteUpdateRequest,
    expected_status: HTTPStatus,
    expected_nmi: str | None,
    expected_tz: str | None,
    expected_device_category: DeviceCategory | None,
    expected_post_rate: int | None,
):
    """Tests that updating sites generates archive records"""

    response = await admin_client_auth.post(SiteUri.format(site_id=site_id), content=update_request.model_dump_json())
    assert response.status_code == expected_status

    if response.status_code == HTTPStatus.NOT_FOUND:
        expected_archive_count = 0
        check_site = False
    else:
        expected_archive_count = 1
        check_site = True

    # Count archive rows are generated, check the row updated
    async with generate_async_session(pg_base_config) as session:
        actual_archive_site_count = (
            await session.execute(
                select(func.count()).select_from(ArchiveSite).where(ArchiveSite.deleted_time.is_(None))
            )
        ).scalar_one()
        assert actual_archive_site_count == expected_archive_count

        if check_site:
            actual_site = (await session.execute(select(Site).where(Site.site_id == site_id))).scalar_one()
            assert actual_site.nmi == expected_nmi
            assert actual_site.post_rate_seconds == expected_post_rate
            assert actual_site.device_category == expected_device_category
            assert actual_site.timezone_id == expected_tz
            assert_nowish(actual_site.changed_time)


@pytest.mark.anyio
async def test_create_group(admin_client_auth: AsyncClient, pg_base_config):
    group_request = generate_class_instance(SiteGroupRequest, name="A Brand New Group", default_group=False)
    resp = await admin_client_auth.post(SiteGroupListUri, content=group_request.model_dump_json())
    assert resp.status_code == HTTPStatus.CREATED

    location = resp.headers["Location"]
    assert location == SiteGroupUri.format(group_name=group_request.name)

    async with generate_async_session(pg_base_config) as session:
        created_group = (
            await session.execute(select(SiteGroup).where(SiteGroup.name == group_request.name))
        ).scalar_one()
        assert created_group.default_group == group_request.default_group
        assert_nowish(created_group.changed_time)

    # And it's now visible via the single group GET
    get_resp = await admin_client_auth.get(SiteGroupUri.format(group_name=group_request.name))
    assert get_resp.status_code == HTTPStatus.OK
    group_response = SiteGroupResponse(**json.loads(read_response_body_string(get_resp)))
    assert group_response.name == group_request.name
    assert group_response.total_sites == 0


@pytest.mark.anyio
async def test_create_group_duplicate_name(admin_client_auth: AsyncClient, pg_base_config):
    group_request = generate_class_instance(SiteGroupRequest, name="Group-1", default_group=False)
    resp = await admin_client_auth.post(SiteGroupListUri, content=group_request.model_dump_json())
    assert resp.status_code == HTTPStatus.BAD_REQUEST

    async with generate_async_session(pg_base_config) as session:
        assert (await count_all_site_groups(session)) == 5, "No new group should've been created"


@pytest.mark.parametrize(
    "group_name, start, limit, expected_assignment_ids, expected_site_ids",
    [
        ("Group-1", None, None, [1, 2, 3], [1, 2, 3]),
        ("Group-1", 1, None, [2, 3], [2, 3]),
        ("Group-1", None, 2, [1, 2], [1, 2]),
        ("Group-1", 1, 1, [2], [2]),
        ("Group-2", None, None, [4], [1]),
        ("Group-3", None, None, [], []),
        ("Group-DNE", None, None, None, None),
    ],
)
@pytest.mark.anyio
async def test_get_all_group_assignments(
    admin_client_auth: AsyncClient,
    pg_base_config,
    group_name: str,
    start: int | None,
    limit: int | None,
    expected_assignment_ids: list[int] | None,
    expected_site_ids: list[int] | None,
):
    params = {}
    if start is not None:
        params["start"] = start
    if limit is not None:
        params["limit"] = limit

    resp = await admin_client_auth.get(SiteGroupAssignmentsListUri.format(group_name=group_name), params=params)

    if expected_assignment_ids is None:
        assert resp.status_code == HTTPStatus.NOT_FOUND
        return

    assert resp.status_code == HTTPStatus.OK
    page = SiteGroupAssignmentPageResponse(**json.loads(read_response_body_string(resp)))
    assert all(isinstance(a, SiteGroupAssignmentResponse) for a in page.assignments)
    assert [a.site_group_assignment_id for a in page.assignments] == expected_assignment_ids
    assert [a.site_id for a in page.assignments] == expected_site_ids

    async with generate_async_session(pg_base_config) as session:
        group = (await session.execute(select(SiteGroup).where(SiteGroup.name == group_name))).scalar_one()
        expected_total = await count_all_site_group_assignments(session, group.site_group_id)
    assert page.total_count == expected_total


@pytest.mark.parametrize(
    "group_name, site_group_assignment_id, expected_site_id",
    [
        ("Group-1", 1, 1),
        ("Group-1", 2, 2),
        ("Group-2", 4, 1),
        ("Group-1", 4, None),  # assignment 4 belongs to Group-2, not Group-1
        ("Group-1", 9999, None),
        ("Group-DNE", 1, None),
    ],
)
@pytest.mark.anyio
async def test_get_group_assignment(
    admin_client_auth: AsyncClient, group_name: str, site_group_assignment_id: int, expected_site_id: int | None
):
    resp = await admin_client_auth.get(
        SiteGroupAssignmentsUri.format(group_name=group_name, site_group_assignment_id=site_group_assignment_id)
    )

    if expected_site_id is None:
        assert resp.status_code == HTTPStatus.NOT_FOUND
    else:
        assert resp.status_code == HTTPStatus.OK
        assignment = SiteGroupAssignmentResponse(**json.loads(read_response_body_string(resp)))
        assert assignment.site_group_assignment_id == site_group_assignment_id
        assert assignment.site_id == expected_site_id


@pytest.mark.anyio
async def test_create_group_assignment(admin_client_auth: AsyncClient, pg_base_config):
    assignment_request = SiteGroupAssignmentRequest(site_id=6)
    resp = await admin_client_auth.post(
        SiteGroupAssignmentsListUri.format(group_name="Group-3"), content=assignment_request.model_dump_json()
    )
    assert resp.status_code == HTTPStatus.CREATED

    location = resp.headers["Location"]
    [assignments_uri, new_id] = location.rsplit("/", maxsplit=1)
    assert assignments_uri == SiteGroupAssignmentsListUri.format(group_name="Group-3")
    assert int(new_id) > 6

    async with generate_async_session(pg_base_config) as session:
        group = (await session.execute(select(SiteGroup).where(SiteGroup.name == "Group-3"))).scalar_one()
        created = (
            await session.execute(
                select(SiteGroupAssignment).where(
                    SiteGroupAssignment.site_group_assignment_id == int(new_id),
                )
            )
        ).scalar_one()
        assert created.site_id == 6
        assert created.site_group_id == group.site_group_id
        assert_nowish(created.changed_time)


@pytest.mark.anyio
async def test_create_group_assignment_group_not_found(admin_client_auth: AsyncClient):
    assignment_request = SiteGroupAssignmentRequest(site_id=1)
    resp = await admin_client_auth.post(
        SiteGroupAssignmentsListUri.format(group_name="Group-DNE"), content=assignment_request.model_dump_json()
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize("site_id", [1, 9999])  # 1 is already a member of Group-1, 9999 doesn't exist
@pytest.mark.anyio
async def test_create_group_assignment_bad_request(admin_client_auth: AsyncClient, pg_base_config, site_id: int):
    assignment_request = SiteGroupAssignmentRequest(site_id=site_id)
    resp = await admin_client_auth.post(
        SiteGroupAssignmentsListUri.format(group_name="Group-1"), content=assignment_request.model_dump_json()
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST

    async with generate_async_session(pg_base_config) as session:
        group = (await session.execute(select(SiteGroup).where(SiteGroup.name == "Group-1"))).scalar_one()
        assert (await count_all_site_group_assignments(session, group.site_group_id)) == 3, (
            "No new assignment should've been created"
        )


@pytest.mark.anyio
async def test_delete_group_assignment(admin_client_auth: AsyncClient, pg_base_config):
    resp = await admin_client_auth.delete(
        SiteGroupAssignmentsUri.format(group_name="Group-1", site_group_assignment_id=1)
    )
    assert resp.status_code == HTTPStatus.NO_CONTENT

    async with generate_async_session(pg_base_config) as session:
        remaining = (
            await session.execute(
                select(SiteGroupAssignment).where(SiteGroupAssignment.site_group_assignment_id == 1)
            )
        ).scalar_one_or_none()
        assert remaining is None

    # Subsequent delete/get now both 404
    resp = await admin_client_auth.delete(
        SiteGroupAssignmentsUri.format(group_name="Group-1", site_group_assignment_id=1)
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND

    resp = await admin_client_auth.get(SiteGroupAssignmentsUri.format(group_name="Group-1", site_group_assignment_id=1))
    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    "group_name, site_group_assignment_id",
    [
        ("Group-1", 9999),  # assignment DNE
        ("Group-1", 4),  # assignment exists but belongs to Group-2
        ("Group-DNE", 1),  # group DNE
    ],
)
@pytest.mark.anyio
async def test_delete_group_assignment_not_found(
    admin_client_auth: AsyncClient, group_name: str, site_group_assignment_id: int
):
    resp = await admin_client_auth.delete(
        SiteGroupAssignmentsUri.format(group_name=group_name, site_group_assignment_id=site_group_assignment_id)
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
