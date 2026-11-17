from http import HTTPStatus

import pytest
from fastapi import HTTPException

from envoy.admin.api.validation import MAX_ADMIN_LIST_SUBMISSION, validate_list_submission_size


@pytest.mark.parametrize("count", [0, 1, MAX_ADMIN_LIST_SUBMISSION - 1, MAX_ADMIN_LIST_SUBMISSION])
def test_validate_list_submission_size_ok(count: int):
    validate_list_submission_size([0] * count)


@pytest.mark.parametrize("count", [MAX_ADMIN_LIST_SUBMISSION + 1, MAX_ADMIN_LIST_SUBMISSION * 10])
def test_validate_list_submission_size_too_large(count: int):
    with pytest.raises(HTTPException) as exc_info:
        validate_list_submission_size([0] * count)
    assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST


def test_validate_list_submission_size_custom_max():
    validate_list_submission_size([1, 2], max_items=2)
    with pytest.raises(HTTPException):
        validate_list_submission_size([1, 2, 3], max_items=2)
