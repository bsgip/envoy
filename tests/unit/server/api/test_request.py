from datetime import datetime, timezone
from typing import Optional

import pytest

from envoy.server.api.request import (
    DEFAULT_DATETIME,
    DEFAULT_LIMIT,
    DEFAULT_START,
    extract_datetime_from_paging_param,
    extract_limit_from_paging_param,
    extract_start_from_paging_param,
)


@pytest.mark.parametrize("query_val, expected_output", [
    ([0], 0),
    ([1], 1),
    ([2], 2),
    ([999999], 999999),
    ([4, 5, 6], 4),

    (None, DEFAULT_LIMIT),
    ([], DEFAULT_LIMIT),
])
def test_extract_limit_from_paging_param(query_val: Optional[list[int]], expected_output: int):
    assert extract_limit_from_paging_param(query_val) == expected_output


@pytest.mark.parametrize("query_val, expected_output", [
    ([0], 0),
    ([1], 1),
    ([2], 2),
    ([999999], 999999),
    ([4, 5, 6], 4),

    (None, DEFAULT_START),
    ([], DEFAULT_START),
])
def test_extract_start_from_paging_param(query_val: Optional[list[int]], expected_output: int):
    assert extract_start_from_paging_param(query_val) == expected_output


@pytest.mark.parametrize("query_val, expected_output", [
    ([0], datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)),
    ([1683074628], datetime(2023, 5, 3, 0, 43, 48, tzinfo=timezone.utc)),

    (None, DEFAULT_DATETIME),
    ([], DEFAULT_DATETIME),
])
def test_extract_datetime_from_paging_param(query_val: Optional[list[int]], expected_output: datetime):
    assert extract_datetime_from_paging_param(query_val) == expected_output
