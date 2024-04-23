import urllib.parse
from http import HTTPStatus
from typing import Optional

import pytest
from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointRequest, ConnectionPointResponse
from httpx import AsyncClient
from psycopg import Connection

from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as AGG_1_VALID_CERT
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_FINGERPRINT as AGG_2_VALID_CERT
from tests.data.certificates.certificate5 import TEST_CERTIFICATE_FINGERPRINT as AGG_3_VALID_CERT
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
        (1, None, AGG_2_VALID_CERT, HTTPStatus.NOT_FOUND),  # Agg 2 can't access site 1
        (3, None, AGG_3_VALID_CERT, HTTPStatus.NOT_FOUND),  # Agg 3 can't access site 3
        (99, None, AGG_1_VALID_CERT, HTTPStatus.NOT_FOUND),  # Site 99 does not exist
        (
            0,
            None,
            AGG_1_VALID_CERT,
            HTTPStatus.NOT_FOUND,
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

    response = await client.get(
        connection_point_uri_format.format(site_id=1), headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)}
    )
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: ConnectionPointResponse = ConnectionPointResponse.from_xml(body)
    assert parsed_response.id is None or parsed_response.id == "", "Expected empty id"


@pytest.mark.anyio
async def test_connectionpoint_update_and_fetch(client: AsyncClient, connection_point_uri_format: str):
    """Tests that connection points can be updated / fetched"""

    # fire off our first update
    href = connection_point_uri_format.format(site_id=1)
    new_cp_specified: ConnectionPointRequest = ConnectionPointRequest(id="1212121212")
    response = await client.post(
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
    assert parsed_response.id == new_cp_specified.id


@pytest.mark.anyio
@pytest.mark.href_prefix("my/custom/prefix")
async def test_connectionpoint_update_and_fetch_href_prefix(client: AsyncClient, connection_point_uri_format: str):
    """Tests that connection points can be updated / fetched"""

    # fire off our first update
    href = connection_point_uri_format.format(site_id=1)
    new_cp_specified: ConnectionPointRequest = ConnectionPointRequest(id="1212121212")
    response = await client.post(
        url=href, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)}, content=new_cp_specified.to_xml()
    )
    assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)
    body = read_response_body_string(response)
    assert read_location_header(response) == "/my/custom/prefix" + href
    assert len(body) == 0

    # check it updated
    response = await client.get(href, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)})
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: ConnectionPointResponse = ConnectionPointResponse.from_xml(body)
    assert parsed_response.id == new_cp_specified.id


@pytest.mark.anyio
async def test_connectionpoint_update_bad_xml(client: AsyncClient, connection_point_uri_format: str):
    """Tests malformed XML on the endpoint results in a BadRequest"""

    # The closing tag on ID has an incorrect namespace
    bad_xml = """<ConnectionPoint xmlns="http://csipaus.org/ns"><id>1111111111</csipaus:id></ConnectionPoint>"""

    href = connection_point_uri_format.format(site_id=1)
    response = await client.post(url=href, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)}, content=bad_xml)
    assert_response_header(response, HTTPStatus.BAD_REQUEST)
    assert_error_response(response)


@pytest.mark.anyio
async def test_connectionpoint_update_aggregator_edev_returns_404(
    client: AsyncClient, connection_point_uri_format: str
):
    """Tests that an aggregator can't update the connection point of an aggregator end device"""

    href = connection_point_uri_format.format(site_id=0)
    new_cp_specified: ConnectionPointRequest = ConnectionPointRequest(id="1212121212")
    response = await client.post(
        url=href, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)}, content=new_cp_specified.to_xml()
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
