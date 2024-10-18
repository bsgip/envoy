from datetime import datetime, timezone
from http import HTTPStatus
from itertools import product
from typing import Optional

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_datetime_equal, assert_nowish
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from envoy_schema.admin.schema.log import (
    CalculationLogListResponse,
    CalculationLogMetadata,
    CalculationLogRequest,
    CalculationLogResponse,
    CalculationLogVariableValues,
)
from envoy_schema.admin.schema.uri import CalculationLogCreateUri, CalculationLogsForPeriod, CalculationLogUri
from httpx import AsyncClient

from envoy.server.api.response import LOCATION_HEADER_NAME


def assert_calc_log_2(calc_log_2: CalculationLogResponse) -> None:
    assert calc_log_2 is not None and isinstance(calc_log_2, CalculationLogResponse)
    assert calc_log_2.external_id == "external-id-2"
    assert_datetime_equal(calc_log_2.calculation_range_start, datetime(2024, 1, 31, 1, 2, 3, tzinfo=timezone.utc))
    assert calc_log_2.calculation_range_duration_seconds == 86402

    assert_list_type(CalculationLogMetadata, calc_log_2.variable_metadata, count=3)
    assert isinstance(calc_log_2.variable_values, CalculationLogVariableValues)

    assert calc_log_2.variable_values.variable_ids == [1, 1, 1, 2, 3, 3]
    assert calc_log_2.variable_values.site_ids == [None, None, None, 2, 1, 1]
    assert calc_log_2.variable_values.interval_periods == [0, 1, 2, 0, 0, 1]
    assert calc_log_2.variable_values.values == [3.3, 2.2, 4.4, -5.5, 0, 1.1]


@pytest.mark.anyio
async def test_get_calculation_log_by_id(admin_client_auth: AsyncClient):
    resp = await admin_client_auth.get(CalculationLogUri.format(calculation_log_id=2))
    assert resp.status_code == HTTPStatus.OK

    calc_log_2 = CalculationLogResponse.model_validate_json(resp.content)
    assert_calc_log_2(calc_log_2)


@pytest.mark.anyio
async def test_get_calculation_log_by_id_missing(admin_client_auth: AsyncClient):
    resp = await admin_client_auth.get(CalculationLogUri.format(calculation_log_id=4))
    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize("optional_is_none, include_children", product([True, False], [True, False]))
@pytest.mark.anyio
async def test_calculation_log_roundtrip_with_children(
    admin_client_auth: AsyncClient, optional_is_none: bool, include_children: bool
):
    """Creates a calculation log - sends it off, pulls it back and ensures the contents is all still the same"""
    var_mds = [generate_class_instance(CalculationLogMetadata, optional_is_none=optional_is_none)]
    var_vals = generate_class_instance(CalculationLogVariableValues, optional_is_none=optional_is_none)

    calc_log: CalculationLogRequest = generate_class_instance(CalculationLogRequest, optional_is_none=optional_is_none)
    if include_children:
        calc_log.variable_metadata = var_mds
        calc_log.variable_values = var_vals

    # Upload the log
    resp = await admin_client_auth.post(CalculationLogCreateUri, content=calc_log.model_dump_json())
    assert resp.status_code == HTTPStatus.CREATED
    uri = resp.headers[LOCATION_HEADER_NAME]
    assert uri

    # download the log
    resp = await admin_client_auth.get(uri)
    assert resp.status_code == HTTPStatus.OK

    # Validate the response
    returned_log = CalculationLogResponse.model_validate_json(resp.content)
    assert_class_instance_equality(CalculationLogRequest, calc_log, returned_log)
    assert_nowish(returned_log.created_time)
    if include_children:
        assert len(returned_log.variable_metadata) == len(var_mds)
        assert_class_instance_equality(CalculationLogMetadata, var_mds[0], returned_log.variable_metadata[0])

        assert_class_instance_equality(CalculationLogVariableValues, var_vals, returned_log.variable_values)
    else:
        assert len(returned_log.variable_metadata) == 0

        assert len(returned_log.variable_values.variable_ids) == 0
        assert len(returned_log.variable_values.site_ids) == 0
        assert len(returned_log.variable_values.interval_periods) == 0
        assert len(returned_log.variable_values.values) == 0


@pytest.mark.parametrize(
    "period_start, period_end, start, limit, expected_ids, expected_count",
    [
        (
            "2023-09-08T00:00+10:00",
            "2023-09-09T00:00+10:00",
            None,
            None,
            [],
            0,
        ),  # Too early
        (
            "2023-09-11T00:00+10:00",
            "2023-09-12T00:00+10:00",
            0,
            None,
            [],
            0,
        ),  # Too late
        (
            "2023-09-08T00:00+10:00",
            "2023-09-12T00:00+10:00",
            None,
            5,
            [4, 5, 6, 7],
            4,
        ),  # Perfectly match 2 day Range
        (
            "2023-09-08T00:00+10:00",
            "2023-09-12T00:00+10:00",
            1,
            2,
            [5, 6],
            4,
        ),  # Paging
    ],
)
@pytest.mark.anyio
async def test_get_calculation_logs_for_period(
    pg_billing_data,
    admin_client_auth: AsyncClient,
    period_start: str,
    period_end: str,
    start: Optional[int],
    limit: Optional[int],
    expected_ids: list[int],
    expected_count: int,
):
    uri = CalculationLogsForPeriod.format(period_start=period_start, period_end=period_end) + "?"
    if start is not None:
        uri += f"&start={start}"
    if limit is not None:
        uri += f"&limit={limit}"
    resp = await admin_client_auth.get(uri)
    assert resp.status_code == HTTPStatus.OK

    log_list = CalculationLogListResponse.model_validate_json(resp.content)
    assert log_list.total_calculation_logs == expected_count
    assert log_list.start == (start if start is not None else 0)
    assert log_list.limit == (limit if limit is not None else 100)
    assert all([isinstance(cl, CalculationLogResponse) for cl in log_list.calculation_logs])
    assert all([cl.variable_metadata == [] for cl in log_list.calculation_logs]), "No child logs in list endpoint"
    assert all([cl.variable_values is None for cl in log_list.calculation_logs]), "No child logs in list endpoint"
    assert [cl.calculation_log_id for cl in log_list.calculation_logs] == expected_ids
