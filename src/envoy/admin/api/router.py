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

    pass


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

    # TODO what validation exists on DOEs?
    # TODO should the DOE model take an dynamic_operating_envelope_id
    # or should that be autoincremented?
    # TODO should the site id be passed as a separate arg? Rather than in the DOE model

    committed = await AdminManager.commit_doe(db.session, doe)

    if not committed:
        pass
        # return Response(status_code=HTTPStatus.IT_BROKED)

    return Response(
        status_code=HTTPStatus.CREATED, headers={LOCATION_HEADER_NAME: uri.AdminDoeUri.format(site_id=site_id)}
    )
