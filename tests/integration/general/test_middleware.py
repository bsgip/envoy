import urllib
from http import HTTPStatus

from psycopg import Connection
import pytest
from httpx import AsyncClient
import envoy_schema.server.schema.uri as uris

from envoy.server.api.depends.csipaus import CSIPV11aXmlNsOptInMiddleware
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as AGG_1_VALID_CERT
from tests.integration.integration_server import cert_header


CP_PAYLOAD_0 = """
    <csipaus:ConnectionPoint
        xmlns="urn:ieee:std:2030.5:ns"
        xmlns:csipaus="{csipaus_xmlns}"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <csipaus:id>"12321"</csipaus:id>
    </csipaus:ConnectionPoint>
    """


@pytest.mark.anyio
@pytest.mark.csipv11a_xmlns_optin_middleware
@pytest.mark.parametrize(
    "csipaus_xmlns, formattable_payload, url, opt_in, expected_http_status",
    [
        ("http://csipaus.org/ns", CP_PAYLOAD_0, "edev/1/cp", False, HTTPStatus.CREATED),
        ("http://csipaus.org/ns", CP_PAYLOAD_0, "edev/1/cp", True, HTTPStatus.BAD_REQUEST),
        ("https://csipaus.org/ns", CP_PAYLOAD_0, "edev/1/cp", False, HTTPStatus.CREATED),
        ("https://csipaus.org/ns", CP_PAYLOAD_0, "edev/1/cp", True, HTTPStatus.CREATED),
        ("invalid", CP_PAYLOAD_0, "edev/1/cp", True, HTTPStatus.BAD_REQUEST),
        ("invalid", CP_PAYLOAD_0, "edev/1/cp", False, HTTPStatus.BAD_REQUEST),
    ],
)
async def test_CSIPV11aXmlNsOptInMiddleware(
    client: AsyncClient,
    pg_base_config: Connection,
    csipaus_xmlns: str,
    formattable_payload: str,
    url: str,
    opt_in: bool,
    expected_http_status: HTTPStatus,
):
    xml_body = formattable_payload.format(csipaus_xmlns=csipaus_xmlns)

    headers = {
        cert_header: urllib.parse.quote(AGG_1_VALID_CERT),
    }
    if opt_in:
        headers[CSIPV11aXmlNsOptInMiddleware.opt_in_header_name] = ""

    response = await client.post(
        url,
        content=xml_body.encode("utf-8"),
        headers=headers,
    )
    assert response.status_code == expected_http_status
