import logging
from http import HTTPStatus

from fastapi import APIRouter, Request, Response

from envoy.admin.model.doe import DynamicOperatingEnvelopeAdmin
from envoy.admin.schema import uri

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(uri.AdminTariffUri, status_code=HTTPStatus.OK)
async def post_tariffgeneratedrate(site_id: int, request: Request):
    """
    TODO

    This endpoint receives a TariffGeneratedRate and commits it
    to the db.

    (Will have to reference a parent tariff)
    """

    return 1


@router.post(uri.AdminDoeUri, status_code=HTTPStatus.OK)
async def post_doe(doe: DynamicOperatingEnvelopeAdmin):
    """
    TODO

    This endpoint receives a DynamicOperatingEnvelope and
    commits it to the db. The DOE comes from ??

    A DOE is comprised of a:
    primary key dynamicoperatingenvelopeid
    foreign key siteid
    doe/creation details
    """

    return 1
