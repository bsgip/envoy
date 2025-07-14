import logging
import http

from envoy_schema.admin.schema.certificate import (
    CertificatePageResponse,
    CertificateRequest,
    CertificateResponse,
)
from envoy_schema.admin.schema import uri
import fastapi
from fastapi_async_sqlalchemy import db

from envoy.admin import manager
from envoy.server import exception
from envoy.server.api import request
from envoy.server.api import error_handler

logger = logging.getLogger(__name__)

router = fastapi.APIRouter()


@router.get(uri.CertificateListUri, status_code=http.HTTPStatus.OK, response_model=CertificatePageResponse)
async def get_all_certificates(
    start: list[int] = fastapi.Query([0]),
    limit: list[int] = fastapi.Query([100]),
) -> CertificatePageResponse:
    """Endpoint for a paginated list of Certificate Objects, ordered by certificate_id attribute.

    Query Param:
        start: list query parameter for the start index value. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 100.

    Returns:
        CertificatePageResponse

    """
    return await manager.CertificateManager.fetch_many_certificates(
        session=db.session,
        start=request.extract_start_from_paging_param(start),
        limit=request.extract_limit_from_paging_param(limit),
    )


@router.get(uri.CertificateUri, status_code=http.HTTPStatus.OK, response_model=CertificateResponse)
async def get_certificate(
    certificate_id: int,
) -> CertificateResponse:
    """Endpoint for requesting a Certificate instance by its unique id,

    Returns:
        AggregatorResponse

    """

    certificate = await manager.CertificateManager.fetch_single_certificate(
        session=db.session, certificate_id=certificate_id
    )
    if certificate is None:
        raise fastapi.HTTPException(http.HTTPStatus.NOT_FOUND, f"Certificate with ID {certificate_id} not found")
    return certificate


@router.post(uri.CertificateListUri, status_code=http.HTTPStatus.CREATED, response_model=None)
async def create_certificate(certificate: CertificateRequest, response: fastapi.Response) -> None:
    """Create a certificate"""
    certificate_id = await manager.CertificateManager.add_new_certificate(db.session, certificate)
    response.headers["Location"] = uri.CertificateUri.format(certificate_id=certificate_id)


@router.put(uri.CertificateUri, status_code=http.HTTPStatus.OK, response_model=None)
async def update_certificate(certificate_id: int, certificate: CertificateRequest) -> None:
    """Endpoint for updating a Certificate"""
    try:
        await manager.CertificateManager.update_existing_certificate(db.session, certificate_id, certificate)
    except exception.NotFoundError as err:
        raise error_handler.LoggedHttpException(logger, err, http.HTTPStatus.NOT_FOUND, f"{err}")


@router.delete(uri.CertificateUri, status_code=http.HTTPStatus.NO_CONTENT, response_model=None)
async def delete_certificate(certificate_id: int) -> None:
    """Deletion of a certificate"""
    try:
        await manager.CertificateManager.delete_certificate(db.session, certificate_id)
    except exception.NotFoundError as err:
        raise error_handler.LoggedHttpException(logger, err, http.HTTPStatus.NOT_FOUND, f"{err}")
