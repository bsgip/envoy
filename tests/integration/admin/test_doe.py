import json
from datetime import datetime, timezone
from decimal import Decimal
from http import HTTPStatus
from typing import Optional
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.time import assert_nowish
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.doe import (
    DoePageResponse,
    DynamicOperatingEnvelopeRequest,
    DynamicOperatingEnvelopeResponse,
)
from envoy_schema.admin.schema.uri import DoeUri
from httpx import AsyncClient
from sqlalchemy import func, select

from envoy.admin.crud.doe import count_all_does
from envoy.admin.mapper.doe import DEFAULT_DOE_SITE_CONTROL_GROUP_ID
from envoy.server.api.request import MAX_LIMIT
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.doe import DynamicOperatingEnvelope
from tests.integration.admin.test_site import _build_query_string
from tests.integration.response import read_response_body_string


@pytest.mark.anyio
async def test_create_does(admin_client_auth: AsyncClient):
    doe: DynamicOperatingEnvelopeRequest = generate_class_instance(DynamicOperatingEnvelopeRequest, site_id=1)
    doe_1: DynamicOperatingEnvelopeRequest = generate_class_instance(DynamicOperatingEnvelopeRequest, site_id=2)

    resp = await admin_client_auth.post(DoeUri, content=f"[{doe.model_dump_json()}, {doe_1.model_dump_json()}]")

    assert resp.status_code == HTTPStatus.CREATED


@pytest.mark.anyio
async def test_supersede_doe(pg_base_config, admin_client_auth: AsyncClient):
    """Checks that inserting a new doe will supersede any others that it overlaps (considering priority)"""
    # Check the DB
    async with generate_async_session(pg_base_config) as session:
        stmt = select(func.count()).select_from(DynamicOperatingEnvelope)
        resp = await session.execute(stmt)
        initial_count = resp.scalar_one()

    # This should be updating doe 1
    new_doe = DynamicOperatingEnvelopeRequest(
        site_id=1,
        start_time=datetime(2022, 5, 7, 1, 2, 3, tzinfo=ZoneInfo("Australia/Brisbane")),
        duration_seconds=2,
        calculation_log_id=3,  # This is how we'll look this record up in the DB later
        export_limit_watts=44,
        import_limit_active_watts=55,
    )

    resp = await admin_client_auth.post(
        DoeUri,
        content=f"[{new_doe.model_dump_json()}]",
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

        assert inserted_doe.calculation_log_id == new_doe.calculation_log_id
        assert inserted_doe.start_time == new_doe.start_time
        assert inserted_doe.duration_seconds == new_doe.duration_seconds
        assert_nowish(inserted_doe.changed_time)
        assert_nowish(inserted_doe.created_time)
        assert inserted_doe.import_limit_active_watts == new_doe.import_limit_active_watts
        assert inserted_doe.export_limit_watts == new_doe.export_limit_watts
        assert inserted_doe.superseded is False

        assert inserted_doe.changed_time == doe_1.changed_time, "Changed in the same operation"

        assert (
            await session.execute(select(func.count()).select_from(ArchiveDynamicOperatingEnvelope))
        ).scalar_one() == 1, "The old updated record should be archived. Unit tests will test this in more detail"


@pytest.mark.parametrize(
    "start, limit, after, expected_doe_ids",
    [
        (
            None,
            None,
            None,
            [1, 2, 3, 4],
        ),
        (
            None,
            99,
            None,
            [1, 2, 3, 4],
        ),
        (
            1,
            2,
            None,
            [2, 3],
        ),
        (
            1,
            2,
            None,
            [2, 3],
        ),
        (
            None,
            9999,
            None,
            [1, 2, 3, 4],
        ),
        (
            None,
            99,
            datetime(2022, 5, 6, 12, 22, 34, tzinfo=timezone.utc),
            [3, 4],
        ),
        (
            1,
            99,
            datetime(2022, 5, 6, 12, 22, 34, tzinfo=timezone.utc),
            [4],
        ),
    ],
)
@pytest.mark.anyio
async def test_get_all_does(
    admin_client_auth: AsyncClient,
    pg_base_config,
    start: Optional[int],
    limit: Optional[int],
    after: Optional[datetime],
    expected_doe_ids: list[int],
):
    """Sanity check on the Fetch DOE endpoint"""
    async with generate_async_session(pg_base_config) as session:
        expected_total_does = await count_all_does(session, DEFAULT_DOE_SITE_CONTROL_GROUP_ID, after)

    response = await admin_client_auth.get(DoeUri + _build_query_string(start, limit, None, after))
    assert response.status_code == HTTPStatus.OK

    body = read_response_body_string(response)
    assert len(body) > 0
    site_page: DoePageResponse = DoePageResponse(**json.loads(body))

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

    assert_list_type(DynamicOperatingEnvelopeResponse, site_page.does, len(expected_doe_ids))
    assert expected_doe_ids == [d.dynamic_operating_envelope_id for d in site_page.does]
