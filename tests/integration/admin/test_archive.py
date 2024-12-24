import json
from datetime import datetime, timedelta, timezone
from http import HTTPStatus

import pytest
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.archive import (
    ArchiveDynamicOperatingEnvelopeResponse,
    ArchivePageResponse,
    ArchiveSiteResponse,
    ArchiveTariffGeneratedRateResponse,
)
from envoy_schema.admin.schema.uri import (
    ArchiveForPeriodDoes,
    ArchiveForPeriodSites,
    ArchiveForPeriodTariffGeneratedRate,
)
from httpx import AsyncClient

from envoy.server.api.request import MAX_LIMIT
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.archive.site import ArchiveSite
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
from tests.integration.response import read_response_body_string

DT1 = datetime(2024, 1, 2, 3, 8, 9, 500000, tzinfo=timezone.utc)
DT2 = DT1 + timedelta(hours=1.24)


async def populate_archive_with_type(pg_base_config, t: type):
    async with generate_async_session(pg_base_config) as session:

        # Archive 1 sits at DT1 for both archive times and delete times
        session.add(generate_class_instance(t, seed=1001, archive_id=1, archive_time=DT1, deleted_time=DT1))

        # Archive 2 sits at DT1 for deleted time but archive time is out of range
        session.add(
            generate_class_instance(t, seed=2002, archive_id=2, archive_time=DT1 - timedelta(hours=1), deleted_time=DT1)
        )

        # Archive 3 sits at DT1 for archive time but deleted time is out of range
        session.add(
            generate_class_instance(t, seed=3003, archive_id=3, archive_time=DT1, deleted_time=DT1 - timedelta(hours=1))
        )

        # Archive 4 sits on DT1 and isn't deleted
        session.add(
            generate_class_instance(
                t,
                seed=4004,
                archive_id=4,
                archive_time=DT1,
                deleted_time=None,
            )
        )

        # Archive 5 sits before DT1 and isn't deleted
        session.add(
            generate_class_instance(
                t,
                seed=5005,
                archive_id=5,
                archive_time=DT1 - timedelta(seconds=1),
                deleted_time=None,
            )
        )

        # Archive 6 sits at DT2
        session.add(
            generate_class_instance(
                t,
                seed=6006,
                archive_id=6,
                archive_time=DT2,
                deleted_time=DT2,
            )
        )

        await session.commit()


TEST_CASES = [
    (0, 999, DT1, DT2, False, [1, 3, 4], 3),  # Get everything for archives
    (0, 999, DT1, DT2, True, [1, 2], 2),  # Get everything for deletes
    (0, 999, DT2, DT2 + timedelta(seconds=1), False, [6], 1),  # Start from DT2
    (0, 999, DT2, DT2 + timedelta(seconds=1), True, [6], 1),  # Start from DT2
    (0, 999, DT1 - timedelta(days=1), DT2 - timedelta(days=1), False, [], 0),  # DT out of range
    (1, 2, DT1, DT2, False, [3, 4], 3),  # Archive pagination
    (2, 1, DT1, DT2, False, [4], 3),  # Archive pagination
    (999, 999, DT1, DT2, False, [], 3),  # Archive pagination
    (1, 2, DT1, DT2, True, [2], 2),  # delete pagination
    (2, 1, DT1, DT2, True, [], 2),  # delete pagination
    (999, 999, DT1, DT2, True, [], 2),  # delete pagination
]


@pytest.mark.parametrize(
    "start, limit, period_start, period_end, only_deletes, expected_archive_ids, expected_count", TEST_CASES
)
@pytest.mark.anyio
async def test_get_archive_for_period_sites(
    admin_client_auth: AsyncClient,
    pg_base_config,
    start: int,
    limit: int,
    period_start: datetime,
    period_end: datetime,
    only_deletes: bool,
    expected_archive_ids: list[int],
    expected_count: int,
):
    """Run through some basic query parameter parsing tests"""

    await populate_archive_with_type(pg_base_config, ArchiveSite)

    response = await admin_client_auth.get(
        ArchiveForPeriodSites.format(period_start=period_start.isoformat(), period_end=period_end.isoformat())
        + f"?only_deletes={only_deletes}&start={start}&limit={limit}"
    )
    assert response.status_code == HTTPStatus.OK

    body = read_response_body_string(response)
    assert len(body) > 0
    page = ArchivePageResponse[ArchiveSiteResponse](**json.loads(body))

    if limit >= MAX_LIMIT:
        assert page.limit == MAX_LIMIT
    else:
        assert page.limit == limit
    assert page.start == start
    assert page.total_count == expected_count
    assert_list_type(ArchiveSiteResponse, page.entities, len(expected_archive_ids))
    assert expected_archive_ids == [e.archive_id for e in page.entities]


@pytest.mark.parametrize(
    "start, limit, period_start, period_end, only_deletes, expected_archive_ids, expected_count", TEST_CASES
)
@pytest.mark.anyio
async def test_get_archive_for_period_rates(
    admin_client_auth: AsyncClient,
    pg_base_config,
    start: int,
    limit: int,
    period_start: datetime,
    period_end: datetime,
    only_deletes: bool,
    expected_archive_ids: list[int],
    expected_count: int,
):
    """Run through some basic query parameter parsing tests"""

    await populate_archive_with_type(pg_base_config, ArchiveTariffGeneratedRate)

    response = await admin_client_auth.get(
        ArchiveForPeriodTariffGeneratedRate.format(
            period_start=period_start.isoformat(), period_end=period_end.isoformat()
        )
        + f"?only_deletes={only_deletes}&start={start}&limit={limit}"
    )
    assert response.status_code == HTTPStatus.OK

    body = read_response_body_string(response)
    assert len(body) > 0
    page = ArchivePageResponse[ArchiveTariffGeneratedRateResponse](**json.loads(body))

    if limit >= MAX_LIMIT:
        assert page.limit == MAX_LIMIT
    else:
        assert page.limit == limit
    assert page.start == start
    assert page.total_count == expected_count
    assert_list_type(ArchiveTariffGeneratedRateResponse, page.entities, len(expected_archive_ids))
    assert expected_archive_ids == [e.archive_id for e in page.entities]


@pytest.mark.parametrize(
    "start, limit, period_start, period_end, only_deletes, expected_archive_ids, expected_count", TEST_CASES
)
@pytest.mark.anyio
async def test_get_archive_for_period_does(
    admin_client_auth: AsyncClient,
    pg_base_config,
    start: int,
    limit: int,
    period_start: datetime,
    period_end: datetime,
    only_deletes: bool,
    expected_archive_ids: list[int],
    expected_count: int,
):
    """Run through some basic query parameter parsing tests"""

    await populate_archive_with_type(pg_base_config, ArchiveDynamicOperatingEnvelope)

    response = await admin_client_auth.get(
        ArchiveForPeriodDoes.format(period_start=period_start.isoformat(), period_end=period_end.isoformat())
        + f"?only_deletes={only_deletes}&start={start}&limit={limit}"
    )
    assert response.status_code == HTTPStatus.OK

    body = read_response_body_string(response)
    assert len(body) > 0
    page = ArchivePageResponse[ArchiveDynamicOperatingEnvelopeResponse](**json.loads(body))

    if limit >= MAX_LIMIT:
        assert page.limit == MAX_LIMIT
    else:
        assert page.limit == limit
    assert page.start == start
    assert page.total_count == expected_count
    assert_list_type(ArchiveDynamicOperatingEnvelopeResponse, page.entities, len(expected_archive_ids))
    assert expected_archive_ids == [e.archive_id for e in page.entities]
