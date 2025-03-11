from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.type import assert_list_type
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.response import ResponseType

from envoy.server.crud.response import (
    count_doe_responses,
    count_tariff_generated_rate_responses,
    select_doe_response_for_scope,
    select_doe_responses,
    select_rate_response_for_scope,
    select_tariff_generated_rate_responses,
)
from envoy.server.model.response import DynamicOperatingEnvelopeResponse, TariffGeneratedRateResponse
from envoy.server.model.site import Site


@pytest.mark.parametrize(
    "agg_id, site_id, start, limit, after, expected_count, expected_ids_with_site_id",
    [
        (1, None, 0, 99, datetime.min, 3, [(3, 2), (2, 1), (1, 1)]),
        (1, 1, 0, 99, datetime.min, 2, [(2, 1), (1, 1)]),
        (1, 2, 0, 99, datetime.min, 1, [(3, 2)]),
        (1, None, 1, 99, datetime.min, 3, [(2, 1), (1, 1)]),  # Testing skip
        (1, None, 2, 99, datetime.min, 3, [(1, 1)]),  # Testing skip
        (1, None, 3, 99, datetime.min, 3, []),  # Testing skip
        (1, None, 0, 2, datetime.min, 3, [(3, 2), (2, 1)]),  # Testing limit
        (1, None, 1, 1, datetime.min, 3, [(2, 1)]),  # Testing limit + skip
        (
            1,
            None,
            0,
            99,
            datetime(2023, 1, 1, 12, 0, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            2,
            [(3, 2), (2, 1)],
        ),  # Created time will skip the first record
        (
            1,
            1,
            0,
            99,
            datetime(2023, 1, 1, 12, 0, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            [(2, 1)],
        ),  # Created time will skip the first record
        (2, None, 0, 99, datetime.min, 0, []),  # Empty agg ID
        (99, None, 0, 99, datetime.min, 0, []),  # Bad agg ID
        (99, None, 0, 99, datetime(2025, 1, 2), 0, []),  # Created time after everything
    ],
)
@pytest.mark.anyio
async def test_select_and_count_doe_response_filters(
    pg_base_config,
    agg_id: int,
    site_id: Optional[int],
    start: int,
    limit: int,
    after: datetime,
    expected_count: int,
    expected_ids_with_site_id: list[tuple[int, int]],
):
    """Performs select_doe_responses and count_doe_responses behave correctly for various combinations of filters

    expected_ids_with_site_id is a tuple of (response_id, site_id)"""
    async with generate_async_session(pg_base_config) as session:
        actual_responses = await select_doe_responses(session, agg_id, site_id, start, limit, after)
        assert_list_type(DynamicOperatingEnvelopeResponse, actual_responses, len(expected_ids_with_site_id))
        assert_list_type(Site, [e.site for e in actual_responses], len(expected_ids_with_site_id))
        assert [e.dynamic_operating_envelope_response_id for e in actual_responses] == [
            t[0] for t in expected_ids_with_site_id
        ]
        assert [e.site.site_id for e in actual_responses] == [t[1] for t in expected_ids_with_site_id]

        actual_count = await count_doe_responses(session, agg_id, site_id, after)
        assert isinstance(actual_count, int)
        assert actual_count == expected_count


@pytest.mark.parametrize(
    "agg_id, site_id, start, limit, after, expected_count, expected_ids_with_site_id",
    [
        (1, None, 0, 99, datetime.min, 3, [(3, 2), (2, 1), (1, 1)]),
        (1, 1, 0, 99, datetime.min, 2, [(2, 1), (1, 1)]),
        (1, 2, 0, 99, datetime.min, 1, [(3, 2)]),
        (1, None, 1, 99, datetime.min, 3, [(2, 1), (1, 1)]),  # Testing skip
        (1, None, 2, 99, datetime.min, 3, [(1, 1)]),  # Testing skip
        (1, None, 3, 99, datetime.min, 3, []),  # Testing skip
        (1, None, 0, 2, datetime.min, 3, [(3, 2), (2, 1)]),  # Testing limit
        (1, None, 1, 1, datetime.min, 3, [(2, 1)]),  # Testing limit + skip
        (
            1,
            None,
            0,
            99,
            datetime(2022, 1, 1, 12, 0, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            2,
            [(3, 2), (2, 1)],
        ),  # Created time will skip the first record
        (
            1,
            1,
            0,
            99,
            datetime(2022, 1, 1, 12, 0, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            1,
            [(2, 1)],
        ),  # Created time will skip the first record
        (2, None, 0, 99, datetime.min, 0, []),  # Empty agg ID
        (99, None, 0, 99, datetime.min, 0, []),  # Bad agg ID
        (99, None, 0, 99, datetime(2025, 1, 2), 0, []),  # Created time after everything
    ],
)
@pytest.mark.anyio
async def test_select_and_count_rate_response_filters(
    pg_base_config,
    agg_id: int,
    site_id: Optional[int],
    start: int,
    limit: int,
    after: datetime,
    expected_count: int,
    expected_ids_with_site_id: list[tuple[int, int]],
):
    """Performs select_tariff_generated_rate_responses and count_tariff_generated_rate_responses behave correctly
    for various combinations of filters

    expected_ids_with_site_id is a tuple of (response_id, site_id)"""
    async with generate_async_session(pg_base_config) as session:
        actual_responses = await select_tariff_generated_rate_responses(session, agg_id, site_id, start, limit, after)
        assert_list_type(TariffGeneratedRateResponse, actual_responses, len(expected_ids_with_site_id))
        assert_list_type(Site, [e.site for e in actual_responses], len(expected_ids_with_site_id))
        assert [e.tariff_generated_rate_response_id for e in actual_responses] == [
            t[0] for t in expected_ids_with_site_id
        ]
        assert [e.site.site_id for e in actual_responses] == [t[1] for t in expected_ids_with_site_id]

        actual_count = await count_tariff_generated_rate_responses(session, agg_id, site_id, after)
        assert isinstance(actual_count, int)
        assert actual_count == expected_count


@pytest.mark.parametrize(
    "agg_id, site_id, pk_id, expected_response_type, expected_site_id",
    [
        (1, None, 1, ResponseType.EVENT_COMPLETED, 1),
        (1, 1, 1, ResponseType.EVENT_COMPLETED, 1),
        (1, None, 2, None, 1),
        (1, 1, 2, None, 1),
        (1, None, 3, ResponseType.USER_CHOSE_OPT_OUT, 2),
        (1, 2, 3, ResponseType.USER_CHOSE_OPT_OUT, 2),
        (1, 2, 1, None, None),  # bad site id
        (1, 99, 1, None, None),  # invalid site id
        (2, None, 1, None, None),  # bad agg ID
        (99, None, 1, None, None),  # invalid agg ID
    ],
)
@pytest.mark.anyio
async def test_select_doe_response_for_scope(
    pg_base_config,
    agg_id: int,
    site_id: Optional[int],
    pk_id: int,
    expected_response_type: Optional[ResponseType],
    expected_site_id: Optional[int],
):
    """Checks that fetching DOE responses by ID works with the various scoping options"""
    async with generate_async_session(pg_base_config) as session:
        actual = await select_doe_response_for_scope(session, agg_id, site_id, pk_id)

        if expected_site_id is None:
            assert actual is None
        else:
            assert isinstance(actual, DynamicOperatingEnvelopeResponse)
            assert isinstance(actual.site, Site), "Site relationship should populate"
            assert actual.site.site_id == expected_site_id
            assert actual.dynamic_operating_envelope_response_id == pk_id
            assert actual.site_id == expected_site_id
            assert actual.response_type == expected_response_type


@pytest.mark.parametrize(
    "agg_id, site_id, pk_id, expected_response_type, expected_site_id",
    [
        (1, None, 1, ResponseType.EVENT_RECEIVED, 1),
        (1, 1, 1, ResponseType.EVENT_RECEIVED, 1),
        (1, None, 2, None, 1),
        (1, 1, 2, None, 1),
        (1, None, 3, ResponseType.EVENT_STARTED, 2),
        (1, 2, 3, ResponseType.EVENT_STARTED, 2),
        (1, 2, 1, None, None),  # bad site id
        (1, 99, 1, None, None),  # invalid site id
        (2, None, 1, None, None),  # bad agg ID
        (99, None, 1, None, None),  # invalid agg ID
    ],
)
@pytest.mark.anyio
async def test_select_rate_response_for_scope(
    pg_base_config,
    agg_id: int,
    site_id: Optional[int],
    pk_id: int,
    expected_response_type: Optional[ResponseType],
    expected_site_id: Optional[int],
):
    """Checks that fetching rate responses by ID works with the various scoping options"""
    async with generate_async_session(pg_base_config) as session:
        actual = await select_rate_response_for_scope(session, agg_id, site_id, pk_id)

        if expected_site_id is None:
            assert actual is None
        else:
            assert isinstance(actual, TariffGeneratedRateResponse)
            assert isinstance(actual.site, Site), "Site relationship should populate"
            assert actual.site.site_id == expected_site_id
            assert actual.tariff_generated_rate_response_id == pk_id
            assert actual.site_id == expected_site_id
            assert actual.response_type == expected_response_type
