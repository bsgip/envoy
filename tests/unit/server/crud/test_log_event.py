from datetime import datetime
from typing import Optional

import pytest
from assertical.asserts.type import assert_list_type
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.log_events import FunctionSetIdentifier

from envoy.server.crud.log_event import count_site_log_events, select_log_event_for_scope, select_site_log_events
from envoy.server.model.site import SiteLogEvent


@pytest.mark.parametrize(
    "agg_id, site_id, start, limit, after, expected_count, expected_ids",
    [
        (1, None, 0, 99, datetime.min, 4, [5, 3, 2, 1]),
        (1, 1, 0, 99, datetime.min, 3, [5, 2, 1]),
        (1, 2, 0, 99, datetime.min, 1, [3]),
        (1, None, 2, 99, datetime.min, 4, [2, 1]),  # Pagination test case
        (1, None, 1, 2, datetime.min, 4, [3, 2]),  # Pagination test case
        (1, None, 4, 99, datetime.min, 4, []),  # Pagination test case
        (1, 1, 2, 1, datetime.min, 3, [1]),  # Pagination test case
        (1, 3, 0, 99, datetime.min, 0, []),  # Site ID not accessible to Agg
        (99, None, 0, 99, datetime.min, 0, []),  # Bad Agg ID
        (1, 99, 0, 99, datetime.min, 0, []),  # Missing site ID
    ],
)
@pytest.mark.anyio
async def test_select_and_count_site_log_event_filters(
    pg_base_config,
    agg_id: int,
    site_id: Optional[int],
    start: int,
    limit: int,
    after: datetime,
    expected_count: int,
    expected_ids: list[int],
):
    """Performs select_site_log_events and count_site_log_events behave correctly for various
    combinations of filters"""
    async with generate_async_session(pg_base_config) as session:
        actual_log_events = await select_site_log_events(session, agg_id, site_id, start, limit, after)
        assert_list_type(SiteLogEvent, actual_log_events, len(expected_ids))
        assert [e.site_log_event_id for e in actual_log_events] == expected_ids

        actual_count = await count_site_log_events(session, agg_id, site_id, after)
        assert isinstance(actual_count, int)
        assert actual_count == expected_count


@pytest.mark.parametrize(
    "agg_id, site_id, pk_id, expected_fs, expected_details, expected_extended_data",
    [
        (1, None, 1, FunctionSetIdentifier.PUBLISH_AND_SUBSCRIBE, "log-1", 11),
        (1, 1, 1, FunctionSetIdentifier.PUBLISH_AND_SUBSCRIBE, "log-1", 11),
        (2, None, 4, FunctionSetIdentifier.RESPONSE, "log-4", 41),
        (2, 3, 4, FunctionSetIdentifier.RESPONSE, "log-4", 41),
        (1, None, 5, FunctionSetIdentifier.DEMAND_RESPONSE_LOAD_CONTROL, None, None),
        (3, None, 1, None, None, None),  # Wrong Agg
        (99, None, 1, None, None, None),  # Bad Agg
        (1, 2, 1, None, None, None),  # Wrong site ID
        (1, 3, 1, None, None, None),  # Wrong site ID
        (1, None, 99, None, None, None),  # Bad primary key
    ],
)
@pytest.mark.anyio
async def test_select_log_event_for_scope(
    pg_base_config,
    agg_id: int,
    site_id: Optional[int],
    pk_id: int,
    expected_fs: Optional[FunctionSetIdentifier],
    expected_details: Optional[str],
    expected_extended_data: Optional[int],
):
    """Checks that fetching log events by ID works with the various scoping options"""
    async with generate_async_session(pg_base_config) as session:
        actual = await select_log_event_for_scope(session, agg_id, site_id, pk_id)

        if expected_fs is None:
            assert actual is None
        else:
            assert isinstance(actual, SiteLogEvent)
            assert actual.site_log_event_id == pk_id
            assert actual.function_set == expected_fs
            assert actual.details == expected_details
            assert actual.extended_data == expected_extended_data
