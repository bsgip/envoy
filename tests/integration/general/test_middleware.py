import urllib
from http import HTTPStatus

from psycopg import Connection
import pytest
from httpx import AsyncClient
import envoy_schema.server.schema.uri as uris
from envoy_schema.server.schema.sep2.end_device import EndDeviceRequest
from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointRequest
from assertical.fake.generator import generate_class_instance

from envoy.server.api.depends.csipaus import CSIPV11aXmlNsOptInMiddleware


from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as AGG_1_VALID_CERT
from tests.integration.integration_server import cert_header


EQUIVALENT_NS_MAP = CSIPV11aXmlNsOptInMiddleware.equivalent_ns_map


@pytest.mark.anyio
@pytest.mark.csipv11a_xmlns_optin_middleware
@pytest.mark.parametrize(
    "xml_body, url, opt_in, expected_http_status",
    [
        (
            generate_class_instance(ConnectionPointRequest)
            .to_xml()
            .replace(EQUIVALENT_NS_MAP[1], EQUIVALENT_NS_MAP[0]),  # request uses v1.1
            uris.ConnectionPointUri.format(site_id=1),
            False,
            HTTPStatus.CREATED,
        ),
        (
            generate_class_instance(ConnectionPointRequest)
            .to_xml()
            .replace(EQUIVALENT_NS_MAP[1], EQUIVALENT_NS_MAP[0]),  # request uses v1.1
            uris.ConnectionPointUri.format(site_id=1),
            True,
            HTTPStatus.BAD_REQUEST,
        ),
        (
            generate_class_instance(ConnectionPointRequest).to_xml(),  # request uses v1.1a
            uris.ConnectionPointUri.format(site_id=1),
            False,
            HTTPStatus.CREATED,
        ),
        (
            generate_class_instance(ConnectionPointRequest).to_xml(),  # request uses v1.1a
            uris.ConnectionPointUri.format(site_id=1),
            True,
            HTTPStatus.CREATED,
        ),
        (
            generate_class_instance(EndDeviceRequest, deviceCategory="0")
            .to_xml()
            .replace(EQUIVALENT_NS_MAP[1], EQUIVALENT_NS_MAP[0]),  # request uses v1.1
            uris.EndDeviceListUri.format(site_id=1),
            False,
            HTTPStatus.CREATED,
        ),
        (
            generate_class_instance(EndDeviceRequest, deviceCategory="0").to_xml(),  # request uses v1.1a
            uris.EndDeviceListUri.format(site_id=1),
            False,
            HTTPStatus.CREATED,
        ),
    ],
)
async def test_post_CSIPV11aXmlNsOptInMiddleware(
    client: AsyncClient,
    pg_base_config: Connection,
    xml_body: bytes,
    url: str,
    opt_in: bool,
    expected_http_status: HTTPStatus,
) -> None:

    headers = {
        cert_header: urllib.parse.quote(AGG_1_VALID_CERT),
    }
    if opt_in:
        headers[CSIPV11aXmlNsOptInMiddleware.opt_in_header_name] = ""

    response = await client.post(
        url,
        content=xml_body,
        headers=headers,
    )
    assert response.status_code == expected_http_status


@pytest.mark.anyio
@pytest.mark.csipv11a_xmlns_optin_middleware
@pytest.mark.parametrize(
    "url, opt_in, expected_http_status, expected_csip_ns",
    [
        (
            "edev/1/cp",
            False,
            HTTPStatus.OK,
            EQUIVALENT_NS_MAP[0],
        ),
        ("edev/1/cp", True, HTTPStatus.OK, EQUIVALENT_NS_MAP[1]),
        (uris.DERCapabilityUri.format(site_id="1", der_id="1"), False, HTTPStatus.OK, EQUIVALENT_NS_MAP[0]),
        (uris.DERCapabilityUri.format(site_id="1", der_id="1"), True, HTTPStatus.OK, EQUIVALENT_NS_MAP[1]),
        (uris.DERSettingsUri.format(site_id="1", der_id="1"), False, HTTPStatus.OK, EQUIVALENT_NS_MAP[0]),
        (uris.DERSettingsUri.format(site_id="1", der_id="1"), True, HTTPStatus.OK, EQUIVALENT_NS_MAP[1]),
    ],
)
async def test_get_CSIPV11aXmlNsOptInMiddleware(
    client: AsyncClient,
    pg_base_config: Connection,
    url: str,
    opt_in: bool,
    expected_http_status: HTTPStatus,
    expected_csip_ns: bytes,
) -> None:

    headers = {
        cert_header: urllib.parse.quote(AGG_1_VALID_CERT),
    }
    if opt_in:
        headers[CSIPV11aXmlNsOptInMiddleware.opt_in_header_name] = ""

    response = await client.get(
        url,
        headers=headers,
    )
    assert response.status_code == expected_http_status
    if response.status_code == HTTPStatus.OK:
        assert expected_csip_ns in response.content
