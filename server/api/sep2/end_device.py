import logging

from fastapi import APIRouter, Request
from fastapi_async_sqlalchemy import db

from server.api.response import XmlResponse
from server.manager.end_device import EndDeviceListManager, EndDeviceManager

logger = logging.getLogger(__name__)


router = APIRouter()


@router.head("/edev/{id1}")
@router.get(
    "/edev/{id1}",
    status_code=200,
)
async def get_enddevice(id1: int, request: Request):
    """Responds with a single EndDevice resource.

    Args:
        id1: Path parameter, the target EndDevice registration number.
        request: FastAPI request object.

    Returns:
        fastapi.Response object.

    """

    edev = await database.fetch_one(query=query)

    if not edev:
        raise HTTPException(status_code=404, detail=f"EndDevice not found.")

    edev_dict = dict(edev)

    edev_dict = {
        "meta_": {
            "id1": f'{edev_dict["reg_no"]}',
            "derlist_all": await der.get_der_list_count(edev_dict["reg_no"]),
            "fsalist_all": await function_set_assignments.get_fsa_list_count(
                edev_dict["reg_no"]
            ),
        },
        **dict(edev),
    }

    return XmlResponse()
