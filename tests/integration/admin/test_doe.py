import json
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Optional

import pytest
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

from envoy.admin.crud.doe import count_all_does
from envoy.server.api.request import MAX_LIMIT
from tests.integration.admin.test_site import _build_query_string
from tests.integration.response import read_response_body_string


@pytest.mark.anyio
async def test_create_does(admin_client_auth: AsyncClient):
    doe = generate_class_instance(DynamicOperatingEnvelopeRequest)
    doe.site_id = 1

    doe_1 = generate_class_instance(DynamicOperatingEnvelopeRequest)
    doe_1.site_id = 2

    resp = await admin_client_auth.post(DoeUri, content=f"[{doe.model_dump_json()}, {doe_1.model_dump_json()}]")

    assert resp.status_code == HTTPStatus.CREATED


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
        expected_total_does = await count_all_does(session, after)

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
