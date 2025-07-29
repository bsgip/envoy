import json
from datetime import datetime, timezone
from decimal import Decimal
from http import HTTPStatus
from typing import Optional
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_nowish
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.site_control import (
    SiteControlGroupPageResponse,
    SiteControlGroupRequest,
    SiteControlGroupResponse,
    SiteControlPageResponse,
    SiteControlRequest,
    SiteControlResponse,
)
from envoy_schema.admin.schema.uri import (
    SiteControlGroupListUri,
    SiteControlGroupUri,
    SiteControlRangeUri,
    SiteControlUri,
)
from httpx import AsyncClient
from sqlalchemy import func, select

from envoy.admin.crud.doe import count_all_does, count_all_site_control_groups
from envoy.server.api.request import MAX_LIMIT
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.doe import DynamicOperatingEnvelope
from tests.integration.admin.test_site import _build_query_string
from tests.integration.response import read_location_header, read_response_body_string


@pytest.mark.anyio
async def test_create_site_control_group(admin_client_auth: AsyncClient):
    """Tests that site control groups can be created and then fetched"""
    group_request = generate_class_instance(SiteControlGroupRequest)
    resp = await admin_client_auth.post(SiteControlGroupListUri, content=group_request.model_dump_json())

    assert resp.status_code == HTTPStatus.CREATED
    location_header = read_location_header(resp)

    # Check we can fetch it
    resp = await admin_client_auth.get(location_header)
    assert resp.status_code == HTTPStatus.OK
    body = read_response_body_string(resp)
    assert len(body) > 0
    group_response: SiteControlGroupResponse = SiteControlGroupResponse(**json.loads(body))

    assert_nowish(group_response.changed_time)
    assert_nowish(group_response.created_time)
    assert_class_instance_equality(SiteControlGroupRequest, group_request, group_response)


@pytest.mark.parametrize("site_control_group_id, expected_primacy", [(1, 0), (99, None)])
@pytest.mark.anyio
async def test_get_site_control_group_by_id(
    admin_client_auth: AsyncClient, site_control_group_id: int, expected_primacy: Optional[int]
):
    """Tests that site control groups can be created and then fetched"""

    # Check we can fetch it
    resp = await admin_client_auth.get(SiteControlGroupUri.format(group_id=site_control_group_id))
    if expected_primacy is None:
        assert resp.status_code == HTTPStatus.NOT_FOUND
    else:
        assert resp.status_code == HTTPStatus.OK
        body = read_response_body_string(resp)
        assert len(body) > 0
        group_response: SiteControlGroupResponse = SiteControlGroupResponse(**json.loads(body))

        assert group_response.site_control_group_id == site_control_group_id
        assert group_response.primacy == expected_primacy


@pytest.mark.parametrize(
    "start, limit, after, expected_group_ids",
    [
        (None, None, None, [1]),
        (1, None, None, []),
        (0, 1, None, [1]),
        (0, 0, None, []),
        (None, None, datetime(2021, 4, 5, 10, 1, 0, 500000, tzinfo=timezone.utc), [1]),
        (None, None, datetime(2021, 4, 5, 10, 2, 0, 500000, tzinfo=timezone.utc), []),
    ],
)
@pytest.mark.anyio
async def test_get_all_site_control_groups(
    admin_client_auth: AsyncClient,
    pg_base_config,
    start: Optional[int],
    limit: Optional[int],
    after: Optional[datetime],
    expected_group_ids: list[int],
):
    """Sanity check on the Fetch site control groups endpoint"""
    async with generate_async_session(pg_base_config) as session:
        expected_total_groups = await count_all_site_control_groups(session, after)

    response = await admin_client_auth.get(SiteControlGroupListUri + _build_query_string(start, limit, None, after))
    assert response.status_code == HTTPStatus.OK

    body = read_response_body_string(response)
    assert len(body) > 0
    group_page: SiteControlGroupPageResponse = SiteControlGroupPageResponse(**json.loads(body))

    assert isinstance(group_page.limit, int)
    assert isinstance(group_page.total_count, int)
    assert isinstance(group_page.start, int)
    if after is None:
        assert group_page.after is None
    else:
        assert isinstance(group_page.after, datetime)
    assert group_page.total_count == expected_total_groups
    if start is None:
        assert group_page.start == 0
    else:
        assert group_page.start == start
    if limit is None:
        assert group_page.limit == 100  # Default limit
    elif limit <= MAX_LIMIT:
        assert group_page.limit == limit
    else:
        assert group_page.limit == MAX_LIMIT

    assert_list_type(SiteControlGroupResponse, group_page.site_control_groups, len(expected_group_ids))
    assert expected_group_ids == [g.site_control_group_id for g in group_page.site_control_groups]


@pytest.mark.anyio
async def test_create_site_controls(admin_client_auth: AsyncClient):
    control_1 = generate_class_instance(SiteControlRequest, site_id=1)
    control_2 = generate_class_instance(SiteControlRequest, site_id=2)

    resp = await admin_client_auth.post(
        SiteControlUri.format(group_id=1), content=f"[{control_1.model_dump_json()}, {control_2.model_dump_json()}]"
    )

    assert resp.status_code == HTTPStatus.CREATED


@pytest.mark.anyio
async def test_create_site_controls_bad_group_id(admin_client_auth: AsyncClient):
    control = generate_class_instance(SiteControlRequest, site_id=1)
    resp = await admin_client_auth.post(SiteControlUri.format(group_id=99), content=f"[{control.model_dump_json()}]")
    assert resp.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.anyio
async def test_supersede_site_control(pg_base_config, admin_client_auth: AsyncClient):
    """Checks that creating a new site control that overlaps at existing one (with priority) will mark the old
    record as superseded"""
    # Check the DB
    async with generate_async_session(pg_base_config) as session:
        stmt = select(func.count()).select_from(DynamicOperatingEnvelope)
        resp = await session.execute(stmt)
        initial_count = resp.scalar_one()

    # This should be superseding doe 1 (doe1 fully encapsulates it)
    updated_rate = SiteControlRequest(
        site_id=1,
        start_time=datetime(2022, 5, 7, 1, 2, 2, tzinfo=ZoneInfo("Australia/Brisbane")),
        duration_seconds=5,
        calculation_log_id=3,  # This is how we'll look this record up in the DB later
        export_limit_watts=44,
        import_limit_watts=55,
    )

    resp = await admin_client_auth.post(
        SiteControlUri.format(group_id=1),
        content=f"[{updated_rate.model_dump_json()}]",
    )

    assert resp.status_code == HTTPStatus.CREATED

    # Check the DB
    async with generate_async_session(pg_base_config) as session:
        after_count = (await session.execute(select(func.count()).select_from(DynamicOperatingEnvelope))).scalar_one()

        assert (initial_count + 1) == after_count, "This should've been an insert"

        # doe_1 should be marked as superseded but otherwise unchanged
        doe_1 = (
            await session.execute(
                select(DynamicOperatingEnvelope).where(DynamicOperatingEnvelope.dynamic_operating_envelope_id == 1)
            )
        ).scalar_one()
        assert doe_1.import_limit_active_watts == Decimal("1.11"), "unchanged"
        assert doe_1.export_limit_watts == Decimal("-1.22"), "unchanged"
        assert doe_1.superseded is True
        assert_nowish(doe_1.changed_time)
        assert doe_1.created_time == datetime(2000, 1, 1, tzinfo=timezone.utc), "unchanged"

        inserted_doe = (
            await session.execute(
                select(DynamicOperatingEnvelope).where(DynamicOperatingEnvelope.calculation_log_id == 3)
            )
        ).scalar_one()

        assert inserted_doe.calculation_log_id == updated_rate.calculation_log_id
        assert inserted_doe.start_time == updated_rate.start_time
        assert inserted_doe.duration_seconds == updated_rate.duration_seconds
        assert_nowish(inserted_doe.changed_time)
        assert_nowish(inserted_doe.created_time)
        assert inserted_doe.import_limit_active_watts == updated_rate.import_limit_watts
        assert inserted_doe.export_limit_watts == updated_rate.export_limit_watts
        assert inserted_doe.superseded is False

        assert inserted_doe.changed_time == doe_1.changed_time, "Changed in the same operation"

        assert (
            await session.execute(select(func.count()).select_from(ArchiveDynamicOperatingEnvelope))
        ).scalar_one() == 1, "The old updated record should be archived. Unit tests will test this in more detail"


@pytest.mark.parametrize(
    "site_control_group_id, start, limit, after, expected_doe_ids",
    [
        (
            1,
            None,
            None,
            None,
            [1, 2, 3, 4],
        ),
        (
            1,
            None,
            99,
            None,
            [1, 2, 3, 4],
        ),
        (
            1,
            1,
            2,
            None,
            [2, 3],
        ),
        (
            1,
            1,
            2,
            None,
            [2, 3],
        ),
        (
            1,
            None,
            9999,
            None,
            [1, 2, 3, 4],
        ),
        (
            1,
            None,
            99,
            datetime(2022, 5, 6, 12, 22, 34, tzinfo=timezone.utc),
            [3, 4],
        ),
        (
            1,
            1,
            99,
            datetime(2022, 5, 6, 12, 22, 34, tzinfo=timezone.utc),
            [4],
        ),
        (
            2,
            1,
            99,
            datetime(2022, 5, 6, 12, 22, 34, tzinfo=timezone.utc),
            [],
        ),  # Change site control group id
    ],
)
@pytest.mark.anyio
async def test_get_all_site_controls(
    admin_client_auth: AsyncClient,
    pg_base_config,
    site_control_group_id,
    start: Optional[int],
    limit: Optional[int],
    after: Optional[datetime],
    expected_doe_ids: list[int],
):
    """Sanity check on the Fetch DOE endpoint"""
    async with generate_async_session(pg_base_config) as session:
        expected_total_does = await count_all_does(session, site_control_group_id, after)

    response = await admin_client_auth.get(
        SiteControlUri.format(group_id=site_control_group_id) + _build_query_string(start, limit, None, after)
    )
    assert response.status_code == HTTPStatus.OK

    body = read_response_body_string(response)
    assert len(body) > 0
    site_page: SiteControlPageResponse = SiteControlPageResponse(**json.loads(body))

    assert isinstance(site_page.limit, int)
    assert isinstance(site_page.total_count, int)
    assert isinstance(site_page.start, int)
    if after is None:
        assert site_page.after is None
    else:
        assert isinstance(site_page.after, datetime)
    assert site_page.total_count == expected_total_does
    if start is None:
        assert site_page.start == 0
    else:
        assert site_page.start == start
    if limit is None:
        assert site_page.limit == 100  # Default limit
    elif limit <= MAX_LIMIT:
        assert site_page.limit == limit
    else:
        assert site_page.limit == MAX_LIMIT

    assert_list_type(SiteControlResponse, site_page.controls, len(expected_doe_ids))
    assert expected_doe_ids == [d.site_control_id for d in site_page.controls]


@pytest.mark.parametrize(
    "site_control_group_id, period_start_str, period_end_str, expected_doe_ids",
    [
        (
            1,
            "2022-05-07T01:02:00+10:00",
            "2023-05-07T01:02:00+10:00",
            [1, 2, 3, 4],
        ),
        (
            2,
            "2022-05-07T01:02:00+10:00",
            "2023-05-07T01:02:00+10:00",
            [],
        ),
        (
            1,
            "2022-05-07T01:02:00+10:00",
            "2022-05-07T02:02:00+10:00",
            [1, 3],
        ),
    ],
)
@pytest.mark.anyio
async def test_delete_does_in_range(
    admin_client_auth: AsyncClient,
    pg_base_config,
    site_control_group_id: int,
    period_start_str: str,
    period_end_str: str,
    expected_doe_ids: list[int],
):
    """Sanity check on the Fetch DOE endpoint"""
    async with generate_async_session(pg_base_config) as session:
        before_doe_count = await count_all_does(session, site_control_group_id, None)

    response = await admin_client_auth.delete(
        SiteControlRangeUri.format(
            group_id=site_control_group_id, period_start=period_start_str, period_end=period_end_str
        )
    )
    assert response.status_code == HTTPStatus.NO_CONTENT

    async with generate_async_session(pg_base_config) as session:
        deleted_does = (
            (
                await session.execute(
                    select(ArchiveDynamicOperatingEnvelope)
                    .where(ArchiveDynamicOperatingEnvelope.deleted_time.is_not(None))
                    .order_by(ArchiveDynamicOperatingEnvelope.dynamic_operating_envelope_id)
                )
            )
            .scalars()
            .all()
        )
        deleted_doe_ids = [d.dynamic_operating_envelope_id for d in deleted_does]
        assert deleted_doe_ids == expected_doe_ids

        assert (before_doe_count - len(deleted_doe_ids)) == (await count_all_does(session, site_control_group_id, None))
