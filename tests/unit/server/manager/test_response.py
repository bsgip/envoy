import unittest.mock as mock
from datetime import datetime

import pytest
from assertical.asserts.time import assert_nowish
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from assertical.fake.sqlalchemy import assert_mock_session, create_mock_session
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.response import Response, ResponseListResponse, ResponseSet, ResponseSetList
from sqlalchemy import func, select

from envoy.server.exception import BadRequestError, NotFoundError
from envoy.server.manager.response import ResponseManager
from envoy.server.mapper.constants import MridType, PricingReadingType, ResponseSetType
from envoy.server.mapper.sep2.mrid import MridMapper
from envoy.server.mapper.sep2.response import response_set_type_to_href
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.response import DynamicOperatingEnvelopeResponse, TariffGeneratedRateResponse
from envoy.server.model.tariff import TariffGeneratedRate
from envoy.server.request_scope import DeviceOrAggregatorRequestScope, SiteRequestScope


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


@mock.patch("envoy.server.manager.response.ResponseMapper.map_to_price_response")
@mock.patch("envoy.server.manager.response.ResponseMapper.map_to_doe_response")
@mock.patch("envoy.server.manager.response.select_doe_response_for_scope")
@mock.patch("envoy.server.manager.response.select_rate_response_for_scope")
@pytest.mark.anyio
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


@mock.patch("envoy.server.manager.response.ResponseMapper.map_to_price_response")
@mock.patch("envoy.server.manager.response.ResponseMapper.map_to_doe_response")
@mock.patch("envoy.server.manager.response.select_doe_response_for_scope")
@mock.patch("envoy.server.manager.response.select_rate_response_for_scope")
@pytest.mark.anyio
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


@mock.patch("envoy.server.manager.response.ResponseMapper.map_to_price_response")
@mock.patch("envoy.server.manager.response.ResponseMapper.map_to_doe_response")
@mock.patch("envoy.server.manager.response.select_doe_response_for_scope")
@mock.patch("envoy.server.manager.response.select_rate_response_for_scope")
@pytest.mark.anyio
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


@mock.patch("envoy.server.manager.response.ResponseMapper.map_to_price_response")
@mock.patch("envoy.server.manager.response.ResponseMapper.map_to_doe_response")
@mock.patch("envoy.server.manager.response.select_doe_response_for_scope")
@mock.patch("envoy.server.manager.response.select_rate_response_for_scope")
@pytest.mark.anyio
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


@mock.patch("envoy.server.manager.response.ResponseListMapper.map_to_price_response")
@mock.patch("envoy.server.manager.response.ResponseListMapper.map_to_doe_response")
@mock.patch("envoy.server.manager.response.select_doe_responses")
@mock.patch("envoy.server.manager.response.count_doe_responses")
@mock.patch("envoy.server.manager.response.select_tariff_generated_rate_responses")
@mock.patch("envoy.server.manager.response.count_tariff_generated_rate_responses")
@pytest.mark.anyio
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


@mock.patch("envoy.server.manager.response.ResponseListMapper.map_to_price_response")
@mock.patch("envoy.server.manager.response.ResponseListMapper.map_to_doe_response")
@mock.patch("envoy.server.manager.response.select_doe_responses")
@mock.patch("envoy.server.manager.response.count_doe_responses")
@mock.patch("envoy.server.manager.response.select_tariff_generated_rate_responses")
@mock.patch("envoy.server.manager.response.count_tariff_generated_rate_responses")
@pytest.mark.anyio
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


@mock.patch("envoy.server.manager.response.MridMapper.decode_and_validate_mrid_type")
@mock.patch("envoy.server.manager.response.MridMapper.decode_doe_mrid")
@mock.patch("envoy.server.manager.response.MridMapper.decode_time_tariff_interval_mrid")
@mock.patch("envoy.server.manager.response.select_doe_include_deleted")
@mock.patch("envoy.server.manager.response.select_tariff_generated_rate_for_scope")
@pytest.mark.anyio
async def test_create_response_for_scope_invalid_mrid(
    mock_select_tariff_generated_rate_for_scope: mock.MagicMock,
    mock_select_doe_include_deleted: mock.MagicMock,
    mock_decode_time_tariff_interval_mrid: mock.MagicMock,
    mock_decode_doe_mrid: mock.MagicMock,
    mock_decode_and_validate_mrid_type: mock.MagicMock,
):
    """Tests that if decode_and_validate_mrid_type raises an error - a bad request is raised"""
    # Arrange
    session = create_mock_session()
    scope = generate_class_instance(SiteRequestScope, seed=101)
    response = generate_class_instance(Response, seed=202)
    mock_decode_and_validate_mrid_type.return_value = ValueError("mock")

    # Act
    with pytest.raises(BadRequestError):
        await ResponseManager.create_response_for_scope(
            session, scope, ResponseSetType.DYNAMIC_OPERATING_ENVELOPES, response
        )

    # Assert
    assert_mock_session(session, committed=False)
    mock_decode_and_validate_mrid_type.assert_called_once_with(scope, response.subject)
    mock_select_tariff_generated_rate_for_scope.assert_not_called()
    mock_select_doe_include_deleted.assert_not_called()
    mock_decode_time_tariff_interval_mrid.assert_not_called()
    mock_decode_doe_mrid.assert_not_called()


@mock.patch("envoy.server.manager.response.MridMapper.decode_and_validate_mrid_type")
@mock.patch("envoy.server.manager.response.MridMapper.decode_doe_mrid")
@mock.patch("envoy.server.manager.response.MridMapper.decode_time_tariff_interval_mrid")
@mock.patch("envoy.server.manager.response.select_doe_include_deleted")
@mock.patch("envoy.server.manager.response.select_tariff_generated_rate_for_scope")
@pytest.mark.anyio
async def test_create_response_for_scope_invalid_response_set_type(
    mock_select_tariff_generated_rate_for_scope: mock.MagicMock,
    mock_select_doe_include_deleted: mock.MagicMock,
    mock_decode_time_tariff_interval_mrid: mock.MagicMock,
    mock_decode_doe_mrid: mock.MagicMock,
    mock_decode_and_validate_mrid_type: mock.MagicMock,
):
    """Tests that if the response_set_type is unknown a bad request is raised"""
    # Arrange
    session = create_mock_session()
    scope = generate_class_instance(SiteRequestScope, seed=101)
    response = generate_class_instance(Response, seed=202)
    mock_decode_and_validate_mrid_type.return_value = MridType.DYNAMIC_OPERATING_ENVELOPE

    # Act
    with pytest.raises(BadRequestError):
        await ResponseManager.create_response_for_scope(session, scope, -1, response)

    # Assert
    assert_mock_session(session, committed=False)
    mock_decode_and_validate_mrid_type.assert_called_once_with(scope, response.subject)
    mock_select_tariff_generated_rate_for_scope.assert_not_called()
    mock_select_doe_include_deleted.assert_not_called()
    mock_decode_time_tariff_interval_mrid.assert_not_called()
    mock_decode_doe_mrid.assert_not_called()


@mock.patch("envoy.server.manager.response.MridMapper.decode_and_validate_mrid_type")
@mock.patch("envoy.server.manager.response.MridMapper.decode_doe_mrid")
@mock.patch("envoy.server.manager.response.MridMapper.decode_time_tariff_interval_mrid")
@mock.patch("envoy.server.manager.response.select_doe_include_deleted")
@mock.patch("envoy.server.manager.response.select_tariff_generated_rate_for_scope")
@pytest.mark.anyio
async def test_create_response_for_scope_doe_with_price_mrid(
    mock_select_tariff_generated_rate_for_scope: mock.MagicMock,
    mock_select_doe_include_deleted: mock.MagicMock,
    mock_decode_time_tariff_interval_mrid: mock.MagicMock,
    mock_decode_doe_mrid: mock.MagicMock,
    mock_decode_and_validate_mrid_type: mock.MagicMock,
):
    """Tests that if a price response is sent to the DOE list - we get raise a bad request error"""
    # Arrange
    session = create_mock_session()
    scope = generate_class_instance(SiteRequestScope, seed=101)
    response = generate_class_instance(Response, seed=202)
    mock_decode_and_validate_mrid_type.return_value = MridType.TIME_TARIFF_INTERVAL

    # Act
    with pytest.raises(BadRequestError):
        await ResponseManager.create_response_for_scope(
            session, scope, ResponseSetType.DYNAMIC_OPERATING_ENVELOPES, response
        )

    # Assert
    assert_mock_session(session, committed=False)
    mock_decode_and_validate_mrid_type.assert_called_once_with(scope, response.subject)
    mock_select_tariff_generated_rate_for_scope.assert_not_called()
    mock_select_doe_include_deleted.assert_not_called()
    mock_decode_time_tariff_interval_mrid.assert_not_called()
    mock_decode_doe_mrid.assert_not_called()


@mock.patch("envoy.server.manager.response.MridMapper.decode_and_validate_mrid_type")
@mock.patch("envoy.server.manager.response.MridMapper.decode_doe_mrid")
@mock.patch("envoy.server.manager.response.MridMapper.decode_time_tariff_interval_mrid")
@mock.patch("envoy.server.manager.response.select_doe_include_deleted")
@mock.patch("envoy.server.manager.response.select_tariff_generated_rate_for_scope")
@pytest.mark.anyio
async def test_create_response_for_scope_doe_not_in_scope(
    mock_select_tariff_generated_rate_for_scope: mock.MagicMock,
    mock_select_doe_include_deleted: mock.MagicMock,
    mock_decode_time_tariff_interval_mrid: mock.MagicMock,
    mock_decode_doe_mrid: mock.MagicMock,
    mock_decode_and_validate_mrid_type: mock.MagicMock,
):
    """Tests that if a doe response references a doe not in scope - we get raise a bad request error"""
    # Arrange

    session = create_mock_session()
    scope = generate_class_instance(SiteRequestScope, seed=101)
    response = generate_class_instance(Response, seed=202)
    decoded_doe_id = 303
    mock_decode_and_validate_mrid_type.return_value = MridType.DYNAMIC_OPERATING_ENVELOPE
    mock_decode_doe_mrid.return_value = decoded_doe_id
    mock_select_doe_include_deleted.return_value = None

    # Act
    with pytest.raises(BadRequestError):
        await ResponseManager.create_response_for_scope(
            session, scope, ResponseSetType.DYNAMIC_OPERATING_ENVELOPES, response
        )

    # Assert
    mock_decode_and_validate_mrid_type.assert_called_once_with(scope, response.subject)
    mock_select_tariff_generated_rate_for_scope.assert_not_called()
    mock_select_doe_include_deleted.assert_called_once_with(session, scope.aggregator_id, scope.site_id, decoded_doe_id)
    mock_decode_time_tariff_interval_mrid.assert_not_called()
    mock_decode_doe_mrid.assert_called_once_with(response.subject)


@mock.patch("envoy.server.manager.response.MridMapper.decode_and_validate_mrid_type")
@mock.patch("envoy.server.manager.response.MridMapper.decode_doe_mrid")
@mock.patch("envoy.server.manager.response.MridMapper.decode_time_tariff_interval_mrid")
@mock.patch("envoy.server.manager.response.select_doe_include_deleted")
@mock.patch("envoy.server.manager.response.select_tariff_generated_rate_for_scope")
@pytest.mark.anyio
async def test_create_response_for_scope_doe_created_normally(
    mock_select_tariff_generated_rate_for_scope: mock.MagicMock,
    mock_select_doe_include_deleted: mock.MagicMock,
    mock_decode_time_tariff_interval_mrid: mock.MagicMock,
    mock_decode_doe_mrid: mock.MagicMock,
    mock_decode_and_validate_mrid_type: mock.MagicMock,
    pg_base_config,
):
    """Tests that DOE responses can be added to the database and the appropriate href returned"""

    # Arrange
    site_id = 1
    scope = generate_class_instance(SiteRequestScope, seed=101, site_id=None, href_prefix="/my_prefix/")
    response = generate_class_instance(Response, seed=202)
    decoded_doe_id = 2
    existing_doe = generate_class_instance(
        DynamicOperatingEnvelope, seed=303, dynamic_operating_envelope_id=decoded_doe_id, site_id=site_id
    )
    mock_decode_and_validate_mrid_type.return_value = MridType.DYNAMIC_OPERATING_ENVELOPE
    mock_decode_doe_mrid.return_value = decoded_doe_id
    mock_select_doe_include_deleted.return_value = existing_doe

    # Act
    async with generate_async_session(pg_base_config) as session:
        db_count_before = (
            await session.execute(select(func.count()).select_from(DynamicOperatingEnvelopeResponse))
        ).scalar_one()

    async with generate_async_session(pg_base_config) as session:
        returned_href = await ResponseManager.create_response_for_scope(
            session, scope, ResponseSetType.DYNAMIC_OPERATING_ENVELOPES, response
        )

    # Assert
    mock_decode_and_validate_mrid_type.assert_called_once_with(scope, response.subject)
    mock_select_tariff_generated_rate_for_scope.assert_not_called()
    mock_select_doe_include_deleted.assert_called_once_with(session, scope.aggregator_id, scope.site_id, decoded_doe_id)
    mock_decode_time_tariff_interval_mrid.assert_not_called()
    mock_decode_doe_mrid.assert_called_once_with(response.subject)

    # Check the href looks valid and matches the new record in the DB
    assert isinstance(returned_href, str)
    assert returned_href.startswith(scope.href_prefix)
    response_id = int(returned_href.split("/")[-1])  # Assume LAST component of href is the DB ID
    assert response_set_type_to_href(ResponseSetType.DYNAMIC_OPERATING_ENVELOPES) in returned_href
    async with generate_async_session(pg_base_config) as session:
        db_count_after = (
            await session.execute(select(func.count()).select_from(DynamicOperatingEnvelopeResponse))
        ).scalar_one()
        db_response = (
            await session.execute(
                select(DynamicOperatingEnvelopeResponse).where(
                    DynamicOperatingEnvelopeResponse.dynamic_operating_envelope_response_id == response_id
                )
            )
        ).scalar_one()

        assert db_count_after == (db_count_before + 1), "There should be a new response in the DB"
        assert db_response.site_id == site_id, "This is double checking the mapper"
        assert db_response.dynamic_operating_envelope_id == decoded_doe_id, "This is double checking the mapper"
        assert_nowish(db_response.created_time)
        assert db_response.response_type == response.status, "This is double checking the mapper"


@mock.patch("envoy.server.manager.response.MridMapper.decode_and_validate_mrid_type")
@mock.patch("envoy.server.manager.response.MridMapper.decode_doe_mrid")
@mock.patch("envoy.server.manager.response.MridMapper.decode_time_tariff_interval_mrid")
@mock.patch("envoy.server.manager.response.select_doe_include_deleted")
@mock.patch("envoy.server.manager.response.select_tariff_generated_rate_for_scope")
@pytest.mark.anyio
async def test_create_response_for_scope_price_with_doe_mrid(
    mock_select_tariff_generated_rate_for_scope: mock.MagicMock,
    mock_select_doe_include_deleted: mock.MagicMock,
    mock_decode_time_tariff_interval_mrid: mock.MagicMock,
    mock_decode_doe_mrid: mock.MagicMock,
    mock_decode_and_validate_mrid_type: mock.MagicMock,
):
    """Tests that if a doe response is sent to the price list - we get raise a bad request error"""
    # Arrange
    session = create_mock_session()
    scope = generate_class_instance(SiteRequestScope, seed=101)
    response = generate_class_instance(Response, seed=202)
    mock_decode_and_validate_mrid_type.return_value = MridType.DYNAMIC_OPERATING_ENVELOPE

    # Act
    with pytest.raises(BadRequestError):
        await ResponseManager.create_response_for_scope(
            session, scope, ResponseSetType.TARIFF_GENERATED_RATES, response
        )

    # Assert
    assert_mock_session(session, committed=False)
    mock_decode_and_validate_mrid_type.assert_called_once_with(scope, response.subject)
    mock_select_tariff_generated_rate_for_scope.assert_not_called()
    mock_select_doe_include_deleted.assert_not_called()
    mock_decode_time_tariff_interval_mrid.assert_not_called()
    mock_decode_doe_mrid.assert_not_called()


@mock.patch("envoy.server.manager.response.MridMapper.decode_and_validate_mrid_type")
@mock.patch("envoy.server.manager.response.MridMapper.decode_doe_mrid")
@mock.patch("envoy.server.manager.response.MridMapper.decode_time_tariff_interval_mrid")
@mock.patch("envoy.server.manager.response.select_doe_include_deleted")
@mock.patch("envoy.server.manager.response.select_tariff_generated_rate_for_scope")
@pytest.mark.anyio
async def test_create_response_for_scope_price_not_in_scope(
    mock_select_tariff_generated_rate_for_scope: mock.MagicMock,
    mock_select_doe_include_deleted: mock.MagicMock,
    mock_decode_time_tariff_interval_mrid: mock.MagicMock,
    mock_decode_doe_mrid: mock.MagicMock,
    mock_decode_and_validate_mrid_type: mock.MagicMock,
):
    """Tests that if a price response references a price not in scope - we get raise a bad request error"""
    # Arrange

    session = create_mock_session()
    scope = generate_class_instance(SiteRequestScope, seed=101)
    response = generate_class_instance(Response, seed=202)
    decoded_rate_id = 303
    pricing_reading_type = PricingReadingType.EXPORT_REACTIVE_POWER_KVARH
    mock_decode_and_validate_mrid_type.return_value = MridType.TIME_TARIFF_INTERVAL
    mock_decode_time_tariff_interval_mrid.return_value = (pricing_reading_type, decoded_rate_id)
    mock_select_tariff_generated_rate_for_scope.return_value = None

    # Act
    with pytest.raises(BadRequestError):
        await ResponseManager.create_response_for_scope(
            session, scope, ResponseSetType.TARIFF_GENERATED_RATES, response
        )

    # Assert
    mock_decode_and_validate_mrid_type.assert_called_once_with(scope, response.subject)
    mock_select_tariff_generated_rate_for_scope.assert_called_once_with(
        session, scope.aggregator_id, scope.site_id, decoded_rate_id
    )
    mock_select_doe_include_deleted.assert_not_called()
    mock_decode_time_tariff_interval_mrid.assert_called_once_with(response.subject)
    mock_decode_doe_mrid.assert_not_called()


@mock.patch("envoy.server.manager.response.MridMapper.decode_and_validate_mrid_type")
@mock.patch("envoy.server.manager.response.MridMapper.decode_doe_mrid")
@mock.patch("envoy.server.manager.response.MridMapper.decode_time_tariff_interval_mrid")
@mock.patch("envoy.server.manager.response.select_doe_include_deleted")
@mock.patch("envoy.server.manager.response.select_tariff_generated_rate_for_scope")
@pytest.mark.anyio
async def test_create_response_for_scope_price_created_normally(
    mock_select_tariff_generated_rate_for_scope: mock.MagicMock,
    mock_select_doe_include_deleted: mock.MagicMock,
    mock_decode_time_tariff_interval_mrid: mock.MagicMock,
    mock_decode_doe_mrid: mock.MagicMock,
    mock_decode_and_validate_mrid_type: mock.MagicMock,
    pg_base_config,
):
    """Tests that rate responses can be added to the database and the appropriate href returned"""

    # Arrange
    site_id = 1
    scope = generate_class_instance(SiteRequestScope, seed=101, site_id=site_id, href_prefix="/my_prefix/")
    response = generate_class_instance(Response, seed=202)
    decoded_rate_id = 2
    existing_rate = generate_class_instance(
        TariffGeneratedRate, seed=303, tariff_generated_rate_id=decoded_rate_id, site_id=site_id
    )
    pricing_reading_type = PricingReadingType.EXPORT_REACTIVE_POWER_KVARH
    mock_decode_and_validate_mrid_type.return_value = MridType.TIME_TARIFF_INTERVAL
    mock_decode_time_tariff_interval_mrid.return_value = (pricing_reading_type, decoded_rate_id)
    mock_select_tariff_generated_rate_for_scope.return_value = existing_rate

    # Act
    async with generate_async_session(pg_base_config) as session:
        db_count_before = (
            await session.execute(select(func.count()).select_from(TariffGeneratedRateResponse))
        ).scalar_one()

    async with generate_async_session(pg_base_config) as session:
        returned_href = await ResponseManager.create_response_for_scope(
            session, scope, ResponseSetType.TARIFF_GENERATED_RATES, response
        )

    # Assert
    mock_decode_and_validate_mrid_type.assert_called_once_with(scope, response.subject)
    mock_select_tariff_generated_rate_for_scope.assert_called_once_with(
        session, scope.aggregator_id, scope.site_id, decoded_rate_id
    )
    mock_select_doe_include_deleted.assert_not_called()
    mock_decode_time_tariff_interval_mrid.assert_called_once_with(response.subject)
    mock_decode_doe_mrid.assert_not_called()

    # Check the href looks valid and matches the new record in the DB
    assert isinstance(returned_href, str)
    assert returned_href.startswith(scope.href_prefix)
    response_id = int(returned_href.split("/")[-1])  # Assume LAST component of href is the DB ID
    assert response_set_type_to_href(ResponseSetType.TARIFF_GENERATED_RATES) in returned_href
    async with generate_async_session(pg_base_config) as session:
        db_count_after = (
            await session.execute(select(func.count()).select_from(TariffGeneratedRateResponse))
        ).scalar_one()
        db_response = (
            await session.execute(
                select(TariffGeneratedRateResponse).where(
                    TariffGeneratedRateResponse.tariff_generated_rate_response_id == response_id
                )
            )
        ).scalar_one()

        assert db_count_after == (db_count_before + 1), "There should be a new response in the DB"
        assert db_response.site_id == site_id, "This is double checking the mapper"
        assert db_response.tariff_generated_rate_id == decoded_rate_id, "This is double checking the mapper"
        assert_nowish(db_response.created_time)
        assert db_response.response_type == response.status, "This is double checking the mapper"
