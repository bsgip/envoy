from datetime import datetime
from typing import Optional

import pytest

from envoy.server.crud.pricing import (
    select_all_tariffs,
    select_single_tariff,
    select_tariff_count,
    select_tariff_rate_for_day_time,
    select_tariff_rates_for_day,
)
from envoy.server.model.site import Site
from envoy.server.schema.sep2.end_device import DeviceCategory
from tests.assert_type import assert_list_type
from tests.data.fake.generator import clone_class_instance, generate_class_instance
from tests.postgres_testing import generate_async_session


@pytest.mark.anyio
async def test_select_tariff_count(pg_base_config):
    """Simple tests to ensure the counts work"""
    async with generate_async_session(pg_base_config) as session:
        # Test the basic config is there and accessible
        assert await select_tariff_count(session, datetime.min) == 3

        # try with after filter being set
        assert await select_tariff_count(session, datetime(2023, 1, 2, 11, 1, 2)) == 3
        assert await select_tariff_count(session, datetime(2023, 1, 2, 11, 1, 3)) == 2
        assert await select_tariff_count(session, datetime(2023, 1, 2, 12, 1, 2)) == 2
        assert await select_tariff_count(session, datetime(2023, 1, 2, 12, 1, 3)) == 1
        assert await select_tariff_count(session, datetime(2023, 1, 2, 13, 1, 2)) == 1
        assert await select_tariff_count(session, datetime(2023, 1, 2, 13, 1, 3)) == 0


@pytest.mark.parametrize(
    "tariff_details",
    [([3, 2, 1], 0, datetime.min, 99),
     ([2, 1], 1, datetime.min, 99),
     ([1], 2, datetime.min, 99),
     ([], 99, datetime.min, 99),
     ([3, 2], 0, datetime.min, 2),
     ([1], 2, datetime.min, 2),
     ([], 3, datetime.min, 2),
     ([3, 2], 0, datetime(2023, 1, 2, 12, 1, 2), 99),
     ([2], 1, datetime(2023, 1, 2, 12, 1, 2), 99),
     ],
)
@pytest.mark.anyio
async def test_select_all_tariffs(pg_base_config, tariff_details: tuple[list[int], int, datetime, int]):
    """Tests that the returned tariffs match what's in the DB"""
    (expected_ids, start, after, limit) = tariff_details

    async with generate_async_session(pg_base_config) as session:
        tariffs = await select_all_tariffs(session, start, after, limit)
        assert len(tariffs) == len(expected_ids)
        assert [t.tariff_id for t in tariffs] == expected_ids

        # check contents of each entry
        for (id, tariff) in zip(expected_ids, tariffs):
            assert tariff.currency_code == id * 10 + id
            assert tariff.dnsp_code == f"tariff-dnsp-code-{id}"
            assert tariff.name == f"tariff-{id}"


@pytest.mark.parametrize(
    "tariff_details",
    [(1, 1),
     (2, 2),
     (3, 3),
     (None, 4),
     (None, 999),
     (None, -1),
     ],
)
@pytest.mark.anyio
async def test_select_single_tariff(pg_base_config, tariff_details: tuple[Optional[int], int]):
    """Tests that singular tariffs can be returned by id"""
    (expected_id, requested_id) = tariff_details
    async with generate_async_session(pg_base_config) as session:
        tariff = await select_single_tariff(session, requested_id)

        if expected_id is None:
            assert tariff is None
        else:
            assert tariff.tariff_id == expected_id
            assert tariff.currency_code == expected_id * 10 + expected_id
            assert tariff.dnsp_code == f"tariff-dnsp-code-{expected_id}"
            assert tariff.name == f"tariff-{expected_id}"

