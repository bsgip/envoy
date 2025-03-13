import unittest.mock as mock
from datetime import datetime

import pytest
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from assertical.fake.sqlalchemy import assert_mock_session, create_mock_session
from envoy_schema.server.schema.sep2.response import Response, ResponseListResponse, ResponseSet, ResponseSetList

from envoy.server.exception import NotFoundError
from envoy.server.manager.response import ResponseManager
from envoy.server.mapper.sep2.mrid import MridMapper, ResponseSetType
from envoy.server.model.response import DynamicOperatingEnvelopeResponse, TariffGeneratedRateResponse
from envoy.server.request_scope import DeviceOrAggregatorRequestScope


@mock.patch("envoy.server.manager.response.ResponseSetMapper")
@pytest.mark.parametrize("rst", ResponseSetType)
def test_fetch_response_set_for_scope(mock_ResponseMapper: mock.MagicMock, rst: ResponseSetType):
    """Sanity check we are offloading to the mapper"""
    # Arrange
    scope = generate_class_instance(DeviceOrAggregatorRequestScope)
    mock_map_result = generate_class_instance(ResponseSet)
    mock_ResponseMapper.map_to_set_response = mock.Mock(return_value=mock_map_result)

    # Act
    actual = ResponseManager.fetch_response_set_for_scope(scope, rst)

    # Assert
    assert actual is mock_map_result
    mock_ResponseMapper.map_to_set_response.assert_called_once_with(scope, rst)


@pytest.mark.parametrize(
    "start, limit, expected_rst",
    [
        (0, 99, [ResponseSetType.TARIFF_GENERATED_RATES, ResponseSetType.DYNAMIC_OPERATING_ENVELOPES]),
        (1, 99, [ResponseSetType.DYNAMIC_OPERATING_ENVELOPES]),
        (1, 1, [ResponseSetType.DYNAMIC_OPERATING_ENVELOPES]),
        (0, 1, [ResponseSetType.TARIFF_GENERATED_RATES]),
        (0, 0, []),
        (99, 99, []),
    ],
)
def test_fetch_response_set_list_for_scope_pagination(start: int, limit: int, expected_rst: list[ResponseSetType]):
    """Tests that the manager implemented pagination for ResponseSet's works as expected"""
    # Arrange
    scope = generate_class_instance(DeviceOrAggregatorRequestScope)

    # Act
    result = ResponseManager.fetch_response_set_list_for_scope(scope, start, limit)

    # Assert
    assert isinstance(result, ResponseSetList)
    assert_list_type(ResponseSet, result.ResponseSet_, len(expected_rst))
    assert result.all_ == len(ResponseSetType)
    assert result.results == len(expected_rst)

    # Check the response is the sets we expected
    # We don't need to check the models too closely - the mapper unit tests will do that
    for expected, actual_set in zip(expected_rst, result.ResponseSet_):
        assert actual_set.mRID == MridMapper.encode_response_set_mrid(scope, expected)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.response.ResponseMapper.map_to_price_response")
@mock.patch("envoy.server.manager.response.ResponseMapper.map_to_doe_response")
@mock.patch("envoy.server.manager.response.select_doe_response_for_scope")
@mock.patch("envoy.server.manager.response.select_rate_response_for_scope")
async def test_fetch_response_for_scope_doe_exists(
    mock_select_rate_response_for_scope: mock.MagicMock,
    mock_select_doe_response_for_scope: mock.MagicMock,
    mock_map_to_doe_response: mock.MagicMock,
    mock_map_to_price_response: mock.MagicMock,
):
    """Checks that the flows for a response work OK with DOEs"""
    # Arrange
    scope = generate_class_instance(DeviceOrAggregatorRequestScope)
    response_obj = generate_class_instance(DynamicOperatingEnvelopeResponse)
    mapped_obj = generate_class_instance(Response)
    mock_session = create_mock_session()
    response_id = 65314141

    mock_select_doe_response_for_scope.return_value = response_obj
    mock_map_to_doe_response.return_value = mapped_obj

    # Act
    result = await ResponseManager.fetch_response_for_scope(
        mock_session, scope, ResponseSetType.DYNAMIC_OPERATING_ENVELOPES, response_id
    )

    # Assert
    assert result is mapped_obj
    assert_mock_session(mock_session)
    mock_select_rate_response_for_scope.assert_not_called()
    mock_map_to_price_response.assert_not_called()
    mock_select_doe_response_for_scope.assert_called_once_with(
        mock_session, scope.aggregator_id, scope.site_id, response_id
    )
    mock_map_to_doe_response.assert_called_once_with(scope, response_obj)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.response.ResponseMapper.map_to_price_response")
@mock.patch("envoy.server.manager.response.ResponseMapper.map_to_doe_response")
@mock.patch("envoy.server.manager.response.select_doe_response_for_scope")
@mock.patch("envoy.server.manager.response.select_rate_response_for_scope")
async def test_fetch_response_for_scope_doe_missing(
    mock_select_rate_response_for_scope: mock.MagicMock,
    mock_select_doe_response_for_scope: mock.MagicMock,
    mock_map_to_doe_response: mock.MagicMock,
    mock_map_to_price_response: mock.MagicMock,
):
    """Checks that the flows for a response work OK with DOEs when they are missing"""
    # Arrange
    scope = generate_class_instance(DeviceOrAggregatorRequestScope)
    mock_session = create_mock_session()
    response_id = 65314141

    mock_select_doe_response_for_scope.return_value = None

    # Act
    with pytest.raises(NotFoundError):
        await ResponseManager.fetch_response_for_scope(
            mock_session, scope, ResponseSetType.DYNAMIC_OPERATING_ENVELOPES, response_id
        )

    # Assert
    assert_mock_session(mock_session)
    mock_select_rate_response_for_scope.assert_not_called()
    mock_map_to_price_response.assert_not_called()
    mock_select_doe_response_for_scope.assert_called_once_with(
        mock_session, scope.aggregator_id, scope.site_id, response_id
    )
    mock_map_to_doe_response.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.server.manager.response.ResponseMapper.map_to_price_response")
@mock.patch("envoy.server.manager.response.ResponseMapper.map_to_doe_response")
@mock.patch("envoy.server.manager.response.select_doe_response_for_scope")
@mock.patch("envoy.server.manager.response.select_rate_response_for_scope")
async def test_fetch_response_for_scope_rate_exists(
    mock_select_rate_response_for_scope: mock.MagicMock,
    mock_select_doe_response_for_scope: mock.MagicMock,
    mock_map_to_doe_response: mock.MagicMock,
    mock_map_to_price_response: mock.MagicMock,
):
    """Checks that the flows for a response work OK with tariff generated rates"""
    # Arrange
    scope = generate_class_instance(DeviceOrAggregatorRequestScope)
    response_obj = generate_class_instance(TariffGeneratedRateResponse)
    mapped_obj = generate_class_instance(Response)
    mock_session = create_mock_session()
    response_id = 65314141

    mock_select_rate_response_for_scope.return_value = response_obj
    mock_map_to_price_response.return_value = mapped_obj

    # Act
    result = await ResponseManager.fetch_response_for_scope(
        mock_session, scope, ResponseSetType.TARIFF_GENERATED_RATES, response_id
    )

    # Assert
    assert result is mapped_obj
    assert_mock_session(mock_session)
    mock_select_rate_response_for_scope.assert_called_once_with(
        mock_session, scope.aggregator_id, scope.site_id, response_id
    )
    mock_map_to_price_response.assert_called_once_with(scope, response_obj)
    mock_select_doe_response_for_scope.assert_not_called()
    mock_map_to_doe_response.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.server.manager.response.ResponseMapper.map_to_price_response")
@mock.patch("envoy.server.manager.response.ResponseMapper.map_to_doe_response")
@mock.patch("envoy.server.manager.response.select_doe_response_for_scope")
@mock.patch("envoy.server.manager.response.select_rate_response_for_scope")
async def test_fetch_response_for_scope_rate_missing(
    mock_select_rate_response_for_scope: mock.MagicMock,
    mock_select_doe_response_for_scope: mock.MagicMock,
    mock_map_to_doe_response: mock.MagicMock,
    mock_map_to_price_response: mock.MagicMock,
):
    """Checks that the flows for a response work OK with tariff generated rates when they are missing"""
    # Arrange
    scope = generate_class_instance(DeviceOrAggregatorRequestScope)
    mock_session = create_mock_session()
    response_id = 65314141

    mock_select_rate_response_for_scope.return_value = None

    # Act
    with pytest.raises(NotFoundError):
        await ResponseManager.fetch_response_for_scope(
            mock_session, scope, ResponseSetType.TARIFF_GENERATED_RATES, response_id
        )

    # Assert
    assert_mock_session(mock_session)
    mock_select_rate_response_for_scope.assert_called_once_with(
        mock_session, scope.aggregator_id, scope.site_id, response_id
    )
    mock_map_to_price_response.assert_not_called()
    mock_select_doe_response_for_scope.assert_not_called()
    mock_map_to_doe_response.assert_not_called()


@pytest.mark.anyio
async def test_fetch_response_for_scope_bad_type():
    """Passing an unrecognised RequestSetType raises NotFoundError"""
    scope = generate_class_instance(DeviceOrAggregatorRequestScope)
    mock_session = create_mock_session()
    response_id = 65314141

    with pytest.raises(NotFoundError):
        await ResponseManager.fetch_response_for_scope(mock_session, scope, -1, response_id)

    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.response.ResponseListMapper.map_to_price_response")
@mock.patch("envoy.server.manager.response.ResponseListMapper.map_to_doe_response")
@mock.patch("envoy.server.manager.response.select_doe_responses")
@mock.patch("envoy.server.manager.response.count_doe_responses")
@mock.patch("envoy.server.manager.response.select_tariff_generated_rate_responses")
@mock.patch("envoy.server.manager.response.count_tariff_generated_rate_responses")
async def test_fetch_response_list_for_scope_does(
    mock_count_tariff_generated_rate_responses: mock.MagicMock,
    mock_select_tariff_generated_rate_responses: mock.MagicMock,
    mock_count_doe_responses: mock.MagicMock,
    mock_select_doe_responses: mock.MagicMock,
    mock_map_to_doe_response: mock.MagicMock,
    mock_map_to_price_response: mock.MagicMock,
):
    """Checks that the flows for a response list work OK with DOEs"""
    # Arrange
    scope = generate_class_instance(DeviceOrAggregatorRequestScope)
    response_objs = [generate_class_instance(DynamicOperatingEnvelopeResponse)]
    mapped_obj = generate_class_instance(ResponseListResponse)
    mock_session = create_mock_session()
    start = 101
    limit = 202
    created_after = datetime(2022, 11, 1)
    mock_count = 67571

    mock_count_doe_responses.return_value = mock_count
    mock_select_doe_responses.return_value = response_objs
    mock_map_to_doe_response.return_value = mapped_obj

    # Act
    result = await ResponseManager.fetch_response_list_for_scope(
        mock_session, scope, ResponseSetType.DYNAMIC_OPERATING_ENVELOPES, start, limit, created_after
    )

    # Assert
    assert result is mapped_obj
    assert_mock_session(mock_session)
    mock_select_tariff_generated_rate_responses.assert_not_called()
    mock_count_tariff_generated_rate_responses.assert_not_called()
    mock_map_to_price_response.assert_not_called()
    mock_select_doe_responses.assert_called_once_with(
        mock_session,
        aggregator_id=scope.aggregator_id,
        site_id=scope.site_id,
        start=start,
        limit=limit,
        created_after=created_after,
    )
    mock_count_doe_responses.assert_called_once_with(mock_session, scope.aggregator_id, scope.site_id, created_after)
    mock_map_to_doe_response.assert_called_once_with(scope, response_objs, mock_count)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.response.ResponseListMapper.map_to_price_response")
@mock.patch("envoy.server.manager.response.ResponseListMapper.map_to_doe_response")
@mock.patch("envoy.server.manager.response.select_doe_responses")
@mock.patch("envoy.server.manager.response.count_doe_responses")
@mock.patch("envoy.server.manager.response.select_tariff_generated_rate_responses")
@mock.patch("envoy.server.manager.response.count_tariff_generated_rate_responses")
async def test_fetch_response_list_for_scope_rates(
    mock_count_tariff_generated_rate_responses: mock.MagicMock,
    mock_select_tariff_generated_rate_responses: mock.MagicMock,
    mock_count_doe_responses: mock.MagicMock,
    mock_select_doe_responses: mock.MagicMock,
    mock_map_to_doe_response: mock.MagicMock,
    mock_map_to_price_response: mock.MagicMock,
):
    """Checks that the flows for a response list work OK with tariff generated rates"""
    # Arrange
    scope = generate_class_instance(DeviceOrAggregatorRequestScope)
    response_objs = [generate_class_instance(TariffGeneratedRateResponse)]
    mapped_obj = generate_class_instance(ResponseListResponse)
    mock_session = create_mock_session()
    start = 101
    limit = 202
    created_after = datetime(2022, 11, 1)
    mock_count = 67571

    mock_count_tariff_generated_rate_responses.return_value = mock_count
    mock_select_tariff_generated_rate_responses.return_value = response_objs
    mock_map_to_price_response.return_value = mapped_obj

    # Act
    result = await ResponseManager.fetch_response_list_for_scope(
        mock_session, scope, ResponseSetType.TARIFF_GENERATED_RATES, start, limit, created_after
    )

    # Assert
    assert result is mapped_obj
    assert_mock_session(mock_session)
    mock_select_tariff_generated_rate_responses.assert_called_once_with(
        mock_session,
        aggregator_id=scope.aggregator_id,
        site_id=scope.site_id,
        start=start,
        limit=limit,
        created_after=created_after,
    )
    mock_count_tariff_generated_rate_responses.assert_called_once_with(
        mock_session, scope.aggregator_id, scope.site_id, created_after
    )
    mock_map_to_price_response.assert_called_once_with(scope, response_objs, mock_count)
    mock_select_doe_responses.assert_not_called()
    mock_count_doe_responses.assert_not_called()
    mock_map_to_doe_response.assert_not_called()


@pytest.mark.anyio
async def test_fetch_response_list_for_scope_bad_type():
    """Checks that an unknown ResponseSetType raises NotFoundError"""
    scope = generate_class_instance(DeviceOrAggregatorRequestScope)
    mock_session = create_mock_session()
    start = 101
    limit = 202
    created_after = datetime(2022, 11, 1)

    with pytest.raises(NotFoundError):
        await ResponseManager.fetch_response_list_for_scope(mock_session, scope, -1, start, limit, created_after)
