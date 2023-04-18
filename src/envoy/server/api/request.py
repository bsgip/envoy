
from http import HTTPStatus

from fastapi import HTTPException, Request


def extract_aggregator_id(request: Request) -> int:
    """Fetches the aggregator id assigned to an incoming request (by the auth dependencies).

    raises a HTTPException if the id does not exist"""
    id = None if request.state is None else request.state.aggregator_id
    if id is None:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                            detail="aggregator_id has not been been extracted correctly by Envoy middleware.")
    return id
