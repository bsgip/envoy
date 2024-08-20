from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from sqlalchemy import select

from envoy.admin.crud.doe import count_all_does, select_all_does, upsert_many_doe
from envoy.server.model.doe import DynamicOperatingEnvelope


async def _select_latest_dynamic_operating_envelope(session):
    stmt = (
        select(DynamicOperatingEnvelope)
        .order_by(DynamicOperatingEnvelope.dynamic_operating_envelope_id.desc())
        .limit(1)
    )
    resp = await session.execute(stmt)
    return resp.scalar_one()


@pytest.mark.anyio
async def test_upsert_many_doe(pg_base_config):
    """Assert that we are able to successfully insert a valid DOERequest into a db"""

    async with generate_async_session(pg_base_config) as session:
        doe_in: DynamicOperatingEnvelope = generate_class_instance(
            DynamicOperatingEnvelope, generate_relationships=False
        )

        # clean up generated instance to ensure it doesn't clash with base_config
        doe_in.site_id = 1
        del doe_in.dynamic_operating_envelope_id

        await upsert_many_doe(session, [doe_in])
        await session.flush()

        doe_out = await _select_latest_dynamic_operating_envelope(session)

        assert_class_instance_equality(
            DynamicOperatingEnvelope, doe_out, doe_in, ignored_properties={"dynamic_operating_envelope_id"}
        )

        doe_in_1 = generate_class_instance(DynamicOperatingEnvelope)
        doe_in_1.site_id = 1
        doe_in_1.start_time = doe_in.start_time + timedelta(seconds=1)

        await upsert_many_doe(session, [doe_in, doe_in_1])


@pytest.mark.parametrize(
    "changed_after, expected_count",
    [
        (None, 4),
        (datetime.min, 4),
        (datetime.max, 0),
        (datetime(2022, 5, 6, 11, 22, 33, tzinfo=timezone.utc), 4),
        (datetime(2022, 5, 6, 11, 22, 34, tzinfo=timezone.utc), 3),
        (datetime(2022, 5, 6, 12, 22, 34, tzinfo=timezone.utc), 2),
        (datetime(2022, 5, 6, 13, 22, 34, tzinfo=timezone.utc), 1),
        (datetime(2022, 5, 6, 14, 22, 34, tzinfo=timezone.utc), 0),
    ],
)
@pytest.mark.anyio
async def test_count_all_does(pg_base_config, changed_after: Optional[datetime], expected_count: int):
    async with generate_async_session(pg_base_config) as session:
        assert (await count_all_does(session, changed_after)) == expected_count


@pytest.mark.parametrize(
    "start, limit, after, expected_doe_ids",
    [
        (0, 999, None, [1, 2, 3, 4]),
        (2, 999, None, [3, 4]),
        (0, 2, None, [1, 2]),
        (1, 2, None, [2, 3]),
        (99, 99, None, []),
        (0, 99, datetime(2022, 5, 6, 11, 22, 34, tzinfo=timezone.utc), [2, 3, 4]),
        (1, 99, datetime(2022, 5, 6, 11, 22, 34, tzinfo=timezone.utc), [3, 4]),
        (1, 1, datetime(2022, 5, 6, 11, 22, 34, tzinfo=timezone.utc), [3]),
    ],
)
@pytest.mark.anyio
async def test_select_all_does(
    pg_base_config, start: int, limit: int, after: Optional[datetime], expected_doe_ids: list[int]
):
    async with generate_async_session(pg_base_config) as session:
        does = await select_all_does(session, start, limit, after)
        assert_list_type(DynamicOperatingEnvelope, does, len(expected_doe_ids))
        assert expected_doe_ids == [d.dynamic_operating_envelope_id for d in does]
