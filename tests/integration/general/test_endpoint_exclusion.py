from http import HTTPStatus
import urllib
import pytest

from httpx import AsyncClient
from envoy_schema.server.schema.uri import TimeUri, EndDeviceUri

from envoy.server.endpoint_exclusion import HTTPMethod

from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT
from tests.integration.integration_server import cert_header


@pytest.mark.exclude_endpoints([(HTTPMethod.HEAD, TimeUri)])
@pytest.mark.anyio
async def test_exclude_endpoints_no_method(client: AsyncClient):
    """Test basic filter usage where route still exist but a specific method has been removed."""
    # Act
    resp = await client.head(TimeUri, headers={cert_header: urllib.parse.quote(TEST_CERTIFICATE_FINGERPRINT)})

    # Assert
    assert resp.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.exclude_endpoints([(HTTPMethod.GET, EndDeviceUri)])
@pytest.mark.anyio
async def test_exclude_endpoints_no_method_formattable_uri(client: AsyncClient):
    """Test basic filter usage where route still exist but a specific method has been removed,
    using a formattable uri."""
    # Act
    resp = await client.get(
        EndDeviceUri.format(site_id=1),  # site included in base_config.sql
        headers={cert_header: urllib.parse.quote(TEST_CERTIFICATE_FINGERPRINT)},
    )

    # Assert
    assert resp.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.exclude_endpoints([(HTTPMethod.HEAD, TimeUri), (HTTPMethod.GET, TimeUri)])
@pytest.mark.anyio
async def test_exclude_endpoints_no_route(client: AsyncClient):
    """Test where all methods of a route have been removed, expecting the entire route to be removed i.e. NOT FOUND"""
    # Act
    resp = await client.head(TimeUri, headers={cert_header: urllib.parse.quote(TEST_CERTIFICATE_FINGERPRINT)})

    # Assert
    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.exclude_endpoints(
    [(HTTPMethod.HEAD, EndDeviceUri), (HTTPMethod.GET, EndDeviceUri), (HTTPMethod.DELETE, EndDeviceUri)]
)
@pytest.mark.anyio
async def test_exclude_endpoints_no_route_formattable_uri(client: AsyncClient):
    """Test where all methods of a route have been removed, expecting the entire route to be removed i.e. NOT FOUND"""
    # Act
    resp = await client.head(
        EndDeviceUri.format(site_id=1), headers={cert_header: urllib.parse.quote(TEST_CERTIFICATE_FINGERPRINT)}
    )

    # Assert
    assert resp.status_code == HTTPStatus.NOT_FOUND
