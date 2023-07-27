import unittest.mock as mock
from http import HTTPStatus

import jwt
import pytest
from fastapi import HTTPException, Request
from starlette.datastructures import Headers

from envoy.server.api.auth.azure import AzureADManagedIdentityConfig, UnableToContactAzureServicesError
from envoy.server.api.depends.azure_ad_auth import AzureADAuthDepends
from envoy.server.exception import UnauthorizedError


@pytest.mark.anyio
@mock.patch("envoy.server.api.depends.azure_ad_auth.validate_azure_ad_token")
async def test_valid_auth(mock_validate_azure_ad_token: mock.MagicMock):
    """Makes sure the basic requests are decomposed and forwarded on to validate_azure_ad_token"""
    raw_token = "abc123-DEF=="
    req = Request(
        {
            "type": "http",
            "headers": Headers({"Authorization": f"beAReR {raw_token}"}).raw,  # Testing case sensitivity
        }
    )
    tenant_id = "tenant-id-123"
    client_id = "client-id-132"
    valid_issuer = "valid-issuer-12456"
    expected_cfg = AzureADManagedIdentityConfig(tenant_id=tenant_id, client_id=client_id, valid_issuer=valid_issuer)

    depends = AzureADAuthDepends(tenant_id, client_id, valid_issuer)

    await depends(req)

    mock_validate_azure_ad_token.assert_called_once_with(expected_cfg, raw_token)


@pytest.mark.anyio
@mock.patch("envoy.server.api.depends.azure_ad_auth.validate_azure_ad_token")
async def test_missing_auth(mock_validate_azure_ad_token: mock.MagicMock):
    """Missing Authorization header results in a HTTPException"""
    req = Request(
        {
            "type": "http",
            "headers": Headers({}).raw,
        }
    )
    tenant_id = "tenant-id-123"
    client_id = "client-id-132"
    valid_issuer = "valid-issuer-12456"

    depends = AzureADAuthDepends(tenant_id, client_id, valid_issuer)

    with pytest.raises(HTTPException):
        await depends(req)

    mock_validate_azure_ad_token.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.server.api.depends.azure_ad_auth.validate_azure_ad_token")
async def test_missing_bearer(mock_validate_azure_ad_token: mock.MagicMock):
    """Missing Authorization header results in a HTTPException"""
    raw_token = "abc-123-DEF"
    req = Request(
        {
            "type": "http",
            "headers": Headers({"Authorization": f"{raw_token}"}).raw,  # No bearer identification
        }
    )
    tenant_id = "tenant-id-123"
    client_id = "client-id-132"
    valid_issuer = "valid-issuer-12456"

    depends = AzureADAuthDepends(tenant_id, client_id, valid_issuer)

    with pytest.raises(HTTPException):
        await depends(req)

    mock_validate_azure_ad_token.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.server.api.depends.azure_ad_auth.validate_azure_ad_token")
async def test_non_bearer_auth(mock_validate_azure_ad_token: mock.MagicMock):
    """Malformed Authorization header results in a HTTPException"""
    raw_token = "abc123-DEF=="
    req = Request(
        {
            "type": "http",
            "headers": Headers({"Authorization": f"Basic {raw_token}"}).raw,
        }
    )
    tenant_id = "tenant-id-123"
    client_id = "client-id-132"
    valid_issuer = "valid-issuer-12456"

    depends = AzureADAuthDepends(tenant_id, client_id, valid_issuer)

    with pytest.raises(HTTPException):
        await depends(req)

    mock_validate_azure_ad_token.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.server.api.depends.azure_ad_auth.validate_azure_ad_token")
async def test_validate_token_auth_error(mock_validate_azure_ad_token: mock.MagicMock):
    """If validate_azure_ad_token raises an error - ensure it's mapped to an appropriate HTTPException"""
    raw_token = "abc123-DEF=="
    req = Request(
        {
            "type": "http",
            "headers": Headers({"Authorization": f"Bearer {raw_token}"}).raw,
        }
    )
    tenant_id = "tenant-id-123"
    client_id = "client-id-132"
    valid_issuer = "valid-issuer-12456"
    expected_cfg = AzureADManagedIdentityConfig(tenant_id=tenant_id, client_id=client_id, valid_issuer=valid_issuer)

    mock_validate_azure_ad_token.side_effect = UnauthorizedError("mock exception")

    depends = AzureADAuthDepends(tenant_id, client_id, valid_issuer)

    with pytest.raises(HTTPException) as ex:
        await depends(req)
    assert ex.value.status_code == HTTPStatus.UNAUTHORIZED

    mock_validate_azure_ad_token.assert_called_once_with(expected_cfg, raw_token)


@pytest.mark.anyio
@mock.patch("envoy.server.api.depends.azure_ad_auth.validate_azure_ad_token")
async def test_validate_token_unable_to_contact_error(mock_validate_azure_ad_token: mock.MagicMock):
    """If validate_azure_ad_token raises an error - ensure it's mapped to an appropriate HTTPException"""
    raw_token = "abc123-DEF=="
    req = Request(
        {
            "type": "http",
            "headers": Headers({"Authorization": f"Bearer {raw_token}"}).raw,
        }
    )
    tenant_id = "tenant-id-123"
    client_id = "client-id-132"
    valid_issuer = "valid-issuer-12456"
    expected_cfg = AzureADManagedIdentityConfig(tenant_id=tenant_id, client_id=client_id, valid_issuer=valid_issuer)

    mock_validate_azure_ad_token.side_effect = UnableToContactAzureServicesError("mock exception")

    depends = AzureADAuthDepends(tenant_id, client_id, valid_issuer)

    with pytest.raises(HTTPException) as ex:
        await depends(req)
    assert ex.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    mock_validate_azure_ad_token.assert_called_once_with(expected_cfg, raw_token)


@pytest.mark.anyio
@mock.patch("envoy.server.api.depends.azure_ad_auth.validate_azure_ad_token")
async def test_validate_token_jwt_error(mock_validate_azure_ad_token: mock.MagicMock):
    """If validate_azure_ad_token raises an error - ensure it's mapped to an appropriate HTTPException"""
    raw_token = "abc123-DEF=="
    req = Request(
        {
            "type": "http",
            "headers": Headers({"Authorization": f"Bearer {raw_token}"}).raw,
        }
    )
    tenant_id = "tenant-id-123"
    client_id = "client-id-132"
    valid_issuer = "valid-issuer-12456"
    expected_cfg = AzureADManagedIdentityConfig(tenant_id=tenant_id, client_id=client_id, valid_issuer=valid_issuer)

    mock_validate_azure_ad_token.side_effect = jwt.ExpiredSignatureError("mock exception")

    depends = AzureADAuthDepends(tenant_id, client_id, valid_issuer)

    with pytest.raises(HTTPException) as ex:
        await depends(req)
    assert ex.value.status_code == HTTPStatus.FORBIDDEN

    mock_validate_azure_ad_token.assert_called_once_with(expected_cfg, raw_token)
