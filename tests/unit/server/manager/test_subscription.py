import unittest.mock as mock
from datetime import datetime
from typing import Optional

import pytest
from envoy_schema.server.schema.sep2.pub_sub import Subscription as Sep2Subscription
from envoy_schema.server.schema.sep2.pub_sub import SubscriptionListResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.exception import BadRequestError, NotFoundError
from envoy.server.manager.subscription import SubscriptionManager
from envoy.server.model.aggregator import Aggregator, AggregatorDomain
from envoy.server.model.site_reading import SiteReadingType
from envoy.server.model.subscription import Subscription, SubscriptionResource
from envoy.server.model.tariff import Tariff
from envoy.server.request_state import RequestStateParameters
from tests.data.fake.generator import generate_class_instance
from tests.unit.mocks import assert_mock_session, create_mock_session


@pytest.mark.anyio
@pytest.mark.parametrize(
    "site_id_filter, scoped_site_id, expect_none",
    [(1, 2, True), (1, 1, False), (1, None, True), (None, 2, False), (None, None, False)],
)
@mock.patch("envoy.server.manager.subscription.select_subscription_by_id")
@mock.patch("envoy.server.manager.subscription.SubscriptionMapper")
async def test_fetch_subscription_by_id_filtering(
    mock_SubscriptionMapper: mock.MagicMock,
    mock_select_subscription_by_id: mock.MagicMock,
    site_id_filter: Optional[int],
    scoped_site_id: Optional[int],
    expect_none: bool,
):
    """Quick tests on the various ways filter options can affect the returned subscriptions. It attempts
    to enumerate all the various ways None can be returned (despite getting a sub returned from the DB)"""
    # Arrange
    mock_session: AsyncSession = create_mock_session()
    rs_params = RequestStateParameters(981, None)
    sub_id = 87

    mock_sub: Subscription = generate_class_instance(Subscription)
    mock_sub.scoped_site_id = scoped_site_id
    mock_result: Sep2Subscription = generate_class_instance(Sep2Subscription)
    mock_select_subscription_by_id.return_value = mock_sub
    mock_SubscriptionMapper.map_to_response = mock.Mock(return_value=mock_result)

    # Act
    actual_result = await SubscriptionManager.fetch_subscription_by_id(mock_session, rs_params, sub_id, site_id_filter)

    # Assert
    if expect_none:
        assert actual_result is None
    else:
        assert actual_result is mock_result
        mock_SubscriptionMapper.map_to_response.assert_called_once_with(mock_sub, rs_params)

    mock_select_subscription_by_id.assert_called_once_with(
        mock_session, aggregator_id=rs_params.aggregator_id, subscription_id=sub_id
    )
    assert_mock_session(mock_session, committed=False)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.subscription.select_subscription_by_id")
async def test_fetch_subscription_by_id_not_found(
    mock_select_subscription_by_id: mock.MagicMock,
):
    """Quick tests on the various ways filter options can affect the returned subscriptions"""
    # Arrange
    mock_session: AsyncSession = create_mock_session()
    rs_params = RequestStateParameters(981, None)
    sub_id = 87
    mock_select_subscription_by_id.return_value = None

    # Act
    actual_result = await SubscriptionManager.fetch_subscription_by_id(mock_session, rs_params, sub_id, None)

    # Assert
    assert actual_result is None
    mock_select_subscription_by_id.assert_called_once_with(
        mock_session, aggregator_id=rs_params.aggregator_id, subscription_id=sub_id
    )
    assert_mock_session(mock_session, committed=False)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.subscription.select_subscriptions_for_site")
@mock.patch("envoy.server.manager.subscription.count_subscriptions_for_site")
@mock.patch("envoy.server.manager.subscription.SubscriptionListMapper")
async def test_fetch_subscriptions_for_site(
    mock_SubscriptionListMapper: mock.MagicMock,
    mock_count_subscriptions_for_site: mock.MagicMock,
    mock_select_subscriptions_for_site: mock.MagicMock,
):
    """Quick tests on the various ways filter options can affect the returned subscriptions"""
    # Arrange
    mock_session: AsyncSession = create_mock_session()
    rs_params = RequestStateParameters(981, None)
    mock_sub_count = 123
    mock_sub_list = [
        generate_class_instance(Subscription, seed=1, optional_is_none=False),
        generate_class_instance(Subscription, seed=2, optional_is_none=True),
    ]
    site_id = 456
    start = 789
    limit = 101112
    after = datetime(2022, 3, 4, 1, 2, 3)
    mock_result = generate_class_instance(SubscriptionListResponse)

    mock_count_subscriptions_for_site.return_value = mock_sub_count
    mock_select_subscriptions_for_site.return_value = mock_sub_list
    mock_SubscriptionListMapper.map_to_site_response = mock.Mock(return_value=mock_result)

    # Act
    actual_result = await SubscriptionManager.fetch_subscriptions_for_site(
        mock_session, rs_params, site_id, start, after, limit
    )

    # Assert
    assert actual_result is mock_result

    mock_SubscriptionListMapper.map_to_site_response.assert_called_once_with(
        rs_params=rs_params, site_id=site_id, sub_list=mock_sub_list, sub_count=mock_sub_count
    )

    mock_count_subscriptions_for_site.assert_called_once_with(
        mock_session,
        aggregator_id=rs_params.aggregator_id,
        site_id=site_id,
        changed_after=after,
    )
    mock_select_subscriptions_for_site.assert_called_once_with(
        mock_session,
        aggregator_id=rs_params.aggregator_id,
        site_id=site_id,
        start=start,
        changed_after=after,
        limit=limit,
    )
    assert_mock_session(mock_session, committed=False)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "retval",
    [(True), (False)],
)
@mock.patch("envoy.server.manager.subscription.delete_subscription_for_site")
async def test_delete_subscription_for_site(mock_delete_subscription_for_site: mock.MagicMock, retval: bool):
    """Ensures session is handled properly on delete"""
    # Arrange
    mock_session: AsyncSession = create_mock_session()
    rs_params = RequestStateParameters(981, None)

    site_id = 456
    sub_id = 5213

    mock_delete_subscription_for_site.return_value = retval

    # Act
    actual_result = await SubscriptionManager.delete_subscription_for_site(mock_session, rs_params, site_id, sub_id)

    # Assert
    assert actual_result == retval

    mock_delete_subscription_for_site.assert_called_once_with(
        mock_session, aggregator_id=rs_params.aggregator_id, site_id=site_id, subscription_id=sub_id
    )

    assert_mock_session(mock_session, committed=True)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.subscription.utc_now")
@mock.patch("envoy.server.manager.subscription.select_aggregator")
@mock.patch("envoy.server.manager.subscription.SubscriptionMapper")
@mock.patch("envoy.server.manager.subscription.fetch_site_reading_type_for_aggregator")
@mock.patch("envoy.server.manager.subscription.select_single_tariff")
@mock.patch("envoy.server.manager.subscription.insert_subscription")
async def test_add_subscription_for_site_bad_agg_lookup(
    mock_insert_subscription: mock.MagicMock,
    mock_select_single_tariff: mock.MagicMock,
    mock_fetch_site_reading_type_for_aggregator: mock.MagicMock,
    mock_SubscriptionMapper: mock.MagicMock,
    mock_select_aggregator: mock.MagicMock,
    mock_utc_now: mock.MagicMock,
):
    mock_session: AsyncSession = create_mock_session()
    rs_params = RequestStateParameters(981, None)
    now = datetime(2014, 4, 5, 6, 7, 8)
    site_id = 456
    sub = generate_class_instance(Sep2Subscription)

    mock_utc_now.return_value = now
    mock_select_aggregator.return_value = None
    mock_insert_subscription.return_value = 98765

    # Act
    with pytest.raises(NotFoundError):
        await SubscriptionManager.add_subscription_for_site(mock_session, rs_params, sub, site_id)

    assert_mock_session(mock_session, committed=False)
    mock_utc_now.assert_called_once()
    mock_select_aggregator.assert_called_once_with(mock_session, rs_params.aggregator_id)
    mock_SubscriptionMapper.map_from_request.assert_not_called()
    mock_select_single_tariff.assert_not_called()
    mock_fetch_site_reading_type_for_aggregator.assert_not_called()
    mock_insert_subscription.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.server.manager.subscription.utc_now")
@mock.patch("envoy.server.manager.subscription.select_aggregator")
@mock.patch("envoy.server.manager.subscription.SubscriptionMapper")
@mock.patch("envoy.server.manager.subscription.fetch_site_reading_type_for_aggregator")
@mock.patch("envoy.server.manager.subscription.select_single_tariff")
@mock.patch("envoy.server.manager.subscription.insert_subscription")
async def test_add_subscription_for_site_bad_site_id(
    mock_insert_subscription: mock.MagicMock,
    mock_select_single_tariff: mock.MagicMock,
    mock_fetch_site_reading_type_for_aggregator: mock.MagicMock,
    mock_SubscriptionMapper: mock.MagicMock,
    mock_select_aggregator: mock.MagicMock,
    mock_utc_now: mock.MagicMock,
):
    mock_session: AsyncSession = create_mock_session()
    rs_params = RequestStateParameters(981, None)
    now = datetime(2014, 4, 5, 6, 7, 8)
    site_id = 456
    site_reading_type_id = 5432
    sub = generate_class_instance(Sep2Subscription)
    mapped_sub = Subscription(
        resource_type=SubscriptionResource.READING, scoped_site_id=site_id + 2, resource_id=site_reading_type_id
    )

    mock_utc_now.return_value = now
    mock_select_aggregator.return_value = Aggregator(domains=[AggregatorDomain(domain="domain.value1")])
    mock_SubscriptionMapper.map_from_request = mock.Mock(return_value=mapped_sub)
    mock_insert_subscription.return_value = 98765
    mock_fetch_site_reading_type_for_aggregator.return_value = SiteReadingType(site_id=site_id)

    # Act
    with pytest.raises(BadRequestError):
        await SubscriptionManager.add_subscription_for_site(mock_session, rs_params, sub, site_id)

    assert_mock_session(mock_session, committed=False)
    mock_utc_now.assert_called_once()
    mock_select_aggregator.assert_called_once_with(mock_session, rs_params.aggregator_id)
    mock_SubscriptionMapper.map_from_request.assert_called_once_with(
        subscription=sub,
        rs_params=rs_params,
        aggregator_domains=set(["domain.value1"]),
        changed_time=now,
    )
    mock_select_single_tariff.assert_not_called()
    mock_fetch_site_reading_type_for_aggregator.assert_not_called()
    mock_insert_subscription.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.server.manager.subscription.utc_now")
@mock.patch("envoy.server.manager.subscription.select_aggregator")
@mock.patch("envoy.server.manager.subscription.SubscriptionMapper")
@mock.patch("envoy.server.manager.subscription.fetch_site_reading_type_for_aggregator")
@mock.patch("envoy.server.manager.subscription.select_single_tariff")
@mock.patch("envoy.server.manager.subscription.insert_subscription")
async def test_add_subscription_for_site_TARIFF_RATE(
    mock_insert_subscription: mock.MagicMock,
    mock_select_single_tariff: mock.MagicMock,
    mock_fetch_site_reading_type_for_aggregator: mock.MagicMock,
    mock_SubscriptionMapper: mock.MagicMock,
    mock_select_aggregator: mock.MagicMock,
    mock_utc_now: mock.MagicMock,
):
    mock_session: AsyncSession = create_mock_session()
    rs_params = RequestStateParameters(981, None)
    now = datetime(2014, 4, 5, 6, 7, 8)
    site_id = 456
    tariff_id = 5433
    sub = generate_class_instance(Sep2Subscription)
    mapped_sub = Subscription(
        resource_type=SubscriptionResource.TARIFF_GENERATED_RATE, scoped_site_id=site_id, resource_id=tariff_id
    )

    mock_utc_now.return_value = now
    mock_select_aggregator.return_value = Aggregator(domains=[AggregatorDomain(domain="domain.value1")])
    mock_SubscriptionMapper.map_from_request = mock.Mock(return_value=mapped_sub)
    mock_insert_subscription.return_value = 98765
    mock_select_single_tariff.return_value = Tariff()

    # Act
    actual_result = await SubscriptionManager.add_subscription_for_site(mock_session, rs_params, sub, site_id)

    assert actual_result == mock_insert_subscription.return_value
    assert_mock_session(mock_session, committed=True)
    mock_utc_now.assert_called_once()
    mock_select_aggregator.assert_called_once_with(mock_session, rs_params.aggregator_id)
    mock_SubscriptionMapper.map_from_request.assert_called_once_with(
        subscription=sub,
        rs_params=rs_params,
        aggregator_domains=set(["domain.value1"]),
        changed_time=now,
    )
    mock_select_single_tariff.assert_called_once_with(mock_session, tariff_id)
    mock_fetch_site_reading_type_for_aggregator.assert_not_called()
    mock_insert_subscription.assert_called_once_with(mock_session, mapped_sub)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.subscription.utc_now")
@mock.patch("envoy.server.manager.subscription.select_aggregator")
@mock.patch("envoy.server.manager.subscription.SubscriptionMapper")
@mock.patch("envoy.server.manager.subscription.fetch_site_reading_type_for_aggregator")
@mock.patch("envoy.server.manager.subscription.select_single_tariff")
@mock.patch("envoy.server.manager.subscription.insert_subscription")
async def test_add_subscription_for_site_TARIFF_RATE_missing(
    mock_insert_subscription: mock.MagicMock,
    mock_select_single_tariff: mock.MagicMock,
    mock_fetch_site_reading_type_for_aggregator: mock.MagicMock,
    mock_SubscriptionMapper: mock.MagicMock,
    mock_select_aggregator: mock.MagicMock,
    mock_utc_now: mock.MagicMock,
):
    mock_session: AsyncSession = create_mock_session()
    rs_params = RequestStateParameters(981, None)
    now = datetime(2014, 4, 5, 6, 7, 8)
    site_id = 456
    tariff_id = 5433
    sub = generate_class_instance(Sep2Subscription)
    mapped_sub = Subscription(
        resource_type=SubscriptionResource.TARIFF_GENERATED_RATE, scoped_site_id=site_id, resource_id=tariff_id
    )

    mock_utc_now.return_value = now
    mock_select_aggregator.return_value = Aggregator(domains=[AggregatorDomain(domain="domain.value1")])
    mock_SubscriptionMapper.map_from_request = mock.Mock(return_value=mapped_sub)
    mock_insert_subscription.return_value = 98765
    mock_select_single_tariff.return_value = None

    # Act
    with pytest.raises(BadRequestError):
        await SubscriptionManager.add_subscription_for_site(mock_session, rs_params, sub, site_id)

    assert_mock_session(mock_session, committed=False)
    mock_utc_now.assert_called_once()
    mock_select_aggregator.assert_called_once_with(mock_session, rs_params.aggregator_id)
    mock_SubscriptionMapper.map_from_request.assert_called_once_with(
        subscription=sub,
        rs_params=rs_params,
        aggregator_domains=set(["domain.value1"]),
        changed_time=now,
    )
    mock_select_single_tariff.assert_called_once_with(mock_session, tariff_id)
    mock_fetch_site_reading_type_for_aggregator.assert_not_called()
    mock_insert_subscription.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.server.manager.subscription.utc_now")
@mock.patch("envoy.server.manager.subscription.select_aggregator")
@mock.patch("envoy.server.manager.subscription.SubscriptionMapper")
@mock.patch("envoy.server.manager.subscription.fetch_site_reading_type_for_aggregator")
@mock.patch("envoy.server.manager.subscription.select_single_tariff")
@mock.patch("envoy.server.manager.subscription.insert_subscription")
async def test_add_subscription_for_site_READING(
    mock_insert_subscription: mock.MagicMock,
    mock_select_single_tariff: mock.MagicMock,
    mock_fetch_site_reading_type_for_aggregator: mock.MagicMock,
    mock_SubscriptionMapper: mock.MagicMock,
    mock_select_aggregator: mock.MagicMock,
    mock_utc_now: mock.MagicMock,
):
    mock_session: AsyncSession = create_mock_session()
    rs_params = RequestStateParameters(981, None)
    now = datetime(2014, 4, 5, 6, 7, 8)
    site_id = 456
    site_reading_type_id = 5432
    sub = generate_class_instance(Sep2Subscription)
    mapped_sub = Subscription(
        resource_type=SubscriptionResource.READING, scoped_site_id=site_id, resource_id=site_reading_type_id
    )

    mock_utc_now.return_value = now
    mock_select_aggregator.return_value = Aggregator(domains=[AggregatorDomain(domain="domain.value1")])
    mock_SubscriptionMapper.map_from_request = mock.Mock(return_value=mapped_sub)
    mock_insert_subscription.return_value = 98765
    mock_fetch_site_reading_type_for_aggregator.return_value = SiteReadingType(site_id=site_id)

    # Act
    actual_result = await SubscriptionManager.add_subscription_for_site(mock_session, rs_params, sub, site_id)

    assert actual_result == mock_insert_subscription.return_value
    assert_mock_session(mock_session, committed=True)
    mock_utc_now.assert_called_once()
    mock_select_aggregator.assert_called_once_with(mock_session, rs_params.aggregator_id)
    mock_SubscriptionMapper.map_from_request.assert_called_once_with(
        subscription=sub,
        rs_params=rs_params,
        aggregator_domains=set(["domain.value1"]),
        changed_time=now,
    )
    mock_select_single_tariff.assert_not_called()
    mock_fetch_site_reading_type_for_aggregator.assert_called_once_with(
        mock_session, rs_params.aggregator_id, site_reading_type_id, include_site_relation=False
    )
    mock_insert_subscription.assert_called_once_with(mock_session, mapped_sub)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.subscription.utc_now")
@mock.patch("envoy.server.manager.subscription.select_aggregator")
@mock.patch("envoy.server.manager.subscription.SubscriptionMapper")
@mock.patch("envoy.server.manager.subscription.fetch_site_reading_type_for_aggregator")
@mock.patch("envoy.server.manager.subscription.select_single_tariff")
@mock.patch("envoy.server.manager.subscription.insert_subscription")
async def test_add_subscription_for_site_READING_bad_site_id(
    mock_insert_subscription: mock.MagicMock,
    mock_select_single_tariff: mock.MagicMock,
    mock_fetch_site_reading_type_for_aggregator: mock.MagicMock,
    mock_SubscriptionMapper: mock.MagicMock,
    mock_select_aggregator: mock.MagicMock,
    mock_utc_now: mock.MagicMock,
):
    mock_session: AsyncSession = create_mock_session()
    rs_params = RequestStateParameters(981, None)
    now = datetime(2014, 4, 5, 6, 7, 8)
    site_id = 456
    site_reading_type_id = 5432
    sub = generate_class_instance(Sep2Subscription)
    mapped_sub = Subscription(
        resource_type=SubscriptionResource.READING, scoped_site_id=site_id, resource_id=site_reading_type_id
    )

    mock_utc_now.return_value = now
    mock_select_aggregator.return_value = Aggregator(domains=[AggregatorDomain(domain="domain.value1")])
    mock_SubscriptionMapper.map_from_request = mock.Mock(return_value=mapped_sub)
    mock_insert_subscription.return_value = 98765
    mock_fetch_site_reading_type_for_aggregator.return_value = SiteReadingType(site_id=site_id + 7)

    # Act
    with pytest.raises(BadRequestError):
        await SubscriptionManager.add_subscription_for_site(mock_session, rs_params, sub, site_id)

    assert_mock_session(mock_session, committed=False)
    mock_utc_now.assert_called_once()
    mock_select_aggregator.assert_called_once_with(mock_session, rs_params.aggregator_id)
    mock_SubscriptionMapper.map_from_request.assert_called_once_with(
        subscription=sub,
        rs_params=rs_params,
        aggregator_domains=set(["domain.value1"]),
        changed_time=now,
    )
    mock_select_single_tariff.assert_not_called()
    mock_fetch_site_reading_type_for_aggregator.assert_called_once_with(
        mock_session, rs_params.aggregator_id, site_reading_type_id, include_site_relation=False
    )
    mock_insert_subscription.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.server.manager.subscription.utc_now")
@mock.patch("envoy.server.manager.subscription.select_aggregator")
@mock.patch("envoy.server.manager.subscription.SubscriptionMapper")
@mock.patch("envoy.server.manager.subscription.fetch_site_reading_type_for_aggregator")
@mock.patch("envoy.server.manager.subscription.select_single_tariff")
@mock.patch("envoy.server.manager.subscription.insert_subscription")
async def test_add_subscription_for_site_READING_missing(
    mock_insert_subscription: mock.MagicMock,
    mock_select_single_tariff: mock.MagicMock,
    mock_fetch_site_reading_type_for_aggregator: mock.MagicMock,
    mock_SubscriptionMapper: mock.MagicMock,
    mock_select_aggregator: mock.MagicMock,
    mock_utc_now: mock.MagicMock,
):
    mock_session: AsyncSession = create_mock_session()
    rs_params = RequestStateParameters(981, None)
    now = datetime(2014, 4, 5, 6, 7, 8)
    site_id = 456
    site_reading_type_id = 5432
    sub = generate_class_instance(Sep2Subscription)
    mapped_sub = Subscription(
        resource_type=SubscriptionResource.READING, scoped_site_id=site_id, resource_id=site_reading_type_id
    )

    mock_utc_now.return_value = now
    mock_select_aggregator.return_value = Aggregator(domains=[AggregatorDomain(domain="domain.value1")])
    mock_SubscriptionMapper.map_from_request = mock.Mock(return_value=mapped_sub)
    mock_insert_subscription.return_value = 98765
    mock_fetch_site_reading_type_for_aggregator.return_value = None

    # Act
    with pytest.raises(BadRequestError):
        await SubscriptionManager.add_subscription_for_site(mock_session, rs_params, sub, site_id)

    assert_mock_session(mock_session, committed=False)
    mock_utc_now.assert_called_once()
    mock_select_aggregator.assert_called_once_with(mock_session, rs_params.aggregator_id)
    mock_SubscriptionMapper.map_from_request.assert_called_once_with(
        subscription=sub,
        rs_params=rs_params,
        aggregator_domains=set(["domain.value1"]),
        changed_time=now,
    )
    mock_select_single_tariff.assert_not_called()
    mock_fetch_site_reading_type_for_aggregator.assert_called_once_with(
        mock_session, rs_params.aggregator_id, site_reading_type_id, include_site_relation=False
    )
    mock_insert_subscription.assert_not_called()


@pytest.mark.anyio
@mock.patch("envoy.server.manager.subscription.utc_now")
@mock.patch("envoy.server.manager.subscription.select_aggregator")
@mock.patch("envoy.server.manager.subscription.SubscriptionMapper")
@mock.patch("envoy.server.manager.subscription.fetch_site_reading_type_for_aggregator")
@mock.patch("envoy.server.manager.subscription.select_single_tariff")
@mock.patch("envoy.server.manager.subscription.insert_subscription")
async def test_add_subscription_for_site_SITE(
    mock_insert_subscription: mock.MagicMock,
    mock_select_single_tariff: mock.MagicMock,
    mock_fetch_site_reading_type_for_aggregator: mock.MagicMock,
    mock_SubscriptionMapper: mock.MagicMock,
    mock_select_aggregator: mock.MagicMock,
    mock_utc_now: mock.MagicMock,
):
    mock_session: AsyncSession = create_mock_session()
    rs_params = RequestStateParameters(981, None)
    now = datetime(2014, 4, 5, 6, 7, 8)
    site_id = 456
    sub = generate_class_instance(Sep2Subscription)
    mapped_sub = Subscription(resource_type=SubscriptionResource.SITE, scoped_site_id=site_id, resource_id=None)

    mock_utc_now.return_value = now
    mock_select_aggregator.return_value = Aggregator(
        domains=[AggregatorDomain(domain="domain.value1"), AggregatorDomain(domain="domain.value2")]
    )
    mock_SubscriptionMapper.map_from_request = mock.Mock(return_value=mapped_sub)
    mock_insert_subscription.return_value = 98765

    # Act
    actual_result = await SubscriptionManager.add_subscription_for_site(mock_session, rs_params, sub, site_id)

    assert actual_result == mock_insert_subscription.return_value
    assert_mock_session(mock_session, committed=True)
    mock_utc_now.assert_called_once()
    mock_select_aggregator.assert_called_once_with(mock_session, rs_params.aggregator_id)
    mock_SubscriptionMapper.map_from_request.assert_called_once_with(
        subscription=sub,
        rs_params=rs_params,
        aggregator_domains=set(["domain.value1", "domain.value2"]),
        changed_time=now,
    )
    mock_select_single_tariff.assert_not_called()
    mock_fetch_site_reading_type_for_aggregator.assert_not_called()
    mock_insert_subscription.assert_called_once_with(mock_session, mapped_sub)
