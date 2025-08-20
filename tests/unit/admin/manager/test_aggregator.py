import pytest
import pytest_mock
from envoy_schema.admin.schema.aggregator import AggregatorRequest

from envoy.admin import manager
from envoy.server import exception


@pytest.fixture
def mock_crud(mocker: pytest_mock.MockerFixture) -> pytest_mock.AsyncMockType:
    return mocker.patch("envoy.admin.crud.aggregator", new=mocker.AsyncMock())


@pytest.fixture
def mock_select_aggregator(mocker: pytest_mock.MockerFixture) -> pytest_mock.AsyncMockType:
    return mocker.patch("envoy.admin.manager.aggregator.select_aggregator", new=mocker.AsyncMock())


@pytest.fixture
def mock_mapper(mocker: pytest_mock.MockerFixture) -> pytest_mock.AsyncMockType:
    return mocker.patch("envoy.admin.mapper.AggregatorMapper", new=mocker.AsyncMock())


@pytest.mark.anyio
async def test_add_new_aggregator(mocker: pytest_mock.MockerFixture, mock_crud: pytest_mock.AsyncMockType) -> None:
    """Confirm correct calls for add_new_aggregator() method"""
    async with mocker.AsyncMock() as session:
        aggregator = AggregatorRequest(name="some new aggregator")
        await manager.AggregatorManager.add_new_aggregator(session, aggregator)
        mock_crud.insert_single_aggregator.assert_called_once()
        session.commit.assert_called_once()


@pytest.mark.anyio
async def test_update_existing_aggregator(
    mocker: pytest_mock.MockerFixture,
    mock_crud: pytest_mock.AsyncMockType,
    mock_select_aggregator: pytest_mock.AsyncMockType,
) -> None:
    """Confirm correct calls for update_existing_aggregator() method"""
    async with mocker.AsyncMock() as session:
        aggregator = AggregatorRequest(name="renamed aggregator")
        await manager.AggregatorManager.update_existing_aggregator(session, 1111, aggregator)
        mock_select_aggregator.assert_called_once()
        mock_crud.update_single_aggregator.assert_called_once()
        session.commit.assert_called_once()


@pytest.mark.anyio
async def test_update_existing_aggregator_non_aggregator(
    mocker: pytest_mock.MockerFixture,
    mock_select_aggregator: pytest_mock.AsyncMockType,
) -> None:
    """Confirm update_existing_aggregator() method raises for non-existing aggregator"""
    async with mocker.AsyncMock() as session:
        aggregator = AggregatorRequest(name="won't be renamed aggregator")
        mock_select_aggregator.return_value = None
        with pytest.raises(exception.NotFoundError):
            await manager.AggregatorManager.update_existing_aggregator(session, 1111, aggregator)
