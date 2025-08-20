import datetime as dt

import psycopg
import pytest
from assertical.fixtures.postgres import generate_async_session
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from envoy.admin.crud.certificate import select_all_certificates_for_aggregator
from envoy.server import model
from envoy.admin import crud
from envoy.server.crud.aggregator import select_aggregator


@pytest.mark.anyio
async def test_count_all_aggregators(pg_base_config: psycopg.Connection) -> None:
    async with generate_async_session(pg_base_config) as session:
        assert (await crud.aggregator.count_all_aggregators(session)) == 3


@pytest.mark.anyio
async def test_count_all_aggregators_empty(pg_empty_config: psycopg.Connection) -> None:
    async with generate_async_session(pg_empty_config) as session:
        assert (await crud.aggregator.count_all_aggregators(session)) == 0


@pytest.mark.parametrize(
    "start, limit, expected_aggregator_ids, expected_domain_ids",
    [
        (0, 500, [1, 2, 3], [1, 2, 3, 4]),
        (0, 1, [1], [1, 4]),
        (1, 1, [2], [2]),
        (2, 1, [3], [3]),
        (3, 1, [], []),
    ],
)
@pytest.mark.anyio
async def test_select_aggregators(
    pg_base_config: psycopg.Connection,
    start: int,
    limit: int,
    expected_aggregator_ids: list[int],
    expected_domain_ids: list[int],
) -> None:
    async with generate_async_session(pg_base_config) as session:
        aggs = await crud.aggregator.select_all_aggregators(session, start, limit)
        assert len(aggs) == len(expected_aggregator_ids)
        assert all([isinstance(s, model.Aggregator) for s in aggs])
        assert expected_aggregator_ids == [a.aggregator_id for a in aggs]
        assert expected_domain_ids == sorted([d.aggregator_domain_id for a in aggs for d in a.domains])


@pytest.mark.parametrize("agg_id_to_delete", [1, 2, 3])
@pytest.mark.anyio
async def test_select_aggregators_no_domains(pg_base_config: psycopg.Connection, agg_id_to_delete: int) -> None:

    async with generate_async_session(pg_base_config) as session:
        stmt = sa.select(model.AggregatorDomain).where(model.AggregatorDomain.aggregator_id == agg_id_to_delete)
        resp = await session.execute(stmt)

        for domain_to_delete in resp.scalars().all():
            await session.delete(domain_to_delete)
        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        aggs = await crud.aggregator.select_all_aggregators(session, 0, 99)
        agg_no_domains = [a for a in aggs if a.aggregator_id == agg_id_to_delete][0]
        assert len(agg_no_domains.domains) == 0


@pytest.mark.anyio
async def test_assign_many_certificates(pg_base_config: psycopg.Connection) -> None:
    async with generate_async_session(pg_base_config) as session:
        prior_assigns_q = await session.execute(sa.select(model.AggregatorCertificateAssignment))
        prior_assigns = prior_assigns_q.scalars().all()
        await crud.aggregator.assign_many_certificates(session, 1, range(4, 6))

        # ensure certificates assigned
        resp = await select_all_certificates_for_aggregator(session, 1, 0, 5000)
        assert [c.certificate_id for c in resp] == [1, 2, 3, 4, 5]

        # ensure new entry in table
        after_assigns_q = await session.execute(sa.select(model.AggregatorCertificateAssignment))
        after_assigns = after_assigns_q.scalars().all()
        assert len(prior_assigns) < len(after_assigns)


@pytest.mark.anyio
async def test_assign_many_certificates_already_assigned(pg_base_config: psycopg.Connection) -> None:
    """Should fail when an existing relationship is attempted to be created"""
    async with generate_async_session(pg_base_config) as session:
        with pytest.raises(IntegrityError):
            await crud.aggregator.assign_many_certificates(session, 1, [3])


@pytest.mark.parametrize(
    "agg_id,certificate_ids,expected_ids",
    [
        (1, [1], [2, 3]),
        (1, [2], [1, 3]),
        (1, [3], [1, 2]),
        (1, [1, 2], [3]),
        (1, [1, 2, 3], []),
        (2, [4], []),
        (1, [4], [1, 2, 3]),
    ],
)
@pytest.mark.anyio
async def test_unassign_many_certificates(
    pg_base_config: psycopg.Connection, agg_id: int, certificate_ids: list[int], expected_ids: list[int]
) -> None:
    async with generate_async_session(pg_base_config) as session:
        await crud.aggregator.unassign_many_certificates(session, agg_id, certificate_ids)
        actual = await crud.certificate.select_all_certificates_for_aggregator(session, agg_id, 0, 500)
        assert [a.certificate_id for a in actual] == expected_ids


@pytest.mark.parametrize(
    "agg_id,cert_ids,one_certs,two_certs,three_certs",
    [
        (1, [4], [1, 2, 3], [4], [5]),
        (1, [6], [1, 2, 3], [4], [5]),
        (2, [4], [1, 2, 3], [], [5]),
    ],
)
@pytest.mark.anyio
async def test_unassign_many_certificates_no_cross_contamination(
    pg_base_config: psycopg.Connection,
    agg_id: int,
    cert_ids: list[int],
    one_certs: list[int],
    two_certs: list[int],
    three_certs: list[int],
) -> None:
    """Testing to ensure the unassignment of a certificate from one aggregator doesn't affect another"""
    async with generate_async_session(pg_base_config) as session:
        await crud.aggregator.unassign_many_certificates(session, agg_id, cert_ids)
        actual_ones = await crud.certificate.select_all_certificates_for_aggregator(session, 1, 0, 500)
        actual_twos = await crud.certificate.select_all_certificates_for_aggregator(session, 2, 0, 500)
        actual_threes = await crud.certificate.select_all_certificates_for_aggregator(session, 3, 0, 500)
        assert [a.certificate_id for a in actual_ones] == one_certs
        assert [a.certificate_id for a in actual_twos] == two_certs
        assert [a.certificate_id for a in actual_threes] == three_certs


@pytest.mark.anyio
async def test_update_single_aggregator(pg_base_config: psycopg.Connection) -> None:
    """Test ensures aggregator can be updated"""
    async with generate_async_session(pg_base_config) as session:
        # retrieve original cert
        agg = await select_aggregator(session, 1)

    async with generate_async_session(pg_base_config) as session:
        await crud.aggregator.update_single_aggregator(
            session,
            model.Aggregator(
                aggregator_id=1,
                name="Some_new_name",
                changed_time=dt.datetime.now(tz=dt.timezone.utc),
                created_time=dt.datetime.now(tz=dt.timezone.utc),
            ),
        )

        # Get updated cert
        new_agg = await select_aggregator(session, 1)

        # Confirm agg returned
        assert agg is not None
        assert new_agg is not None

        # Assert key fields changed
        assert agg.name != new_agg.name
        assert agg.created_time == new_agg.created_time
        assert agg.changed_time < new_agg.changed_time


@pytest.mark.anyio
async def test_insert_single_aggregator(pg_base_config: psycopg.Connection) -> None:
    """Test ensures single aggregator gets created"""
    async with generate_async_session(pg_base_config) as session:
        original_aggregators = await crud.aggregator.select_all_aggregators(session, 0, 500)

    async with generate_async_session(pg_base_config) as session:
        fake_time = dt.datetime(1234, 12, 3, 4, 5, 6, tzinfo=dt.timezone.utc)
        agg = model.Aggregator(
            name="SOMEFAKEAGG",
            changed_time=fake_time,
            # Should reassign this to current time
            created_time=fake_time,
        )
        await crud.aggregator.insert_single_aggregator(session, agg)
        await session.flush()

        assert agg.aggregator_id not in [a.aggregator_id for a in original_aggregators]
        assert agg.created_time > fake_time
        assert agg.created_time.year != fake_time.year
        assert agg.changed_time == fake_time
