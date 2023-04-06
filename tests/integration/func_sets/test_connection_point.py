import urllib.parse
from http import HTTPStatus
from typing import Optional

import pytest
from httpx import AsyncClient
from psycopg import Connection

from envoy.server.schema.csip_aus.connection_point import ConnectionPointRequest, ConnectionPointResponse
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_PEM as AGG_1_VALID_PEM
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_PEM as AGG_2_VALID_PEM
from tests.data.certificates.certificate5 import TEST_CERTIFICATE_PEM as AGG_3_VALID_PEM
from tests.integration.integration_server import cert_pem_header
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
    "test_detail",
    [(1, '1111111111', AGG_1_VALID_PEM, HTTPStatus.OK),
     (2, '2222222222', AGG_1_VALID_PEM, HTTPStatus.OK),
     (3, '3333333333', AGG_2_VALID_PEM, HTTPStatus.OK),
     (4, '4444444444', AGG_1_VALID_PEM, HTTPStatus.OK),

     (1, None, AGG_2_VALID_PEM, HTTPStatus.NOT_FOUND),  # Agg 2 can't access site 1
     (3, None, AGG_3_VALID_PEM, HTTPStatus.NOT_FOUND),  # Agg 3 can't access site 3
     (99, None, AGG_1_VALID_PEM, HTTPStatus.NOT_FOUND),  # Site 99 does not exist
     ])
@pytest.mark.anyio
async def test_get_connectionpoint(client: AsyncClient, connection_point_uri_format: str, test_detail: tuple[int, Optional[str], str, HTTPStatus]):
    """Tests getting a variety of connection points for the sites - tests successful / unsuccessful responses"""
    (site_id, expected_nmi, cert, expected_status_response) = test_detail

    response = await client.get(connection_point_uri_format.format(site_id=site_id), headers={cert_pem_header: urllib.parse.quote(cert)})
    assert_response_header(response, expected_status_response)

    if expected_status_response == HTTPStatus.OK:
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response: ConnectionPointResponse = ConnectionPointResponse.from_xml(body)
        assert parsed_response.id == expected_nmi
    else:
        assert_error_response(response)


@pytest.mark.anyio
async def test_get_connectionpoint_none_nmi(client: AsyncClient, pg_base_config: Connection, connection_point_uri_format: str):
    """Tests that a site with a None nmi will return empty string """

    with pg_base_config.cursor() as cursor:
        cursor.execute("UPDATE public.site SET \"nmi\" = NULL WHERE \"site_id\" = 1")
        pg_base_config.commit()

    response = await client.get(connection_point_uri_format.format(site_id=1), headers={cert_pem_header: urllib.parse.quote(AGG_1_VALID_PEM)})
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: ConnectionPointResponse = ConnectionPointResponse.from_xml(body)
    assert parsed_response.id is None or parsed_response.id == '', "Expected empty id"


@pytest.mark.anyio
async def test_connectionpoint_update_and_fetch(client: AsyncClient, connection_point_uri_format: str):
    """Tests that connection points can be updated / fetched"""

    # fire off our first update
    href = connection_point_uri_format.format(site_id=1)
    new_cp_specified: ConnectionPointRequest = ConnectionPointRequest(id="1212121212")
    response = await client.post(
        url=href,
        headers={cert_pem_header: urllib.parse.quote(AGG_1_VALID_PEM)},
        content=new_cp_specified.to_xml()
    )
    assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)
    body = read_response_body_string(response)
    assert read_location_header(response) == href
    assert len(body) == 0

    # check it updated
    response = await client.get(href, headers={cert_pem_header: urllib.parse.quote(AGG_1_VALID_PEM)})
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: ConnectionPointResponse = ConnectionPointResponse.from_xml(body)
    assert parsed_response.id == new_cp_specified.id
