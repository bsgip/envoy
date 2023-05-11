import unittest.mock as mock
from datetime import date, datetime, time
from decimal import Decimal
from typing import Union

import pytest

from envoy.server.crud.pricing import TariffGeneratedRateDailyStats
from envoy.server.exception import InvalidIdError
from envoy.server.manager.pricing import (
    ConsumptionTariffIntervalManager,
    RateComponentManager,
    TariffProfileManager,
    TimeTariffIntervalManager,
)
from envoy.server.mapper.sep2.pricing import TOTAL_PRICING_READING_TYPES, PricingReadingType
from envoy.server.model.site import Site
from envoy.server.model.tariff import Tariff, TariffGeneratedRate
from envoy.server.schema.sep2.pricing import (
    ConsumptionTariffIntervalListResponse,
    ConsumptionTariffIntervalResponse,
    RateComponentListResponse,
    RateComponentResponse,
    TariffProfileListResponse,
    TariffProfileResponse,
    TimeTariffIntervalListResponse,
    TimeTariffIntervalResponse,
)
from tests.data.fake.generator import generate_class_instance
from tests.postgres_testing import generate_async_session
from tests.unit.mocks import assert_mock_session, create_mock_session


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
    tariffs = [generate_class_instance(Tariff)]
    mapped_tariffs = generate_class_instance(TariffProfileListResponse)

    mock_select_all_tariffs.return_value = tariffs
    mock_select_tariff_count.return_value = count
    mock_TariffProfileMapper.map_to_list_nosite_response = mock.Mock(return_value=mapped_tariffs)

    response = await TariffProfileManager.fetch_tariff_profile_list_no_site(mock_session, start, changed, limit)
    assert response is mapped_tariffs

    mock_select_all_tariffs.assert_called_once_with(mock_session, start, changed, limit)
    mock_select_tariff_count.assert_called_once_with(mock_session, changed)
    mock_TariffProfileMapper.map_to_list_nosite_response.assert_called_once_with(tariffs, count)
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
    agg_id = 543
    site_id = 987
    tariff_count = 33
    tariff_1: Tariff = generate_class_instance(Tariff, seed=101)
    tariff_2: Tariff = generate_class_instance(Tariff, seed=202)
    tariff_1_rate_count = 9814
    tariff_2_rate_count = 4521
    tariffs = [tariff_1, tariff_2]
    mapped_tariffs = generate_class_instance(TariffProfileListResponse)

    def count_unique_rate_days_handler(
        session, aggregator_id: int, tariff_id: int, site_id: int, changed_after: datetime
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
    response = await TariffProfileManager.fetch_tariff_profile_list(
        mock_session, agg_id, site_id, start, changed, limit
    )

    # Assert
    assert response is mapped_tariffs
    mock_select_all_tariffs.assert_called_once_with(mock_session, start, changed, limit)
    mock_select_tariff_count.assert_called_once_with(mock_session, changed)
    assert_mock_session(mock_session)

    # We called count_unique_rate_days for each tariff returned
    all_mock_count_args = [c.args for c in mock_count_unique_rate_days.call_args_list]
    assert mock_count_unique_rate_days.call_count == 2
    assert (mock_session, agg_id, tariff_1.tariff_id, site_id, changed) in all_mock_count_args
    assert (mock_session, agg_id, tariff_2.tariff_id, site_id, changed) in all_mock_count_args

    # make sure we properly bundled up the resulting tariff + rate count tuples and passed it along to the mapper
    mock_TariffProfileMapper.map_to_list_response.assert_called_once()
    call_args = mock_TariffProfileMapper.map_to_list_response.call_args_list[0].args
    (tariffs_with_rates, total_tariffs, called_site_id) = call_args
    assert list(tariffs_with_rates) == [
        (tariff_1, tariff_1_rate_count * TOTAL_PRICING_READING_TYPES),
        (tariff_2, tariff_2_rate_count * TOTAL_PRICING_READING_TYPES),
    ]
    assert total_tariffs == tariff_count
    assert called_site_id == site_id


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.TariffProfileMapper")
@mock.patch("envoy.server.manager.pricing.select_single_tariff")
async def test_fetch_tariff_profile_nosite(
    mock_select_single_tariff: mock.MagicMock, mock_TariffProfileMapper: mock.MagicMock
):
    """Simple test to ensure dependencies are called correctly"""
    mock_session = create_mock_session()
    tariff_id = 111
    tariff = generate_class_instance(Tariff)
    mapped_tp = generate_class_instance(TariffProfileResponse)

    mock_select_single_tariff.return_value = tariff
    mock_TariffProfileMapper.map_to_nosite_response = mock.Mock(return_value=mapped_tp)

    response = await TariffProfileManager.fetch_tariff_profile_no_site(mock_session, tariff_id)
    assert response is mapped_tp

    mock_select_single_tariff.assert_called_once_with(mock_session, tariff_id)
    mock_TariffProfileMapper.map_to_nosite_response.assert_called_once_with(tariff)
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.select_single_tariff")
async def test_fetch_tariff_profile_nosite_missing(mock_select_single_tariff: mock.MagicMock):
    """Simple test to ensure dependencies are called correctly"""
    mock_session = create_mock_session()
    tariff_id = 111

    mock_select_single_tariff.return_value = None

    response = await TariffProfileManager.fetch_tariff_profile_no_site(mock_session, tariff_id)
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
    agg_id = 111
    tariff_id = 222
    site_id = 333
    rates = 444

    tariff = generate_class_instance(Tariff)
    mapped_tp = generate_class_instance(TariffProfileResponse)

    mock_select_single_tariff.return_value = tariff
    mock_count_unique_rate_days.return_value = rates
    mock_TariffProfileMapper.map_to_response = mock.Mock(return_value=mapped_tp)

    response = await TariffProfileManager.fetch_tariff_profile(mock_session, agg_id, tariff_id, site_id)
    assert response is mapped_tp

    mock_select_single_tariff.assert_called_once_with(mock_session, tariff_id)
    expected_count = rates * TOTAL_PRICING_READING_TYPES
    mock_TariffProfileMapper.map_to_response.assert_called_once_with(tariff, site_id, expected_count)
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.select_single_tariff")
async def test_fetch_tariff_profile_missing(mock_select_single_tariff: mock.MagicMock):
    """Simple test to ensure dependencies are called correctly"""
    mock_session = create_mock_session()
    agg_id = 111
    tariff_id = 222
    site_id = 333

    mock_select_single_tariff.return_value = None

    response = await TariffProfileManager.fetch_tariff_profile(mock_session, agg_id, tariff_id, site_id)
    assert response is None

    mock_select_single_tariff.assert_called_once_with(mock_session, tariff_id)
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.RateComponentMapper")
@mock.patch("envoy.server.manager.pricing.count_tariff_rates_for_day")
async def test_fetch_rate_component(
    mock_count_tariff_rates_for_day: mock.MagicMock, mock_RateComponentMapper: mock.MagicMock
):
    """Simple test to ensure dependencies are called correctly"""
    mock_session = create_mock_session()
    tariff_id = 111
    agg_id = 222
    site_id = 333
    count = 444
    rc_id = "2012-02-03"
    mapped_rc = generate_class_instance(RateComponentResponse)
    pricing_type = PricingReadingType.EXPORT_ACTIVE_POWER_KWH

    mock_count_tariff_rates_for_day.return_value = count
    mock_RateComponentMapper.map_to_response = mock.Mock(return_value=mapped_rc)

    response = await RateComponentManager.fetch_rate_component(
        mock_session, agg_id, tariff_id, site_id, rc_id, pricing_type
    )
    assert response is mapped_rc

    mock_count_tariff_rates_for_day.assert_called_once_with(
        mock_session, agg_id, tariff_id, site_id, date(2012, 2, 3), datetime.min
    )
    mock_RateComponentMapper.map_to_response.assert_called_once_with(
        count, tariff_id, site_id, pricing_type, date(2012, 2, 3)
    )
    assert_mock_session(mock_session)


@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.RateComponentMapper")
@mock.patch("envoy.server.manager.pricing.select_rate_daily_stats")
async def test_fetch_rate_component_list(
    mock_select_rate_daily_stats: mock.MagicMock, mock_RateComponentMapper: mock.MagicMock
):
    """Tests usage of basic dependencies in a simple case"""
    mock_session = create_mock_session()
    tariff_id = 111
    agg_id = 222
    site_id = 333
    changed_after = datetime.now()
    input_date_counts = [(date(2012, 1, 2), 5)]
    total_distinct_dates = 62
    start = 4
    limit = 8
    mapped_list = generate_class_instance(RateComponentListResponse)
    rate_stats = TariffGeneratedRateDailyStats(
        single_date_counts=input_date_counts, total_distinct_dates=total_distinct_dates
    )

    mock_select_rate_daily_stats.return_value = rate_stats
    mock_RateComponentMapper.map_to_list_response = mock.Mock(return_value=mapped_list)

    list_response = await RateComponentManager.fetch_rate_component_list(
        mock_session, agg_id, tariff_id, site_id, start, changed_after, limit
    )
    assert list_response is mapped_list

    # check mock assumptions
    mock_select_rate_daily_stats.assert_called_once_with(
        mock_session, agg_id, tariff_id, site_id, 1, changed_after, 2  # adjusted start
    )  # adjusted limit
    mock_RateComponentMapper.map_to_list_response.assert_called_once_with(rate_stats, 0, 0, tariff_id, site_id)
    assert_mock_session(mock_session)


@pytest.mark.parametrize(
    "page_data",
    [
        # no pagination - oversized limit
        (
            ([(date(2023, 1, 2), 3), (date(2023, 1, 3), 4), (date(2023, 1, 4), 5)], 0, 99),  # Input data/start/limit
            (date(2023, 1, 2), 3, PricingReadingType.IMPORT_ACTIVE_POWER_KWH),  # First output child RateComponent
            (date(2023, 1, 4), 5, PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # Last output child RateComponent
            12,  # Expected total items in list
        ),
        # no pagination - matched limit
        (
            ([(date(2023, 1, 2), 3), (date(2023, 1, 3), 4), (date(2023, 1, 4), 5)], 0, 12),  # Input data/start/limit
            (date(2023, 1, 2), 3, PricingReadingType.IMPORT_ACTIVE_POWER_KWH),  # First output child RateComponent
            (date(2023, 1, 4), 5, PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # Last output child RateComponent
            12,  # Expected total items in list
        ),
        # no pagination - undersized limit
        (
            ([(date(2023, 1, 2), 3), (date(2023, 1, 3), 4), (date(2023, 1, 4), 5)], 0, 10),  # Input data/start/limit
            (date(2023, 1, 2), 3, PricingReadingType.IMPORT_ACTIVE_POWER_KWH),  # First output child RateComponent
            (date(2023, 1, 4), 5, PricingReadingType.EXPORT_ACTIVE_POWER_KWH),  # Last output child RateComponent
            10,  # Expected total items in list
        ),
        # unaligned pagination - oversized limit
        (
            ([(date(2023, 1, 2), 3), (date(2023, 1, 3), 4), (date(2023, 1, 4), 5)], 2, 99),  # Input data/start/limit
            (date(2023, 1, 2), 3, PricingReadingType.IMPORT_REACTIVE_POWER_KVARH),  # First output child RateComponent
            (date(2023, 1, 4), 5, PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # Last output child RateComponent
            10,  # Expected total items in list
        ),
        # aligned pagination - oversized limit
        (
            ([(date(2023, 1, 3), 4), (date(2023, 1, 4), 5)], 4, 99),  # Input data/start/limit
            (date(2023, 1, 3), 4, PricingReadingType.IMPORT_ACTIVE_POWER_KWH),  # First output child RateComponent
            (date(2023, 1, 4), 5, PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # Last output child RateComponent
            8,  # Expected total items in list
        ),
        # aligned pagination - matched limit
        (
            ([(date(2023, 1, 3), 4), (date(2023, 1, 4), 5)], 4, 8),  # Input data/start/limit
            (date(2023, 1, 3), 4, PricingReadingType.IMPORT_ACTIVE_POWER_KWH),  # First output child RateComponent
            (date(2023, 1, 4), 5, PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # Last output child RateComponent
            8,  # Expected total items in list
        ),
        # misaligned pagination - technically aligned limit
        (
            ([(date(2023, 1, 3), 4), (date(2023, 1, 4), 5)], 3, 5),  # Input data/start/limit
            (date(2023, 1, 3), 4, PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # First output child RateComponent
            (date(2023, 1, 4), 5, PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # Last output child RateComponent
            5,  # Expected total items in list
        ),
    ],
)
@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.select_rate_daily_stats")
async def test_fetch_rate_component_list_pagination(mock_select_rate_daily_stats: mock.MagicMock, page_data):
    """This test technically integrates with the mapper directly to double check the integration with
    the virtual pagination is running as expected.

    It does overlap a little with tests on the mapper but because this is so finnicky - I think it's worth it
    for a little more safety"""
    (
        (input_date_counts, start, limit),
        (first_date, first_count, first_price_type),
        (last_date, last_count, last_price_type),
        expected_count,
    ) = page_data

    mock_session = create_mock_session()
    tariff_id = 111
    agg_id = 222
    site_id = 333
    changed_after = datetime.now()

    mock_select_rate_daily_stats.return_value = TariffGeneratedRateDailyStats(
        single_date_counts=input_date_counts, total_distinct_dates=42
    )

    list_response = await RateComponentManager.fetch_rate_component_list(
        mock_session, agg_id, tariff_id, site_id, start, changed_after, limit
    )
    assert list_response.all_ == 42 * TOTAL_PRICING_READING_TYPES
    assert list_response.results == expected_count
    assert len(list_response.RateComponent) == expected_count

    # validate the first / last RateComponents
    if expected_count > 0:
        first = list_response.RateComponent[0]
        assert first.href.endswith(f"/{first_price_type}"), f"{first.href} should end with /{first_price_type}"
        assert f"/{first_date.isoformat()}/" in first.href
        assert first.TimeTariffIntervalListLink.all_ == first_count

        last = list_response.RateComponent[-1]
        assert last.href.endswith(f"/{last_price_type}"), f"{last.href} should end with /{last_price_type}"
        assert f"/{last_date.isoformat()}/" in last.href
        assert last.TimeTariffIntervalListLink.all_ == last_count

    # check mock assumptions
    mock_select_rate_daily_stats.assert_called_once()
    assert_mock_session(mock_session)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "page_data",
    [
        # misaligned pagination - technically aligned limit
        (
            (3, 5),  # Input data/start/limit
            (date(2022, 3, 5), 2, PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # First output child RateComponent
            (date(2022, 3, 6), 1, PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # Last output child RateComponent
            5,  # Expected total items in list
        ),
        (
            (3, 3),  # Input data/start/limit
            (date(2022, 3, 5), 2, PricingReadingType.EXPORT_REACTIVE_POWER_KVARH),  # First output child RateComponent
            (date(2022, 3, 6), 1, PricingReadingType.EXPORT_ACTIVE_POWER_KWH),  # Last output child RateComponent
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
        (first_date, first_count, first_price_type),
        (last_date, last_count, last_price_type),
        expected_count,
    ) = page_data

    async with generate_async_session(pg_base_config) as session:
        list_response = await RateComponentManager.fetch_rate_component_list(
            session, 1, 1, 1, start, datetime.min, limit
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
            assert first.TimeTariffIntervalListLink.all_ == first_count

            last = list_response.RateComponent[-1]
            assert last.href.endswith(f"/{last_price_type}"), f"{last.href} should end with /{last_price_type}"
            assert f"/{last_date.isoformat()}/" in last.href
            assert last.TimeTariffIntervalListLink.all_ == last_count


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
    site_id = 11223344
    aggregator_id = 44322
    rate_component_id = "2022-02-01"
    time_tariff_interval = "13:37"
    price = 12345
    pricing_type = PricingReadingType.EXPORT_ACTIVE_POWER_KWH
    mapped_cti_list = generate_class_instance(ConsumptionTariffIntervalListResponse)
    mock_session = create_mock_session()
    mock_RateComponentManager.parse_rate_component_id = mock.Mock(return_value=date(2022, 1, 2))
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id = mock.Mock(return_value=time(1, 2))
    mock_select_single_site_with_site_id.return_value = generate_class_instance(Site)
    mock_ConsumptionTariffIntervalMapper.map_to_list_response = mock.Mock(return_value=mapped_cti_list)

    result = await ConsumptionTariffIntervalManager.fetch_consumption_tariff_interval_list(
        mock_session, aggregator_id, tariff_id, site_id, rate_component_id, pricing_type, time_tariff_interval, price
    )
    assert result is mapped_cti_list

    # check we validated the ids
    mock_RateComponentManager.parse_rate_component_id.assert_called_once_with(rate_component_id)
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id.assert_called_once_with(time_tariff_interval)
    mock_select_single_site_with_site_id.assert_called_once_with(
        mock_session, site_id=site_id, aggregator_id=aggregator_id
    )
    mock_ConsumptionTariffIntervalMapper.map_to_list_response.assert_called_once_with(
        tariff_id, site_id, pricing_type, date(2022, 1, 2), time(1, 2), Decimal("1.2345")
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
    site_id = 11223344
    aggregator_id = 44322
    rate_component_id = "2023-02-01"
    time_tariff_interval = "09:08"
    price = -14567
    pricing_type = PricingReadingType.IMPORT_ACTIVE_POWER_KWH
    mapped_cti = generate_class_instance(ConsumptionTariffIntervalResponse)
    mock_session = create_mock_session()
    mock_RateComponentManager.parse_rate_component_id = mock.Mock(return_value=date(2022, 1, 2))
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id = mock.Mock(return_value=time(1, 2))
    mock_select_single_site_with_site_id.return_value = generate_class_instance(Site)
    mock_ConsumptionTariffIntervalMapper.map_to_response = mock.Mock(return_value=mapped_cti)

    cti = await ConsumptionTariffIntervalManager.fetch_consumption_tariff_interval(
        mock_session, aggregator_id, tariff_id, site_id, rate_component_id, pricing_type, time_tariff_interval, price
    )
    assert cti is mapped_cti

    # check we validated the ids
    mock_RateComponentManager.parse_rate_component_id.assert_called_once_with(rate_component_id)
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id.assert_called_once_with(time_tariff_interval)
    mock_select_single_site_with_site_id.assert_called_once_with(
        mock_session, site_id=site_id, aggregator_id=aggregator_id
    )
    mock_ConsumptionTariffIntervalMapper.map_to_response.assert_called_once_with(
        tariff_id, site_id, pricing_type, date(2022, 1, 2), time(1, 2), Decimal("-1.4567")
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
    site_id = 11223344
    aggregator_id = 44322
    rate_component_id = "2023-02-01"
    time_tariff_interval = "09:08"
    pricing_type = PricingReadingType.IMPORT_ACTIVE_POWER_KWH
    existing_rate: TariffGeneratedRate = generate_class_instance(TariffGeneratedRate)
    mapped_interval: TimeTariffIntervalResponse = generate_class_instance(TimeTariffIntervalResponse)
    mock_session = create_mock_session()
    parsed_date = date(2022, 1, 2)
    parsed_time = time(3, 4)

    mock_RateComponentManager.parse_rate_component_id = mock.Mock(return_value=parsed_date)
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id = mock.Mock(return_value=parsed_time)
    mock_select_tariff_rate_for_day_time.return_value = existing_rate
    mock_TimeTariffIntervalMapper.map_to_response.return_value = mapped_interval

    # Act
    result = await TimeTariffIntervalManager.fetch_time_tariff_interval(
        mock_session, aggregator_id, tariff_id, site_id, rate_component_id, time_tariff_interval, pricing_type
    )

    # Assert
    assert result is mapped_interval
    mock_RateComponentManager.parse_rate_component_id.assert_called_once_with(rate_component_id)
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id.assert_called_once_with(time_tariff_interval)
    mock_select_tariff_rate_for_day_time.assert_called_once_with(
        mock_session, aggregator_id, tariff_id, site_id, parsed_date, parsed_time
    )
    mock_TimeTariffIntervalMapper.map_to_response.assert_called_once_with(existing_rate, pricing_type)
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
    site_id = 11223344
    aggregator_id = 44322
    rate_component_id = "2023-02-01"
    time_tariff_interval = "09:08"
    pricing_type = PricingReadingType.IMPORT_ACTIVE_POWER_KWH
    mock_session = create_mock_session()
    parsed_date = date(2022, 1, 2)
    parsed_time = time(3, 4)

    mock_RateComponentManager.parse_rate_component_id = mock.Mock(return_value=parsed_date)
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id = mock.Mock(return_value=parsed_time)
    mock_select_tariff_rate_for_day_time.return_value = None

    # Act
    result = await TimeTariffIntervalManager.fetch_time_tariff_interval(
        mock_session, aggregator_id, tariff_id, site_id, rate_component_id, time_tariff_interval, pricing_type
    )

    # Assert
    assert result is None
    mock_RateComponentManager.parse_rate_component_id.assert_called_once_with(rate_component_id)
    mock_TimeTariffIntervalManager.parse_time_tariff_interval_id.assert_called_once_with(time_tariff_interval)
    mock_select_tariff_rate_for_day_time.assert_called_once_with(
        mock_session, aggregator_id, tariff_id, site_id, parsed_date, parsed_time
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
    site_id = 11223344
    aggregator_id = 44322
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

    mock_RateComponentManager.parse_rate_component_id = mock.Mock(return_value=parsed_date)
    mock_select_tariff_rates_for_day.return_value = existing_rates
    mock_count_tariff_rates_for_day.return_value = total_rate_count
    mock_TimeTariffIntervalMapper.map_to_list_response.return_value = mapped_list_response

    # Act
    result = await TimeTariffIntervalManager.fetch_time_tariff_interval_list(
        mock_session, aggregator_id, tariff_id, site_id, rate_component_id, pricing_type, start, after, limit
    )

    # Assert
    assert result is mapped_list_response
    mock_RateComponentManager.parse_rate_component_id.assert_called_once_with(rate_component_id)
    mock_select_tariff_rates_for_day.assert_called_once_with(
        mock_session, aggregator_id, tariff_id, site_id, parsed_date, start, after, limit
    )
    mock_count_tariff_rates_for_day.assert_called_once_with(
        mock_session, aggregator_id, tariff_id, site_id, parsed_date, after
    )
    mock_TimeTariffIntervalMapper.map_to_list_response.assert_called_once_with(
        existing_rates, pricing_type, total_rate_count
    )
    assert_mock_session(mock_session)
