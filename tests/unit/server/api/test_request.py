from datetime import date, datetime, timezone
from typing import Optional

import pytest

from envoy.server.api.request import (
    DEFAULT_DATETIME,
    DEFAULT_LIMIT,
    DEFAULT_START,
    MAX_LIMIT,
    extract_date_from_iso_string,
    extract_datetime_from_paging_param,
    extract_limit_from_paging_param,
    extract_start_from_paging_param,
)


@pytest.mark.parametrize(
    "query_val, expected_output",
    [
        ([0], 0),
        ([1], 1),
        ([2], 2),
        ([999999], MAX_LIMIT),
        ([4, 5, 6], 4),
        (None, DEFAULT_LIMIT),
        ([], DEFAULT_LIMIT),
    ],
)
def test_extract_limit_from_paging_param(query_val: Optional[list[int]], expected_output: int):
    assert extract_limit_from_paging_param(query_val) == expected_output


@pytest.mark.parametrize(
    "query_val, expected_output",
    [
        ([0], 0),
        ([1], 1),
        ([2], 2),
        ([999999], 999999),
        ([4, 5, 6], 4),
        (None, DEFAULT_START),
        ([], DEFAULT_START),
    ],
)
def test_extract_start_from_paging_param(query_val: Optional[list[int]], expected_output: int):
    assert extract_start_from_paging_param(query_val) == expected_output


@pytest.mark.parametrize(
    "query_val, expected_output",
    [
        ([0], datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)),
        ([1683074628], datetime(2023, 5, 3, 0, 43, 48, tzinfo=timezone.utc)),
        (None, DEFAULT_DATETIME),
        ([], DEFAULT_DATETIME),
    ],
)
def test_extract_datetime_from_paging_param(query_val: Optional[list[int]], expected_output: datetime):
    assert extract_datetime_from_paging_param(query_val) == expected_output


@pytest.mark.parametrize(
    "input, output",
    [
        ("2022-11-10", date(2022, 11, 10)),
        ("2036-09-30", date(2036, 9, 30)),
        ("1985-01-02", date(1985, 1, 2)),
        ("2020-02-29", date(2020, 2, 29)),
        ("", None),
        ("2022", None),
        ("2022/10/09", None),
        ("2022-11-31", None),  # There is no 31st Nov
        ("2021-02-29", None),  # Not a leap year
        ("2022-Nov-02", None),
        ("2022-1-2", None),
    ],
)
def test_parse_rate_component_id(input: str, output: Optional[date]):
    assert extract_date_from_iso_string(input) == output
