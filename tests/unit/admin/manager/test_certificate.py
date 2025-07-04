import datetime as dt

import pytest
import pytest_mock
import psycopg
import sqlalchemy as sa
from assertical.fixtures import postgres
from envoy_schema.admin.schema.certificate import CertificateAssignmentRequest

from envoy.admin import manager
from envoy.server.model.aggregator import AggregatorCertificateAssignment
from envoy.admin import crud
from envoy.server import exception


@pytest.mark.anyio
async def test_add_many_certficates_for_aggregator_assign_many_mocked(
    pg_base_config: psycopg.Connection, mocker: pytest_mock.MockerFixture
) -> None:
    """Testing to make sure final call to assign_many_certificates expected are being made."""
    async with postgres.generate_async_session(pg_base_config) as session:
        assign_many_mock = mocker.patch("envoy.admin.crud.aggregator.assign_many_certificates")

        certs: list[CertificateAssignmentRequest] = [
            CertificateAssignmentRequest(certificate_id=4),
            CertificateAssignmentRequest(lfdi="SOMEFAKELFDI", expiry=dt.datetime.now() + dt.timedelta(365)),
            CertificateAssignmentRequest(lfdi="ec08e4c9d68a0669c3673708186fde317f7c67a2"),
        ]
        await manager.CertificateManager.add_many_certificates_for_aggregator(session, 1, certs)
        assign_many_mock.assert_called_once()

        args, _ = assign_many_mock.call_args
        assert args[1] == 1, "Aggregator ID doesn't match"

        # Make sure the expected new assignment certificate IDs are being passed in
        assert [a for a in args[2]] == [7, 4, 5], "Certificate IDs doesn't match"


@pytest.mark.anyio
async def test_add_many_certficates_for_aggregator_create_many_mocked(
    pg_base_config: psycopg.Connection,
    mocker: pytest_mock.MockerFixture,
) -> None:
    """Testing to make sure call to create_many_certificates_on_conflict_do_nothing are being made"""
    async with postgres.generate_async_session(pg_base_config) as session:
        mocker.patch("envoy.admin.crud.aggregator.assign_many_certificates")
        create_many_mock = mocker.patch("envoy.admin.crud.certificate.create_many_certificates_on_conflict_do_nothing")
        create_many_mock.return_value = []

        certs: list[CertificateAssignmentRequest] = [
            CertificateAssignmentRequest(certificate_id=4),
            CertificateAssignmentRequest(lfdi="SOMEFAKELFDI", expiry=dt.datetime.now() + dt.timedelta(365)),
            CertificateAssignmentRequest(lfdi="ec08e4c9d68a0669c3673708186fde317f7c67a2"),
        ]
        await manager.CertificateManager.add_many_certificates_for_aggregator(session, 1, certs)
        create_many_mock.assert_called_once()

        args, _ = create_many_mock.call_args
        certs_to_create = args[1]
        assert len(certs_to_create) == 1
        assert certs_to_create[0].lfdi == "SOMEFAKELFDI"


@pytest.mark.anyio
async def test_add_many_certficates_for_aggregator_existing_cert(pg_base_config: psycopg.Connection) -> None:
    """Proper test, no mocks"""
    async with postgres.generate_async_session(pg_base_config) as session:
        prior_assigns_q = await session.execute(sa.select(AggregatorCertificateAssignment))
        prior_assigns = prior_assigns_q.scalars().all()

        certs: list[CertificateAssignmentRequest] = [
            CertificateAssignmentRequest(certificate_id=4),
            CertificateAssignmentRequest(lfdi="SOMEFAKELFDI", expiry=dt.datetime.now() + dt.timedelta(365)),
        ]
        await manager.CertificateManager.add_many_certificates_for_aggregator(session, 1, certs)

        # ensure new entry in table
        after_assigns_q = await session.execute(sa.select(AggregatorCertificateAssignment))
        after_assigns = after_assigns_q.scalars().all()
        assert len(prior_assigns) < len(after_assigns)

        all_certs = await crud.certificate.select_all_certificates(session, 0, 500)
        assert "SOMEFAKELFDI" in [ac.lfdi for ac in all_certs]


@pytest.mark.parametrize(
    "agg_id,cert_id,expected_ids",
    [
        (1, 1, [2, 3]),
        (1, 2, [1, 3]),
        (1, 3, [1, 2]),
    ],
)
@pytest.mark.anyio
async def test_unassign_certificate_for_aggregator(
    pg_base_config: psycopg.Connection, agg_id: int, cert_id: int, expected_ids: list[int]
) -> None:
    """Happy path tests for unassign_certificate_for_aggregator() method"""
    async with postgres.generate_async_session(pg_base_config) as session:
        # invoke method
        await manager.certificate.CertificateManager.unassign_certificate_for_aggregator(session, agg_id, cert_id)

        # query certificates
        actual_certs = await crud.certificate.select_all_certificates_for_aggregator(session, agg_id, 0, 500)

        # assert
        assert [a.certificate_id for a in actual_certs] == expected_ids


@pytest.mark.anyio
async def test_unassign_certificate_invalid_aggregator_id(pg_base_config: psycopg.Connection) -> None:
    """Confirm correct error raised"""
    async with postgres.generate_async_session(pg_base_config) as session:
        with pytest.raises(exception.NotFoundError, match="Aggregator with id 1111 not found"):
            await manager.certificate.CertificateManager.unassign_certificate_for_aggregator(session, 1111, 1)


@pytest.mark.anyio
async def test_unassign_certificate_invalid_certificate_id(pg_base_config: psycopg.Connection) -> None:
    """Confirm correct error raised"""
    async with postgres.generate_async_session(pg_base_config) as session:
        with pytest.raises(exception.NotFoundError, match="Certificate with id 1111 not found"):
            await manager.certificate.CertificateManager.unassign_certificate_for_aggregator(session, 1, 1111)
