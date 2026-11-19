import json
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.cleanup import (
    ArchiveCleanupRequest,
    ArchiveCleanupResponse,
    ArchiveCleanupType,
    CleanupResponse,
    ExpiredCleanupMode,
    ExpiredCleanupRequest,
)
from envoy_schema.admin.schema.uri import (
    CleanupArchiveUri,
    CleanupExpiredSiteControlsUri,
    CleanupExpiredTariffGeneratedRatesUri,
)
from httpx import AsyncClient
from sqlalchemy import func, select

from envoy.admin.manager.cleanup import ARCHIVE_TABLE_BY_CLEANUP_TYPE
from envoy.server.model.archive.base import ArchiveBase
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.archive.site import ArchiveSite
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.tariff import TariffGeneratedRate
from tests.integration.response import read_response_body_string

AEST = timedelta(hours=10)


def test_archive_table_mapping_is_complete():
    """Every ArchiveCleanupType must be accounted for - otherwise the cleanup endpoint will raise a KeyError"""
    assert set(ARCHIVE_TABLE_BY_CLEANUP_TYPE.keys()) == set(ArchiveCleanupType)


@pytest.mark.parametrize(
    "expired_before, mode, expected_remaining_ids",
    [
        # base_config DOE end_times: 1 -> 2022-05-07 01:02:11+10, 2 -> 03:04:22+10, 3 -> 01:02:33+10,
        # 4 -> 2022-05-08 01:02:44+10
        (datetime(2022, 5, 7, 1, 2, 10, tzinfo=UTC) - AEST, ExpiredCleanupMode.archive, [1, 2, 3, 4]),
        (datetime(2022, 5, 7, 1, 2, 11, tzinfo=UTC) - AEST, ExpiredCleanupMode.archive, [2, 3, 4]),  # inclusive
        (datetime(2022, 5, 7, 1, 2, 11, tzinfo=UTC) - AEST, ExpiredCleanupMode.delete, [2, 3, 4]),
        (datetime(2022, 5, 7, 12, 0, 0, tzinfo=UTC) - AEST, ExpiredCleanupMode.archive, [4]),
        (datetime(2022, 5, 7, 12, 0, 0, tzinfo=UTC) - AEST, ExpiredCleanupMode.delete, [4]),
        (datetime(2030, 1, 1, tzinfo=UTC), ExpiredCleanupMode.archive, []),
        (datetime(2030, 1, 1, tzinfo=UTC), None, []),  # Default mode is archive
    ],
)
@pytest.mark.anyio
async def test_cleanup_expired_site_controls(
    pg_base_config,
    admin_client_auth: AsyncClient,
    expired_before: datetime,
    mode: ExpiredCleanupMode | None,
    expected_remaining_ids: list[int],
):
    if mode is None:
        body = {"expired_before": expired_before.isoformat()}
    else:
        body = ExpiredCleanupRequest(expired_before=expired_before, mode=mode).model_dump(mode="json")

    resp = await admin_client_auth.post(CleanupExpiredSiteControlsUri, json=body)
    assert resp.status_code == HTTPStatus.OK
    cleanup_resp = CleanupResponse.model_validate(json.loads(read_response_body_string(resp)))

    expected_removed_ids = sorted({1, 2, 3, 4} - set(expected_remaining_ids))
    assert cleanup_resp.removed_count == len(expected_removed_ids)

    async with generate_async_session(pg_base_config) as session:
        remaining = (
            (
                await session.execute(
                    select(DynamicOperatingEnvelope.dynamic_operating_envelope_id).order_by(
                        DynamicOperatingEnvelope.dynamic_operating_envelope_id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert list(remaining) == expected_remaining_ids

        archived = (await session.execute(select(ArchiveDynamicOperatingEnvelope))).scalars().all()
        if mode == ExpiredCleanupMode.delete:
            assert len(archived) == 0
        else:
            assert sorted(a.dynamic_operating_envelope_id for a in archived) == expected_removed_ids
            assert all(a.deleted_time is not None for a in archived)


@pytest.mark.parametrize(
    "expired_before, mode, expected_remaining_ids",
    [
        # base_config rate end times (all 2022-03-05 +10): 1 -> 01:00:11, 2 -> 01:00:33, 3 -> 01:01:06,
        # 4 -> 01:00:44, 5 -> 01:00:55, 6 -> 01:01:06, 7 -> 01:01:17
        (datetime(2022, 3, 5, 1, 0, 10, tzinfo=UTC) - AEST, ExpiredCleanupMode.archive, [1, 2, 3, 4, 5, 6, 7]),
        (datetime(2022, 3, 5, 1, 0, 11, tzinfo=UTC) - AEST, ExpiredCleanupMode.archive, [2, 3, 4, 5, 6, 7]),  # incl.
        (datetime(2022, 3, 5, 1, 0, 12, tzinfo=UTC) - AEST, ExpiredCleanupMode.delete, [2, 3, 4, 5, 6, 7]),
        (datetime(2022, 3, 5, 1, 0, 44, tzinfo=UTC) - AEST, ExpiredCleanupMode.archive, [3, 5, 6, 7]),
        (datetime(2022, 3, 5, 1, 1, 6, tzinfo=UTC) - AEST, ExpiredCleanupMode.delete, [7]),
        (datetime(2030, 1, 1, tzinfo=UTC), ExpiredCleanupMode.archive, []),
    ],
)
@pytest.mark.anyio
async def test_cleanup_expired_tariff_generated_rates(
    pg_base_config,
    admin_client_auth: AsyncClient,
    expired_before: datetime,
    mode: ExpiredCleanupMode,
    expected_remaining_ids: list[int],
):
    body = ExpiredCleanupRequest(expired_before=expired_before, mode=mode).model_dump(mode="json")
    resp = await admin_client_auth.post(CleanupExpiredTariffGeneratedRatesUri, json=body)
    assert resp.status_code == HTTPStatus.OK
    cleanup_resp = CleanupResponse.model_validate(json.loads(read_response_body_string(resp)))

    expected_removed_ids = sorted(set(range(1, 8)) - set(expected_remaining_ids))
    assert cleanup_resp.removed_count == len(expected_removed_ids)

    async with generate_async_session(pg_base_config) as session:
        remaining = (
            (
                await session.execute(
                    select(TariffGeneratedRate.tariff_generated_rate_id).order_by(
                        TariffGeneratedRate.tariff_generated_rate_id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert list(remaining) == expected_remaining_ids

        archived = (await session.execute(select(ArchiveTariffGeneratedRate))).scalars().all()
        if mode == ExpiredCleanupMode.delete:
            assert len(archived) == 0
        else:
            assert sorted(a.tariff_generated_rate_id for a in archived) == expected_removed_ids
            assert all(a.deleted_time is not None for a in archived)


@pytest.mark.parametrize("uri", [CleanupExpiredSiteControlsUri, CleanupExpiredTariffGeneratedRatesUri])
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"mode": "archive"},
        {"expired_before": "not-a-date"},
        {"expired_before": "2022-01-01T00:00:00Z", "mode": "invalid-mode"},
    ],
)
@pytest.mark.anyio
async def test_cleanup_expired_bad_request(admin_client_auth: AsyncClient, uri: str, body: dict):
    resp = await admin_client_auth.post(uri, json=body)
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


ARCHIVE_DT = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)


async def populate_archive(pg_base_config, t: type[ArchiveBase], id_offset: int):
    """Adds 3 archive records to t with archive_ids id_offset + (1, 2, 3) - archived at ARCHIVE_DT - 1 sec,
    ARCHIVE_DT and ARCHIVE_DT + 1 sec respectively"""
    async with generate_async_session(pg_base_config) as session:
        for i, delta in enumerate([timedelta(seconds=-1), timedelta(0), timedelta(seconds=1)], start=1):
            session.add(
                generate_class_instance(
                    t,
                    seed=id_offset + i * 101,
                    archive_id=id_offset + i,
                    archive_time=ARCHIVE_DT + delta,
                    deleted_time=None,
                )
            )
        await session.commit()


async def count_archive(pg_base_config, t: type[ArchiveBase]) -> int:
    async with generate_async_session(pg_base_config) as session:
        return (await session.execute(select(func.count()).select_from(t))).scalar_one()


@pytest.mark.parametrize(
    "archive_types, archived_before, expected_counts",
    [
        # None means all types
        (
            None,
            ARCHIVE_DT,
            {t: 0 for t in ArchiveCleanupType}
            | {
                ArchiveCleanupType.site: 2,
                ArchiveCleanupType.site_control: 2,
                ArchiveCleanupType.tariff_generated_rate: 2,
            },
        ),
        (
            None,
            ARCHIVE_DT + timedelta(days=1),
            {t: 0 for t in ArchiveCleanupType}
            | {
                ArchiveCleanupType.site: 3,
                ArchiveCleanupType.site_control: 3,
                ArchiveCleanupType.tariff_generated_rate: 3,
            },
        ),
        ([ArchiveCleanupType.site], ARCHIVE_DT, {ArchiveCleanupType.site: 2}),
        (
            [ArchiveCleanupType.site_control, ArchiveCleanupType.site_control, ArchiveCleanupType.tariff_component],
            ARCHIVE_DT - timedelta(seconds=1),
            {ArchiveCleanupType.site_control: 1, ArchiveCleanupType.tariff_component: 0},
        ),
        (
            [ArchiveCleanupType.site, ArchiveCleanupType.tariff_generated_rate],
            ARCHIVE_DT - timedelta(days=1),
            {
                ArchiveCleanupType.site: 0,
                ArchiveCleanupType.tariff_generated_rate: 0,
            },
        ),
        ([], ARCHIVE_DT, {}),
    ],
)
@pytest.mark.anyio
async def test_cleanup_archive(
    pg_base_config,
    admin_client_auth: AsyncClient,
    archive_types: list[ArchiveCleanupType] | None,
    archived_before: datetime,
    expected_counts: dict[ArchiveCleanupType, int],
):
    populated: dict[ArchiveCleanupType, type[ArchiveBase]] = {
        ArchiveCleanupType.site: ArchiveSite,
        ArchiveCleanupType.site_control: ArchiveDynamicOperatingEnvelope,
        ArchiveCleanupType.tariff_generated_rate: ArchiveTariffGeneratedRate,
    }
    for i, t in enumerate(populated.values()):
        await populate_archive(pg_base_config, t, i * 100)

    body = ArchiveCleanupRequest(archived_before=archived_before, archive_types=archive_types).model_dump(mode="json")
    resp = await admin_client_auth.post(CleanupArchiveUri, json=body)
    assert resp.status_code == HTTPStatus.OK
    cleanup_resp = ArchiveCleanupResponse.model_validate(json.loads(read_response_body_string(resp)))

    assert cleanup_resp.archived_before == archived_before
    assert cleanup_resp.removed_counts == expected_counts

    # Validate the DB was actually updated
    for cleanup_type, t in populated.items():
        assert await count_archive(pg_base_config, t) == 3 - expected_counts.get(cleanup_type, 0)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"archived_before": "not-a-date"},
        {"archived_before": "2022-01-01T00:00:00Z", "archive_types": ["not-a-type"]},
    ],
)
@pytest.mark.anyio
async def test_cleanup_archive_bad_request(admin_client_auth: AsyncClient, body: dict):
    resp = await admin_client_auth.post(CleanupArchiveUri, json=body)
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
