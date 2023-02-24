import pytest


@pytest.fixture
def mock_db(mocker, request):
    db = mocker.patch(request.param).object().return_value
    db.session = None
    return db
