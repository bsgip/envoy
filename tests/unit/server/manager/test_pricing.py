import unittest.mock as mock
from datetime import datetime
from itertools import product
from typing import Optional

import pytest
from assertical.fake.generator import generate_class_instance
from assertical.fake.sqlalchemy import assert_mock_session, create_mock_session
from envoy_schema.server.schema.sep2.pricing import RateComponentListResponse, TariffProfileListResponse

from envoy.server.manager.pricing import RateComponentManager, TariffProfileManager
from envoy.server.model.tariff import Tariff, TariffComponent
from envoy.server.request_scope import SiteRequestScope


@pytest.mark.parametrize("fsa_id, n_tariffs", product([333, None], [0, 1, 2]))
@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.TariffProfileMapper.map_to_list_response")
@mock.patch("envoy.server.manager.pricing.select_all_tariffs")
@mock.patch("envoy.server.manager.pricing.select_tariff_count")
@mock.patch("envoy.server.manager.pricing.count_tariff_components_by_tariff")
@mock.patch("envoy.server.manager.pricing.count_active_rates_include_deleted")
async def test_fetch_tariff_profile_list_counts_members(
    mock_count_active_rates_include_deleted: mock.MagicMock,
    mock_count_tariff_components_by_tariff: mock.MagicMock,
    mock_select_tariff_count: mock.MagicMock,
    mock_select_all_tariffs: mock.MagicMock,
    mock_map_to_list_response: mock.MagicMock,
    fsa_id: Optional[int],
    n_tariffs: int,
):
    """Tests that the function correctly interrogates the counts for each list item returned and correctly passes
    it off to the mapper function"""
    # Arrange
    mock_session = create_mock_session()
    start = 111
    changed = datetime.now()
    limit = 222
    tariff_count = 33

    all_tariffs = [generate_class_instance(Tariff, seed=i, tariff_id=i) for i in range(n_tariffs)]
    count_components = [i for i in range(n_tariffs)]
    count_rates = [i * 11 for i in range(n_tariffs)]

    mapped_tariffs = generate_class_instance(TariffProfileListResponse)
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=1001, aggregator_id=665, site_id=776)

    mock_select_all_tariffs.return_value = all_tariffs
    mock_select_tariff_count.return_value = tariff_count

    mock_count_active_rates_include_deleted.side_effect = count_rates
    mock_count_tariff_components_by_tariff.side_effect = count_components
    mock_map_to_list_response.return_value = mapped_tariffs

    # Act
    response = await TariffProfileManager.fetch_tariff_profile_list(mock_session, scope, start, changed, limit, fsa_id)

    # Assert
    assert response is mapped_tariffs
    mock_select_all_tariffs.assert_called_once_with(mock_session, start, changed, limit, fsa_id)
    mock_select_tariff_count.assert_called_once_with(mock_session, changed, fsa_id)
    assert_mock_session(mock_session)

    assert mock_count_active_rates_include_deleted.call_count == n_tariffs
    assert mock_count_tariff_components_by_tariff.call_count == n_tariffs

    # make sure we properly bundled up the resulting tariff + rate count tuples and passed it along to the mapper
    mock_map_to_list_response.assert_called_once()
    call_args = mock_map_to_list_response.call_args_list[0].args
    passed_scope, tariffs_with_rates, total_tariffs, mapped_fsa_id = call_args
    assert list(tariffs_with_rates) == list(zip(all_tariffs, count_components, count_rates))
    assert total_tariffs == tariff_count
    assert mapped_fsa_id == fsa_id
    assert passed_scope is scope


@pytest.mark.parametrize("n_rates", [0, 1, 2])
@pytest.mark.anyio
@mock.patch("envoy.server.manager.pricing.RateComponentMapper.map_to_list_response")
@mock.patch("envoy.server.manager.pricing.select_tariff_components_by_tariff")
@mock.patch("envoy.server.manager.pricing.count_tariff_components_by_tariff")
@mock.patch("envoy.server.manager.pricing.count_active_rates_include_deleted")
async def test_fetch_rate_component_list_counts_members(
    mock_count_active_rates_include_deleted: mock.MagicMock,
    mock_count_tariff_components_by_tariff: mock.MagicMock,
    mock_select_tariff_components_by_tariff: mock.MagicMock,
    mock_map_to_list_response: mock.MagicMock,
    n_rates: int,
):
    """Tests that the function correctly interrogates the counts for each list item returned and correctly passes
    it off to the mapper function"""
    mock_session = create_mock_session()
    changed_after = datetime.now()
    tariff_id = 1441
    start = 4
    limit = 8
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=1001)
    mapped_list = generate_class_instance(RateComponentListResponse)

    count_components = 141
    all_components = [
        generate_class_instance(TariffComponent, seed=i, tariff_component_id=i, tariff_id=tariff_id)
        for i in range(n_rates)
    ]
    count_rates = [i * 111 for i in range(n_rates)]

    mock_select_tariff_components_by_tariff.return_value = all_components
    mock_count_tariff_components_by_tariff.return_value = count_components
    mock_count_active_rates_include_deleted.side_effect = count_rates
    mock_map_to_list_response.return_value = mapped_list

    list_response = await RateComponentManager.fetch_rate_component_list(
        mock_session, scope, tariff_id, start, changed_after, limit
    )
    assert list_response is mapped_list

    # make sure we properly bundled up the resulting tariff + rate count tuples and passed it along to the mapper
    mock_map_to_list_response.assert_called_once_with(
        scope, tariff_id, list(zip(all_components, count_rates)), count_components
    )
    assert_mock_session(mock_session)
