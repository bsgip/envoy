import urllib.parse
from http import HTTPStatus
from typing import Optional

import pytest
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointRequest, ConnectionPointResponse
from httpx import AsyncClient
from psycopg import Connection
from sqlalchemy import select

from envoy.server.manager.nmi_validator import DNSPParticipantId
from envoy.server.model.archive.site import ArchiveSite
from envoy.server.model.site import Site
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as AGG_1_VALID_CERT
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_FINGERPRINT as AGG_2_VALID_CERT
from tests.data.certificates.certificate5 import TEST_CERTIFICATE_FINGERPRINT as AGG_3_VALID_CERT
from tests.data.certificates.certificate7 import TEST_CERTIFICATE_FINGERPRINT as REGISTERED_DEVICE_CERT
from tests.integration.integration_server import cert_header
from tests.integration.response import (
    assert_error_response,
    assert_response_header,
    read_location_header,
    read_response_body_string,
)


@pytest.fixture
def connection_point_uri_format():
    return "/edev/{site_id}/cp"


@pytest.mark.parametrize(
    "site_id,expected_nmi,cert,expected_status_response",
    [
        (1, "1111111111", AGG_1_VALID_CERT, HTTPStatus.OK),
        (2, "2222222222", AGG_1_VALID_CERT, HTTPStatus.OK),
        (3, "3333333333", AGG_2_VALID_CERT, HTTPStatus.OK),
        (4, "4444444444", AGG_1_VALID_CERT, HTTPStatus.OK),
        (6, "6666666666", REGISTERED_DEVICE_CERT, HTTPStatus.OK),
        (6, None, AGG_1_VALID_CERT, HTTPStatus.NOT_FOUND),  # Agg1 cant reach device cert registered EndDevices
        (1, None, REGISTERED_DEVICE_CERT, HTTPStatus.FORBIDDEN),  # Device cert cant reach aggregator EndDevices
        (5, None, REGISTERED_DEVICE_CERT, HTTPStatus.FORBIDDEN),  # Device cert cant reach OTHER device cert EndDevices
        (1, None, AGG_2_VALID_CERT, HTTPStatus.NOT_FOUND),  # Agg 2 can't access site 1
        (3, None, AGG_3_VALID_CERT, HTTPStatus.NOT_FOUND),  # Agg 3 can't access site 3
        (99, None, AGG_1_VALID_CERT, HTTPStatus.NOT_FOUND),  # Site 99 does not exist
        (
            0,
            None,
            AGG_1_VALID_CERT,
            HTTPStatus.FORBIDDEN,
        ),  # Virtual EndDevice doesn't exist for the purpose of creating a CP
    ],
)
@pytest.mark.anyio
async def test_get_connectionpoint(
    client: AsyncClient,
    connection_point_uri_format: str,
    site_id: int,
    expected_nmi: Optional[str],
    cert: str,
    expected_status_response: HTTPStatus,
):
    """Tests getting a variety of connection points for the sites - tests successful / unsuccessful responses"""
    response = await client.get(
        connection_point_uri_format.format(site_id=site_id), headers={cert_header: urllib.parse.quote(cert)}
    )
    assert_response_header(response, expected_status_response)

    if expected_status_response == HTTPStatus.OK:
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response: ConnectionPointResponse = ConnectionPointResponse.from_xml(body)
        assert parsed_response.id == expected_nmi
    else:
        assert_error_response(response)


@pytest.mark.anyio
async def test_get_connectionpoint_none_nmi(
    client: AsyncClient, pg_base_config: Connection, connection_point_uri_format: str
):
    """Tests that a site with a None nmi will return empty string"""

    with pg_base_config.cursor() as cursor:
        cursor.execute('UPDATE public.site SET "nmi" = NULL WHERE "site_id" = 1')
        pg_base_config.commit()

    href = connection_point_uri_format.format(site_id=1)
    response = await client.get(href, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)})
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: ConnectionPointResponse = ConnectionPointResponse.from_xml(body)
    assert parsed_response.id is None or parsed_response.id == "", "Expected empty id"
    assert parsed_response.href == href


@pytest.mark.parametrize(
    "site_id, cert, update_nmi_value, expected_result, expected_nmi",
    [
        (1, AGG_1_VALID_CERT, "1212121212", HTTPStatus.CREATED, "1212121212"),
        (6, REGISTERED_DEVICE_CERT, "1212121212", HTTPStatus.CREATED, "1212121212"),
        (5, REGISTERED_DEVICE_CERT, "1212121212", HTTPStatus.FORBIDDEN, "5555555555"),  # Wrong device for device cert
        (1, REGISTERED_DEVICE_CERT, "1212121212", HTTPStatus.FORBIDDEN, "1111111111"),  # Wrong device for device cert
        (3, AGG_1_VALID_CERT, "1212121212", HTTPStatus.NOT_FOUND, "3333333333"),  # No update - wrong agg
        (6, AGG_1_VALID_CERT, "1212121212", HTTPStatus.NOT_FOUND, "6666666666"),  # No update - wrong agg
    ],
)
@pytest.mark.anyio
async def test_connectionpoint_update(
    client: AsyncClient,
    pg_base_config,
    connection_point_uri_format: str,
    site_id: int,
    cert: str,
    update_nmi_value: str,
    expected_result: HTTPStatus,
    expected_nmi: Optional[str],
):
    """Tests that connection points can be updated / fetched (and that they archive appropriately)"""

    # fire off our update
    href = connection_point_uri_format.format(site_id=site_id)
    new_cp_specified: ConnectionPointRequest = ConnectionPointRequest(id=update_nmi_value)
    response = await client.put(
        url=href, headers={cert_header: urllib.parse.quote(cert)}, content=new_cp_specified.to_xml()
    )

    # Validate response
    if expected_result == HTTPStatus.CREATED:
        assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)
        body = read_response_body_string(response)
        assert read_location_header(response) == href
        assert len(body) == 0
        archive_expected = True
    else:
        assert_response_header(response, expected_result)
        assert_error_response(response)
        archive_expected = False

    # check whether it updated (or not) in the DB
    async with generate_async_session(pg_base_config) as session:
        site = (await session.execute(select(Site).where(Site.site_id == site_id))).scalar_one()
        assert site.nmi == expected_nmi

        archived_sites = (
            (await session.execute(select(ArchiveSite).where(ArchiveSite.site_id == site_id))).scalars().all()
        )
        if archive_expected:
            assert len(archived_sites) == 1
            assert archived_sites[0].site_id == site_id
            assert archived_sites[0].nmi == (str(site_id) * 10), "All NMIs in base config are just like 1111111111"
        else:
            assert len(archived_sites) == 0


@pytest.mark.anyio
async def test_connectionpoint_update_and_fetch_legacy_csip(client: AsyncClient, connection_point_uri_format: str):
    """Tests that connection points can be updated / fetched using the updated legacy csip v11"""

    # fire off our first update
    href = connection_point_uri_format.format(site_id=1)
    new_cp_specified: ConnectionPointRequest = ConnectionPointRequest(id_v11="1212121212")
    response = await client.put(
        url=href, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)}, content=new_cp_specified.to_xml()
    )
    assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)
    body = read_response_body_string(response)
    assert read_location_header(response) == href
    assert len(body) == 0

    # check it updated
    response = await client.get(href, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)})
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: ConnectionPointResponse = ConnectionPointResponse.from_xml(body)
    assert parsed_response.id == new_cp_specified.id_v11


@pytest.mark.anyio
@pytest.mark.href_prefix("my/custom/prefix")
async def test_connectionpoint_update_and_fetch_href_prefix(client: AsyncClient, connection_point_uri_format: str):
    """Tests that connection points can be updated / fetched"""

    # fire off our first update
    href = connection_point_uri_format.format(site_id=1)
    expected_href = "/my/custom/prefix" + href
    new_cp_specified: ConnectionPointRequest = ConnectionPointRequest(id="1212121212")
    response = await client.put(
        url=href, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)}, content=new_cp_specified.to_xml()
    )
    assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)
    body = read_response_body_string(response)

    assert read_location_header(response) == expected_href
    assert len(body) == 0

    # check it updated
    response = await client.get(href, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)})
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: ConnectionPointResponse = ConnectionPointResponse.from_xml(body)
    assert parsed_response.id == new_cp_specified.id
    assert parsed_response.href == expected_href


@pytest.mark.anyio
async def test_connectionpoint_update_bad_xml(client: AsyncClient, connection_point_uri_format: str):
    """Tests malformed XML on the endpoint results in a BadRequest"""

    # The closing tag on ID has an incorrect namespace
    bad_xml = """<ConnectionPoint xmlns="http://csipaus.org/ns"><id>1111111111</csipaus:id></ConnectionPoint>"""

    href = connection_point_uri_format.format(site_id=1)
    response = await client.put(url=href, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)}, content=bad_xml)
    assert_response_header(response, HTTPStatus.BAD_REQUEST)
    assert_error_response(response)


@pytest.mark.anyio
async def test_connectionpoint_update_aggregator_edev_returns_403(
    client: AsyncClient, connection_point_uri_format: str
):
    """Tests that an aggregator can't update the connection point of an aggregator end device"""

    href = connection_point_uri_format.format(site_id=0)
    new_cp_specified: ConnectionPointRequest = ConnectionPointRequest(id="1212121212")
    response = await client.put(
        url=href, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)}, content=new_cp_specified.to_xml()
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.nmi_validation_enabled(DNSPParticipantId.Ausgrid.value)
@pytest.mark.parametrize(
    "site_id, cert, update_nmi_value, expected_result",
    [
        (1, AGG_1_VALID_CERT, "41020000002", HTTPStatus.CREATED),
        (1, AGG_1_VALID_CERT, "NCCC1234564", HTTPStatus.CREATED),
        (1, AGG_1_VALID_CERT, "41020000003", HTTPStatus.UNPROCESSABLE_ENTITY),  # Invalid
        (11, AGG_1_VALID_CERT, "41020000003", HTTPStatus.NOT_FOUND),  # Valid, not found
        (11, AGG_1_VALID_CERT, "41020000003", HTTPStatus.NOT_FOUND),  # Invalid, not found
    ],
)
@pytest.mark.anyio
async def test_connectionpoint_put_with_nmi_validation(
    client: AsyncClient,
    connection_point_uri_format: str,
    site_id: int,
    cert: str,
    update_nmi_value: str,
    expected_result: HTTPStatus,
):
    """Tests that connection points can be PUT with appropriate NMI validation checks."""

    # fire off our update
    href = connection_point_uri_format.format(site_id=site_id)
    new_cp_specified: ConnectionPointRequest = ConnectionPointRequest(id=update_nmi_value)
    response = await client.put(
        url=href, headers={cert_header: urllib.parse.quote(cert)}, content=new_cp_specified.to_xml()
    )

    # Validate response
    if expected_result == HTTPStatus.CREATED:
        assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)
        body = read_response_body_string(response)
        assert read_location_header(response) == href
        assert len(body) == 0
    else:
        assert_response_header(response, expected_result)
        assert_error_response(response)


@pytest.mark.allow_nmi_updates("false")
@pytest.mark.anyio
async def test_connectionpoint_put_disallow_updates(client: AsyncClient, connection_point_uri_format: str):
    # Attempt update
    href = connection_point_uri_format.format(site_id=1)  # existing site with NMI
    new_cp_specified: ConnectionPointRequest = ConnectionPointRequest(id="123")
    response = await client.put(
        url=href, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)}, content=new_cp_specified.to_xml()
    )

    # Expect Conflict response
    assert response.status_code == HTTPStatus.CONFLICT
