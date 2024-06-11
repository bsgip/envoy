from datetime import datetime
import pytest
import unittest.mock as mock

from envoy.server.api.depends.lfdi_auth import update_client_id_details_cache
from envoy.server.cache import ExpiringValue
from envoy.server.crud.auth import ClientIdDetails
from tests.unit.mocks import assert_mock_session, create_async_result, create_mock_session


def dt(seed) -> datetime:
    return datetime(2024, 1, 2, seed % 24, seed % 60)


def cid(seed: int) -> ClientIdDetails:
    return ClientIdDetails(str(seed), seed * 37, dt(seed))


@pytest.mark.anyio
@pytest.mark.parametrize(
    "client_details, expected",
    [
        ([], {}),
        ([cid(1)], {"1": ExpiringValue(dt(1), cid(1))}),
        ([cid(1), cid(22)], {"1": ExpiringValue(dt(1), cid(1)), "22": ExpiringValue(dt(22), cid(22))}),
        (
            [cid(11), cid(22), cid(11)],
            {"11": ExpiringValue(dt(11), cid(11)), "22": ExpiringValue(dt(22), cid(22))},
        ),  # contains duplicates
    ],
)
@mock.patch("envoy.server.api.depends.lfdi_auth.db")
@mock.patch("envoy.server.api.depends.lfdi_auth.select_all_client_id_details")
async def test_update_client_id_details_cache(
    mock_select_all_client_id_details: mock.MagicMock,
    mock_db: mock.MagicMock,
    client_details: list[ClientIdDetails],
    expected: dict[str, ClientIdDetails],
):
    """In addition to asserting the return value of update_client_id_details_cache, we test to validate the that the DB
    session is reset (as desired) by asserting __aexit__ is called by the context manager. We test this
    here because it is a pattern unique to this particular function.
    """
    # arrange
    mock_session = create_mock_session()
    mock_db.session = mock_session
    mock_db.return_value = mock.Mock()
    mock_db.return_value.__aenter__ = mock.Mock(return_value=create_async_result(None))
    mock_db.return_value.__aexit__ = mock.Mock(return_value=create_async_result(None))

    mock_select_all_client_id_details.return_value = client_details

    # act
    result = await update_client_id_details_cache(None)

    # assert
    assert isinstance(result, dict)
    assert all([isinstance(k, str) for k in result.keys()])
    assert all([isinstance(v, ExpiringValue) for v in result.values()])
    assert all([isinstance(v.value, ClientIdDetails) for v in result.values()])
    assert all([k.value.expiry == k.expiry for k in result.values()])
    assert expected == result

    mock_select_all_client_id_details.assert_called_once_with(mock_session)
    assert_mock_session(mock_session)
    mock_db.return_value.__aenter__.assert_called_once()
    mock_db.return_value.__aexit__.assert_called_once()
