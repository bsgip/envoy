import unittest.mock as mock
from datetime import date, datetime, time
from decimal import Decimal
from typing import Union

import pytest
from assertical.fake.generator import generate_class_instance
from assertical.fake.sqlalchemy import assert_mock_session, create_mock_session
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.pricing import (
    ConsumptionTariffIntervalListResponse,
    ConsumptionTariffIntervalResponse,
    RateComponentListResponse,
    RateComponentResponse,
    TariffProfileListResponse,
    TariffProfileResponse,
    TimeTariffIntervalListResponse,
    TimeTariffIntervalResponse,
)

from envoy.server.exception import InvalidIdError
from envoy.server.manager.pricing import (
    ConsumptionTariffIntervalManager,
    RateComponentManager,
    TariffProfileManager,
    TimeTariffIntervalManager,
)
from envoy.server.mapper.constants import PricingReadingType
from envoy.server.mapper.sep2.pricing import TOTAL_PRICING_READING_TYPES
from envoy.server.model.site import Site
from envoy.server.model.tariff import Tariff, TariffGeneratedRate
from envoy.server.request_scope import BaseRequestScope, SiteRequestScope


@pytest.mark.parametrize(
    "input, output",
    [
        ("2022-11-10", date(2022, 11, 10)),
        ("2036-09-30", date(2036, 9, 30)),
        ("1985-01-02", date(1985, 1, 2)),
        ("2020-02-29", date(2020, 2, 29)),
        ("", InvalidIdError),
        ("2022", InvalidIdError),
        ("2022/10/09", InvalidIdError),
        ("2022-11-31", InvalidIdError),  # There is no 31st Nov
        ("2021-02-29", InvalidIdError),  # Not a leap year
        ("2022-Nov-02", InvalidIdError),
    ],
)
def test_parse_rate_component_id(input: str, output: Union[date, type]):
    """Simple test on parser generating valid values / catching errors"""
    if isinstance(output, date):
        assert RateComponentManager.parse_rate_component_id(input) == output
    else:
        with pytest.raises(output):
            RateComponentManager.parse_rate_component_id(input) == output


@pytest.mark.parametrize(
    "input, output",
    [
        ("11:59", time(11, 59)),
        ("13:01", time(13, 1)),
        ("02:34", time(2, 34)),
        ("00:00", time(0, 0)),
        ("23:59", time(23, 59)),
        ("", InvalidIdError),
        ("12:3", InvalidIdError),
        ("1:32", InvalidIdError),
        ("12:60", InvalidIdError),
        ("24:01", InvalidIdError),
        ("11-12", InvalidIdError),
        ("11 12", InvalidIdError),
        ("11", InvalidIdError),
        (" 12:13 ", InvalidIdError),
    ],
)
def test_parse_time_tariff_interval_id(input: str, output: Union[time, type]):
    """Simple test on parser generating valid values / catching errors"""
    if isinstance(output, time):
        assert TimeTariffIntervalManager.parse_time_tariff_interval_id(input) == output
    else:
        with pytest.raises(output):
            TimeTariffIntervalManager.parse_time_tariff_interval_id(input) == output


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.TariffProfileMapper")
@mock.patch("envoy.server.manager.pricing.select_all_tariffs")
@mock.patch("envoy.server.manager.pricing.select_tariff_count")
async def test_fetch_tariff_profile_list_no_site(
    mock_select_tariff_count: mock.MagicMock,
    mock_select_all_tariffs: mock.MagicMock,
    mock_TariffProfileMapper: mock.MagicMock,
):
    """Simple test to ensure dependencies are called correctly"""
    mock_session = create_mock_session()
    start = 111
    changed = datetime.now()
    limit = 222
    count = 33
    scope: BaseRequestScope = generate_class_instance(BaseRequestScope, seed=1001)
    tariffs = [generate_class_instance(Tariff)]
    mapped_tariffs = generate_class_instance(TariffProfileListResponse)

    mock_select_all_tariffs.return_value = tariffs
    mock_select_tariff_count.return_value = count
    mock_TariffProfileMapper.map_to_list_nosite_response = mock.Mock(return_value=mapped_tariffs)

    response = await TariffProfileManager.fetch_tariff_profile_list_no_site(mock_session, scope, start, changed, limit)
    assert response is mapped_tariffs

    mock_select_all_tariffs.assert_called_once_with(mock_session, start, changed, limit, None)
    mock_select_tariff_count.assert_called_once_with(mock_session, changed, None)
    mock_TariffProfileMapper.map_to_list_nosite_response.assert_called_once_with(scope, tariffs, count)
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.TariffProfileMapper")
@mock.patch("envoy.server.manager.pricing.select_all_tariffs")
@mock.patch("envoy.server.manager.pricing.select_tariff_count")
@mock.patch("envoy.server.manager.pricing.count_unique_rate_days")
async def test_fetch_tariff_profile_list(
    mock_count_unique_rate_days: mock.MagicMock,
    mock_select_tariff_count: mock.MagicMock,
    mock_select_all_tariffs: mock.MagicMock,
    mock_TariffProfileMapper: mock.MagicMock,
):
    """Simple test to ensure dependencies are called correctly"""
    # Arrange
    mock_session = create_mock_session()
    start = 111
    changed = datetime.now()
    limit = 222
    fsa_id = 333
    tariff_count = 33
    tariff_1: Tariff = generate_class_instance(Tariff, seed=101)
    tariff_2: Tariff = generate_class_instance(Tariff, seed=202)
    tariff_1_rate_count = 9814
    tariff_2_rate_count = 4521
    tariffs = [tariff_1, tariff_2]
    mapped_tariffs = generate_class_instance(TariffProfileListResponse)
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=1001, aggregator_id=665, site_id=776)

    def count_unique_rate_days_handler(
        session, scope: SiteRequestScope, tariff_id: int, site_id: int, changed_after: datetime
    ) -> int:
        if tariff_id == tariff_1.tariff_id:
            return tariff_1_rate_count
        elif tariff_id == tariff_2.tariff_id:
            return tariff_2_rate_count
        else:
            raise Exception(f"unknown tariff_id {tariff_id}")

    mock_select_all_tariffs.return_value = tariffs
    mock_select_tariff_count.return_value = tariff_count
    mock_TariffProfileMapper.map_to_list_response = mock.Mock(return_value=mapped_tariffs)
    mock_count_unique_rate_days.side_effect = count_unique_rate_days_handler

    # Act
    response = await TariffProfileManager.fetch_tariff_profile_list(mock_session, scope, start, changed, limit, fsa_id)

    # Assert
    assert response is mapped_tariffs
    mock_select_all_tariffs.assert_called_once_with(mock_session, start, changed, limit, fsa_id)
    mock_select_tariff_count.assert_called_once_with(mock_session, changed, fsa_id)
    assert_mock_session(mock_session)

    # We called count_unique_rate_days for each tariff returned
    all_mock_count_args = [c.args for c in mock_count_unique_rate_days.call_args_list]
    assert mock_count_unique_rate_days.call_count == 2
    assert (mock_session, scope.aggregator_id, tariff_1.tariff_id, scope.site_id, changed) in all_mock_count_args
    assert (mock_session, scope.aggregator_id, tariff_2.tariff_id, scope.site_id, changed) in all_mock_count_args

    # make sure we properly bundled up the resulting tariff + rate count tuples and passed it along to the mapper
    mock_TariffProfileMapper.map_to_list_response.assert_called_once()
    call_args = mock_TariffProfileMapper.map_to_list_response.call_args_list[0].args
    passed_scope, tariffs_with_rates, total_tariffs, mapped_fsa_id = call_args
    assert list(tariffs_with_rates) == [
        (tariff_1, tariff_1_rate_count * TOTAL_PRICING_READING_TYPES),
        (tariff_2, tariff_2_rate_count * TOTAL_PRICING_READING_TYPES),
    ]
    assert total_tariffs == tariff_count
    assert mapped_fsa_id == fsa_id
    assert passed_scope is scope


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.TariffProfileMapper")
@mock.patch("envoy.server.manager.pricing.select_single_tariff")
async def test_fetch_tariff_profile_nosite(
    mock_select_single_tariff: mock.MagicMock, mock_TariffProfileMapper: mock.MagicMock
):
    """Simple test to ensure dependencies are called correctly"""
    mock_session = create_mock_session()
    tariff_id = 111
    scope: BaseRequestScope = generate_class_instance(BaseRequestScope, seed=1001)
    tariff = generate_class_instance(Tariff)
    mapped_tp = generate_class_instance(TariffProfileResponse)

    mock_select_single_tariff.return_value = tariff
    mock_TariffProfileMapper.map_to_nosite_response = mock.Mock(return_value=mapped_tp)

    response = await TariffProfileManager.fetch_tariff_profile_no_site(mock_session, scope, tariff_id)
    assert response is mapped_tp

    mock_select_single_tariff.assert_called_once_with(mock_session, tariff_id)
    mock_TariffProfileMapper.map_to_nosite_response.assert_called_once_with(scope, tariff)
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.select_single_tariff")
async def test_fetch_tariff_profile_nosite_missing(mock_select_single_tariff: mock.MagicMock):
    """Simple test to ensure dependencies are called correctly"""
    mock_session = create_mock_session()
    tariff_id = 111
    scope: BaseRequestScope = generate_class_instance(BaseRequestScope, seed=1001)
    mock_select_single_tariff.return_value = None

    response = await TariffProfileManager.fetch_tariff_profile_no_site(mock_session, scope, tariff_id)
    assert response is None

    mock_select_single_tariff.assert_called_once_with(mock_session, tariff_id)
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.TariffProfileMapper")
@mock.patch("envoy.server.manager.pricing.select_single_tariff")
@mock.patch("envoy.server.manager.pricing.count_unique_rate_days")
async def test_fetch_tariff_profile(
    mock_count_unique_rate_days: mock.MagicMock,
    mock_select_single_tariff: mock.MagicMock,
    mock_TariffProfileMapper: mock.MagicMock,
):
    """Simple test to ensure dependencies are called correctly"""
    mock_session = create_mock_session()
    tariff_id = 222
    rates = 444
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=1001)

    tariff = generate_class_instance(Tariff)
    mapped_tp = generate_class_instance(TariffProfileResponse)

    mock_select_single_tariff.return_value = tariff
    mock_count_unique_rate_days.return_value = rates
    mock_TariffProfileMapper.map_to_response = mock.Mock(return_value=mapped_tp)

    response = await TariffProfileManager.fetch_tariff_profile(mock_session, scope, tariff_id)
    assert response is mapped_tp

    mock_select_single_tariff.assert_called_once_with(mock_session, tariff_id)
    expected_count = rates * TOTAL_PRICING_READING_TYPES
    mock_TariffProfileMapper.map_to_response.assert_called_once_with(scope, tariff, expected_count)
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.select_single_tariff")
async def test_fetch_tariff_profile_missing(mock_select_single_tariff: mock.MagicMock):
    """Simple test to ensure dependencies are called correctly"""
    mock_session = create_mock_session()
    tariff_id = 222
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=1001)

    mock_select_single_tariff.return_value = None

    response = await TariffProfileManager.fetch_tariff_profile(mock_session, scope, tariff_id)
    assert response is None

    mock_select_single_tariff.assert_called_once_with(mock_session, tariff_id)
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.RateComponentMapper")
async def test_fetch_rate_component(mock_RateComponentMapper: mock.MagicMock):
    """Simple test to ensure dependencies are called correctly"""
    tariff_id = 111
    rc_id = "2012-02-03"
    mapped_rc = generate_class_instance(RateComponentResponse)
    pricing_type = PricingReadingType.EXPORT_ACTIVE_POWER_KWH
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=1001)

    mock_RateComponentMapper.map_to_response = mock.Mock(return_value=mapped_rc)

    response = await RateComponentManager.fetch_rate_component(scope, tariff_id, rc_id, pricing_type)
    assert response is mapped_rc

    mock_RateComponentMapper.map_to_response.assert_called_once_with(scope, tariff_id, pricing_type, date(2012, 2, 3))


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.RateComponentMapper")
@mock.patch("envoy.server.manager.pricing.select_unique_rate_days")
async def test_fetch_rate_component_list(
    mock_select_unique_rate_days: mock.MagicMock, mock_RateComponentMapper: mock.MagicMock
):
    """Tests usage of basic dependencies in a simple case"""
    mock_session = create_mock_session()
    tariff_id = 111
    changed_after = datetime.now()
    input_dates = [date(2012, 1, 2)]
    total_distinct_dates = 62
    start = 4
    limit = 8
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=1001)
    mapped_list = generate_class_instance(RateComponentListResponse)

    mock_select_unique_rate_days.return_value = (input_dates, total_distinct_dates)
    mock_RateComponentMapper.map_to_list_response = mock.Mock(return_value=mapped_list)

    list_response = await RateComponentManager.fetch_rate_component_list(
        mock_session, scope, tariff_id, start, changed_after, limit
    )
    assert list_response is mapped_list

    # check mock assumptions
    mock_select_unique_rate_days.assert_called_once_with(
        mock_session, scope.aggregator_id, tariff_id, scope.site_id, 1, changed_after, 2  # adjusted start
    )  # adjusted limit
    mock_RateComponentMapper.map_to_list_response.assert_called_once_with(
        scope, input_dates, total_distinct_dates, 0, 0, tariff_id
    )
    assert_mock_session(mock_session)


@pytest.mark.parametrize(
    "page_data",
    [
        # no pagination - oversized limit
        (
            ([date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)], 0, 99),  # Input data/start/limit
            (date(2023, 1, 2), PricingReadingType.IMPORT_ACTIVE_POWER_KWH),  # First output child RateComponent
            (date(2023, 1, 4), PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # Last output child RateComponent
            12,  # Expected total items in list
        ),
        # no pagination - matched limit
        (
            ([date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)], 0, 12),  # Input data/start/limit
            (date(2023, 1, 2), PricingReadingType.IMPORT_ACTIVE_POWER_KWH),  # First output child RateComponent
            (date(2023, 1, 4), PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # Last output child RateComponent
            12,  # Expected total items in list
        ),
        # no pagination - undersized limit
        (
            ([date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)], 0, 10),  # Input data/start/limit
            (date(2023, 1, 2), PricingReadingType.IMPORT_ACTIVE_POWER_KWH),  # First output child RateComponent
            (date(2023, 1, 4), PricingReadingType.EXPORT_ACTIVE_POWER_KWH),  # Last output child RateComponent
            10,  # Expected total items in list
        ),
        # unaligned pagination - oversized limit
        (
            ([date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)], 2, 99),  # Input data/start/limit
            (date(2023, 1, 2), PricingReadingType.IMPORT_REACTIVE_POWER_KVARH),  # First output child RateComponent
            (date(2023, 1, 4), PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # Last output child RateComponent
            10,  # Expected total items in list
        ),
        # aligned pagination - oversized limit
        (
            ([date(2023, 1, 3), date(2023, 1, 4)], 4, 99),  # Input data/start/limit
            (date(2023, 1, 3), PricingReadingType.IMPORT_ACTIVE_POWER_KWH),  # First output child RateComponent
            (date(2023, 1, 4), PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # Last output child RateComponent
            8,  # Expected total items in list
        ),
        # aligned pagination - matched limit
        (
            ([date(2023, 1, 3), date(2023, 1, 4)], 4, 8),  # Input data/start/limit
            (date(2023, 1, 3), PricingReadingType.IMPORT_ACTIVE_POWER_KWH),  # First output child RateComponent
            (date(2023, 1, 4), PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # Last output child RateComponent
            8,  # Expected total items in list
        ),
        # misaligned pagination - technically aligned limit
        (
            ([date(2023, 1, 3), date(2023, 1, 4)], 3, 5),  # Input data/start/limit
            (date(2023, 1, 3), PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # First output child RateComponent
            (date(2023, 1, 4), PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # Last output child RateComponent
            5,  # Expected total items in list
        ),
    ],
)
@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.select_unique_rate_days")
async def test_fetch_rate_component_list_pagination(mock_select_unique_rate_days: mock.MagicMock, page_data):
    """This test technically integrates with the mapper directly to double check the integration with
    the virtual pagination is running as expected.

    It does overlap a little with tests on the mapper but because this is so finnicky - I think it's worth it
    for a little more safety"""
    (
        (input_dates, start, limit),
        (first_date, first_price_type),
        (last_date, last_price_type),
        expected_count,
    ) = page_data

    mock_session = create_mock_session()
    tariff_id = 111
    changed_after = datetime.now()
    total_distinct_dates = 515215
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=1001)

    mock_select_unique_rate_days.return_value = (input_dates, total_distinct_dates)

    list_response = await RateComponentManager.fetch_rate_component_list(
        mock_session, scope, tariff_id, start, changed_after, limit
    )
    assert list_response.all_ == total_distinct_dates * TOTAL_PRICING_READING_TYPES
    assert list_response.results == expected_count
    assert len(list_response.RateComponent) == expected_count

    # validate the first / last RateComponents
    if expected_count > 0:
        first = list_response.RateComponent[0]
        assert first.href.endswith(f"/{first_price_type}"), f"{first.href} should end with /{first_price_type}"
        assert f"/{first_date.isoformat()}/" in first.href

        last = list_response.RateComponent[-1]
        assert last.href.endswith(f"/{last_price_type}"), f"{last.href} should end with /{last_price_type}"
        assert f"/{last_date.isoformat()}/" in last.href

    # check mock assumptions
    mock_select_unique_rate_days.assert_called_once()
    assert_mock_session(mock_session)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "page_data",
    [
        # misaligned pagination - technically aligned limit
        (
            (3, 5),  # Input data/start/limit
            (date(2022, 3, 5), PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # First output child RateComponent
            (date(2022, 3, 6), PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # Last output child RateComponent
            5,  # Expected total items in list
        ),
        (
            (3, 3),  # Input data/start/limit
            (date(2022, 3, 5), PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # First output child RateComponent
            (date(2022, 3, 6), PricingReadingType.EXPORT_ACTIVE_POWER_KWH),  # Last output child RateComponent
            3,  # Expected total items in list
        ),
    ],
)
async def test_fetch_rate_component_list_full_db(pg_base_config, page_data):
    """This test technically integrates with the mapper directly to double check the integration with
    the virtual pagination is running as expected.

    It does overlap a little with tests on the mapper but because this is so finnicky - I think it's worth it
    for a little more safety"""

    (
        (start, limit),
        (first_date, first_price_type),
        (last_date, last_price_type),
        expected_count,
    ) = page_data
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=1001, aggregator_id=1, site_id=1)

    async with generate_async_session(pg_base_config) as session:
        list_response = await RateComponentManager.fetch_rate_component_list(
            session, scope, 1, start, datetime.min, limit
        )

        assert (
            list_response.all_ == 2 * TOTAL_PRICING_READING_TYPES
        ), "There are 2 distinct dates in base config for these filters"
        assert list_response.results == expected_count
        assert len(list_response.RateComponent) == expected_count

        if expected_count > 0:
            first = list_response.RateComponent[0]
            assert first.href.endswith(f"/{first_price_type}"), f"{first.href} should end with /{first_price_type}"
            assert f"/{first_date.isoformat()}/" in first.href

            last = list_response.RateComponent[-1]
            assert last.href.endswith(f"/{last_price_type}"), f"{last.href} should end with /{last_price_type}"
            assert f"/{last_date.isoformat()}/" in last.href


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.TimeTariffIntervalManager")
@mock.patch("envoy.server.manager.pricing.RateComponentManager")
@mock.patch("envoy.server.manager.pricing.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.pricing.ConsumptionTariffIntervalMapper")
async def test_fetch_consumption_tariff_interval_list(
    mock_ConsumptionTariffIntervalMapper: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
    mock_RateComponentManager: mock.MagicMock,
    mock_TimeTariffIntervalManager: mock.MagicMock,
):
    tariff_id = 54321
    rate_component_id = "2022-02-01"
    time_tariff_interval = "13:37"
    price = 12345
    pricing_type = PricingReadingType.EXPORT_ACTIVE_POWER_KWH
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=1001)
    mapped_cti_list = generate_class_instance(ConsumptionTariffIntervalListResponse)
    mock_session = create_mock_session()
    mock_RateComponentManager.parse_rate_component_id = mock.Mock(return_value=date(2022, 1, 2))
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id = mock.Mock(return_value=time(1, 2))
    mock_select_single_site_with_site_id.return_value = generate_class_instance(Site)
    mock_ConsumptionTariffIntervalMapper.map_to_list_response = mock.Mock(return_value=mapped_cti_list)

    result = await ConsumptionTariffIntervalManager.fetch_consumption_tariff_interval_list(
        mock_session,
        scope,
        tariff_id,
        rate_component_id,
        pricing_type,
        time_tariff_interval,
        price,
    )
    assert result is mapped_cti_list

    # check we validated the ids
    mock_RateComponentManager.parse_rate_component_id.assert_called_once_with(rate_component_id)
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id.assert_called_once_with(time_tariff_interval)
    mock_select_single_site_with_site_id.assert_called_once_with(
        mock_session, site_id=scope.site_id, aggregator_id=scope.aggregator_id
    )
    mock_ConsumptionTariffIntervalMapper.map_to_list_response.assert_called_once_with(
        scope, tariff_id, pricing_type, date(2022, 1, 2), time(1, 2), Decimal("1.2345")
    )  # converted price
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.TimeTariffIntervalManager")
@mock.patch("envoy.server.manager.pricing.RateComponentManager")
@mock.patch("envoy.server.manager.pricing.select_single_site_with_site_id")
@mock.patch("envoy.server.manager.pricing.ConsumptionTariffIntervalMapper")
async def test_fetch_consumption_tariff_interval(
    mock_ConsumptionTariffIntervalMapper: mock.MagicMock,
    mock_select_single_site_with_site_id: mock.MagicMock,
    mock_RateComponentManager: mock.MagicMock,
    mock_TimeTariffIntervalManager: mock.MagicMock,
):
    tariff_id = 665544
    rate_component_id = "2023-02-01"
    time_tariff_interval = "09:08"
    price = -14567
    pricing_type = PricingReadingType.IMPORT_ACTIVE_POWER_KWH
    mapped_cti = generate_class_instance(ConsumptionTariffIntervalResponse)
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=1001)
    mock_session = create_mock_session()
    mock_RateComponentManager.parse_rate_component_id = mock.Mock(return_value=date(2022, 1, 2))
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id = mock.Mock(return_value=time(1, 2))
    mock_select_single_site_with_site_id.return_value = generate_class_instance(Site)
    mock_ConsumptionTariffIntervalMapper.map_to_response = mock.Mock(return_value=mapped_cti)

    cti = await ConsumptionTariffIntervalManager.fetch_consumption_tariff_interval(
        mock_session,
        scope,
        tariff_id,
        rate_component_id,
        pricing_type,
        time_tariff_interval,
        price,
    )
    assert cti is mapped_cti

    # check we validated the ids
    mock_RateComponentManager.parse_rate_component_id.assert_called_once_with(rate_component_id)
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id.assert_called_once_with(time_tariff_interval)
    mock_select_single_site_with_site_id.assert_called_once_with(
        mock_session, site_id=scope.site_id, aggregator_id=scope.aggregator_id
    )
    mock_ConsumptionTariffIntervalMapper.map_to_response.assert_called_once_with(
        scope, tariff_id, pricing_type, date(2022, 1, 2), time(1, 2), Decimal("-1.4567")
    )  # converted price
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.TimeTariffIntervalMapper")
@mock.patch("envoy.server.manager.pricing.TimeTariffIntervalManager")
@mock.patch("envoy.server.manager.pricing.RateComponentManager")
@mock.patch("envoy.server.manager.pricing.select_tariff_rate_for_day_time")
async def test_fetch_time_tariff_interval_existing(
    mock_select_tariff_rate_for_day_time: mock.MagicMock,
    mock_RateComponentManager: mock.MagicMock,
    mock_TimeTariffIntervalManager: mock.MagicMock,
    mock_TimeTariffIntervalMapper: mock.MagicMock,
):
    """Tests the manager correctly interacts with dependencies"""
    tariff_id = 665544
    rate_component_id = "2023-02-01"
    time_tariff_interval = "09:08"
    pricing_type = PricingReadingType.IMPORT_ACTIVE_POWER_KWH
    existing_rate: TariffGeneratedRate = generate_class_instance(TariffGeneratedRate)
    mapped_interval: TimeTariffIntervalResponse = generate_class_instance(TimeTariffIntervalResponse)
    mock_session = create_mock_session()
    parsed_date = date(2022, 1, 2)
    parsed_time = time(3, 4)
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=1001)

    mock_RateComponentManager.parse_rate_component_id = mock.Mock(return_value=parsed_date)
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id = mock.Mock(return_value=parsed_time)
    mock_select_tariff_rate_for_day_time.return_value = existing_rate
    mock_TimeTariffIntervalMapper.map_to_response.return_value = mapped_interval

    # Act
    result = await TimeTariffIntervalManager.fetch_time_tariff_interval(
        mock_session,
        scope,
        tariff_id,
        rate_component_id,
        time_tariff_interval,
        pricing_type,
    )

    # Assert
    assert result is mapped_interval
    mock_RateComponentManager.parse_rate_component_id.assert_called_once_with(rate_component_id)
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id.assert_called_once_with(time_tariff_interval)
    mock_select_tariff_rate_for_day_time.assert_called_once_with(
        mock_session, scope.aggregator_id, tariff_id, scope.site_id, parsed_date, parsed_time
    )
    mock_TimeTariffIntervalMapper.map_to_response.assert_called_once_with(scope, existing_rate, pricing_type)
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.TimeTariffIntervalManager")
@mock.patch("envoy.server.manager.pricing.RateComponentManager")
@mock.patch("envoy.server.manager.pricing.select_tariff_rate_for_day_time")
async def test_fetch_time_tariff_interval_missing(
    mock_select_tariff_rate_for_day_time: mock.MagicMock,
    mock_RateComponentManager: mock.MagicMock,
    mock_TimeTariffIntervalManager: mock.MagicMock,
):
    """Tests the manager correctly interacts with dependencies when there is no rate"""
    tariff_id = 665544
    rate_component_id = "2023-02-01"
    time_tariff_interval = "09:08"
    pricing_type = PricingReadingType.IMPORT_ACTIVE_POWER_KWH
    mock_session = create_mock_session()
    parsed_date = date(2022, 1, 2)
    parsed_time = time(3, 4)
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=1001)

    mock_RateComponentManager.parse_rate_component_id = mock.Mock(return_value=parsed_date)
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id = mock.Mock(return_value=parsed_time)
    mock_select_tariff_rate_for_day_time.return_value = None

    # Act
    result = await TimeTariffIntervalManager.fetch_time_tariff_interval(
        mock_session,
        scope,
        tariff_id,
        rate_component_id,
        time_tariff_interval,
        pricing_type,
    )

    # Assert
    assert result is None
    mock_RateComponentManager.parse_rate_component_id.assert_called_once_with(rate_component_id)
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id.assert_called_once_with(time_tariff_interval)
    mock_select_tariff_rate_for_day_time.assert_called_once_with(
        mock_session, scope.aggregator_id, tariff_id, scope.site_id, parsed_date, parsed_time
    )
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.TimeTariffIntervalMapper")
@mock.patch("envoy.server.manager.pricing.RateComponentManager")
@mock.patch("envoy.server.manager.pricing.select_tariff_rates_for_day")
@mock.patch("envoy.server.manager.pricing.count_tariff_rates_for_day")
async def test_fetch_time_tariff_interval_list(
    mock_count_tariff_rates_for_day: mock.MagicMock,
    mock_select_tariff_rates_for_day: mock.MagicMock,
    mock_RateComponentManager: mock.MagicMock,
    mock_TimeTariffIntervalMapper: mock.MagicMock,
):
    """Tests the manager correctly interacts with dependencies"""
    tariff_id = 665544
    rate_component_id = "2023-02-01"
    pricing_type = PricingReadingType.IMPORT_ACTIVE_POWER_KWH
    existing_rates: list[TariffGeneratedRate] = [generate_class_instance(TariffGeneratedRate)]
    mapped_list_response: TimeTariffIntervalListResponse = generate_class_instance(TimeTariffIntervalListResponse)
    total_rate_count = 542
    mock_session = create_mock_session()
    parsed_date = date(2022, 1, 2)
    start = 2
    after = datetime(2023, 1, 2, 3, 4)
    limit = 5
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=1001)

    mock_RateComponentManager.parse_rate_component_id = mock.Mock(return_value=parsed_date)
    mock_select_tariff_rates_for_day.return_value = existing_rates
    mock_count_tariff_rates_for_day.return_value = total_rate_count
    mock_TimeTariffIntervalMapper.map_to_list_response.return_value = mapped_list_response

    # Act
    result = await TimeTariffIntervalManager.fetch_time_tariff_interval_list(
        mock_session,
        scope,
        tariff_id,
        rate_component_id,
        pricing_type,
        start,
        after,
        limit,
    )

    # Assert
    assert result is mapped_list_response
    mock_RateComponentManager.parse_rate_component_id.assert_called_once_with(rate_component_id)
    mock_select_tariff_rates_for_day.assert_called_once_with(
        mock_session, scope.aggregator_id, tariff_id, scope.site_id, parsed_date, start, after, limit
    )
    mock_count_tariff_rates_for_day.assert_called_once_with(
        mock_session, scope.aggregator_id, tariff_id, scope.site_id, parsed_date, after
    )
    mock_TimeTariffIntervalMapper.map_to_list_response.assert_called_once_with(
        scope, existing_rates, pricing_type, total_rate_count
    )
    assert_mock_session(mock_session)
