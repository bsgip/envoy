from collections.abc import Sized
from http import HTTPStatus

from fastapi import HTTPException

# The maximum number of entities that can be submitted in a single "bulk" admin request. Larger payloads should be
# split across multiple requests (this is to prevent the ORM choking on massive inserts/updates)
MAX_ADMIN_LIST_SUBMISSION = 500


def validate_list_submission_size(items: Sized, max_items: int = MAX_ADMIN_LIST_SUBMISSION) -> None:
    """Raises a HTTPException (BadRequest) if items has more than max_items elements"""
    if len(items) > max_items:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            f"Request contains {len(items)} items which exceeds the maximum of {max_items}.",
        )
