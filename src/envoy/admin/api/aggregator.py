import logging
import http
import sqlalchemy.exc

from envoy_schema.admin.schema.certificate import CertificatePageResponse, CertificateAssignmentRequest
from envoy_schema.admin.schema.aggregator import AggregatorResponse, AggregatorPageResponse
from envoy_schema.admin.schema import uri
import fastapi
from fastapi_async_sqlalchemy import db

from envoy.admin import manager
from envoy.server import exception
from envoy.server.api import request
from envoy.server.api import error_handler

logger = logging.getLogger(__name__)

router = fastapi.APIRouter()


@router.get(uri.AggregatorListUri, status_code=http.HTTPStatus.OK, response_model=AggregatorPageResponse)
async def get_all_aggregators(
    start: list[int] = fastapi.Query([0]),
    limit: list[int] = fastapi.Query([100]),
) -> AggregatorPageResponse:
    """Endpoint for a paginated list of Aggregator Objects, ordered by aggregator_id attribute.

    Query Param:
        start: list query parameter for the start index value. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 100.

    Returns:
        AggregatorPageResponse

    """
    return await manager.AggregatorManager.fetch_many_aggregators(
        session=db.session,
        start=request.extract_start_from_paging_param(start),
        limit=request.extract_limit_from_paging_param(limit),
    )


@router.get(uri.AggregatorUri, status_code=http.HTTPStatus.OK, response_model=AggregatorResponse)
async def get_aggregator(
    aggregator_id: int,
) -> AggregatorResponse:
    """Endpoint for requesting an Aggregator instance by its unique id,

    Returns:
        AggregatorResponse

    """

    agg = await manager.AggregatorManager.fetch_single_aggregator(session=db.session, aggregator_id=aggregator_id)
    if agg is None:
        raise fastapi.HTTPException(http.HTTPStatus.NOT_FOUND, f"Aggregator with ID {aggregator_id} not found")
    return agg


@router.get(
    uri.AggregatorCertificateListUri,
    status_code=http.HTTPStatus.OK,
    response_model=CertificatePageResponse,
)
async def get_aggregator_certificates(
    aggregator_id: int, start: list[int] = fastapi.Query([0]), limit: list[int] = fastapi.Query([100])
) -> CertificatePageResponse:
    """Endpoint for a paginated list of Aggregator certificates, ordered by certificate id

    Path Params:
        aggregator_id: ID that the query will focus

    Query Params:
        start: list query parameter for the start index value. Default 0.
        limit: list query parameter for the maximum number of objects to return. Default 100.

    Returns:
        CertificatePageResponse
    """
    certs = await manager.CertificateManager.fetch_many_certificates_for_aggregator(
        session=db.session,
        aggregator_id=aggregator_id,
        start=request.extract_start_from_paging_param(start),
        limit=request.extract_limit_from_paging_param(limit),
    )

    if certs is None:
        raise fastapi.HTTPException(http.HTTPStatus.NOT_FOUND, f"Aggregator with ID {aggregator_id} not found")

    return certs


@router.post(
    uri.AggregatorCertificateListUri,
    status_code=http.HTTPStatus.CREATED,
    response_model=None,
)
async def assign_certificates_to_aggregator(
    aggregator_id: int, certificates: list[CertificateAssignmentRequest]
) -> None:
    """Endpoint for assigning certificates to an aggregator.

    Certificates are either created or just assigned. If there is a new expiry provided for
    an existing certificate this will be ignored. To update certificate expiries please refer to the certificate
    modify endpoint.

    Path Params:
        aggregator_id: ID of the aggregator that the certificates will be assigned

    Body:
        certificates: For each certificate to be assigned, it either needs an ID or LFDI supplied. Expiry will be
            ignored for existing certificates. New certificates require an expiry.
    """
    try:
        await manager.CertificateManager.add_many_certificates_for_aggregator(
            session=db.session, aggregator_id=aggregator_id, certs=certificates
        )
    except exception.NotFoundError as err:
        raise error_handler.LoggedHttpException(logger, err, http.HTTPStatus.NOT_FOUND, f"{err}")
    except (exception.InvalidIdError, sqlalchemy.exc.IntegrityError) as err:
        raise error_handler.LoggedHttpException(logger, err, http.HTTPStatus.BAD_REQUEST, f"{err}")


@router.delete(
    uri.AggregatorCertificateUri,
    status_code=http.HTTPStatus.NO_CONTENT,
    response_model=None,
)
async def delete_aggregator_certificate_assignment(aggregator_id: int, certificate_id: int) -> None:
    """Deletion of an aggregator certificate assignment.

    Does not delete the certificate entry itself.

    Path Params:
        aggregator_id: ID of aggregator
        certificate_id: ID of certificate
    """
    try:
        await manager.CertificateManager.unassign_certificate_for_aggregator(db.session, aggregator_id, certificate_id)
    except exception.NotFoundError as err:
        raise error_handler.LoggedHttpException(logger, err, http.HTTPStatus.NOT_FOUND, f"{err}")
