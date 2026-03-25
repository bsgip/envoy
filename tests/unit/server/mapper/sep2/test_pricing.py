from datetime import datetime, timedelta, timezone
from itertools import product
from typing import Optional, Union

import pytest
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from envoy_schema.server.schema.sep2.event import EventStatusType
from envoy_schema.server.schema.sep2.metering import ReadingType
from envoy_schema.server.schema.sep2.pricing import (
    ConsumptionTariffIntervalListResponse,
    ConsumptionTariffIntervalListSummaryResponse,
    ConsumptionTariffIntervalResponse,
    RateComponentListResponse,
    RateComponentResponse,
    TariffProfileListResponse,
    TariffProfileResponse,
    TimeTariffIntervalResponse,
)
from envoy_schema.server.schema.sep2.types import ConsumptionBlockType
from envoy_schema.server.schema.uri import TariffProfileFSAListUri, TariffProfileListUri

from envoy.server.exception import NotFoundError
from envoy.server.mapper.sep2.pricing import (
    ConsumptionTariffIntervalMapper,
    RateComponentMapper,
    TariffProfileMapper,
    TimeTariffIntervalMapper,
)
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
from envoy.server.model.tariff import Tariff, TariffComponent, TariffGeneratedRate
from envoy.server.request_scope import DeviceOrAggregatorRequestScope


def test_tariff_profile_mapping():
    """Non exhaustive test of the tariff profile mapping - mainly to sanity check important fields and ensure
    that exceptions aren't being raised"""
    total_rates = 76543
    total_components = 951878
    all_set = generate_class_instance(Tariff, seed=101, optional_is_none=False)
    scope = generate_class_instance(DeviceOrAggregatorRequestScope, seed=1001)
    mapped_all_set = TariffProfileMapper.map_to_response(scope, all_set, total_components, total_rates)
    assert mapped_all_set
    assert f"/{scope.display_site_id}" in mapped_all_set.href
    assert mapped_all_set.pricePowerOfTenMultiplier == all_set.price_power_of_ten_multiplier
    assert mapped_all_set.primacyType == all_set.primacy
    assert mapped_all_set.rateCode == all_set.dnsp_code
    assert mapped_all_set.currency == all_set.currency_code
    assert mapped_all_set.RateComponentListLink and mapped_all_set.RateComponentListLink.href
    assert mapped_all_set.RateComponentListLink.href.startswith(mapped_all_set.href)
    assert f"/{scope.display_site_id}" in mapped_all_set.RateComponentListLink.href
    assert mapped_all_set.RateComponentListLink.all_ == total_components
    assert mapped_all_set.CombinedTimeTariffIntervalListLink and mapped_all_set.CombinedTimeTariffIntervalListLink.href
    assert mapped_all_set.CombinedTimeTariffIntervalListLink.href.startswith(mapped_all_set.href)
    assert f"/{scope.display_site_id}" in mapped_all_set.CombinedTimeTariffIntervalListLink.href
    assert mapped_all_set.CombinedTimeTariffIntervalListLink.all_ == total_rates
    assert mapped_all_set.RateComponentListLink.href != mapped_all_set.CombinedTimeTariffIntervalListLink.href

    some_set = generate_class_instance(Tariff, seed=202, optional_is_none=True)
    mapped_some_set = TariffProfileMapper.map_to_response(scope, some_set, total_components, total_rates)
    assert mapped_some_set
    assert f"/{scope.display_site_id}" in mapped_some_set.href
    assert mapped_some_set.pricePowerOfTenMultiplier == some_set.price_power_of_ten_multiplier
    assert mapped_some_set.primacyType == some_set.primacy
    assert mapped_some_set.rateCode == some_set.dnsp_code
    assert mapped_some_set.currency == some_set.currency_code
    assert mapped_some_set.RateComponentListLink and mapped_some_set.RateComponentListLink.href
    assert mapped_some_set.RateComponentListLink.href.startswith(mapped_some_set.href)
    assert f"/{scope.display_site_id}" in mapped_some_set.RateComponentListLink.href
    assert mapped_some_set.RateComponentListLink.all_ == total_components
    assert (
        mapped_some_set.CombinedTimeTariffIntervalListLink and mapped_some_set.CombinedTimeTariffIntervalListLink.href
    )
    assert mapped_some_set.CombinedTimeTariffIntervalListLink.href.startswith(mapped_some_set.href)
    assert f"/{scope.display_site_id}" in mapped_some_set.CombinedTimeTariffIntervalListLink.href
    assert mapped_some_set.CombinedTimeTariffIntervalListLink.all_ == total_rates
    assert mapped_some_set.RateComponentListLink.href != mapped_some_set.CombinedTimeTariffIntervalListLink.href


@pytest.mark.parametrize("optional_is_none, fsa_id", product([True, False], [1234321, None]))
def test_tariff_profile_list_mapping(optional_is_none: bool, fsa_id: Optional[int]):
    """Non exhaustive test of the tariff profile list mapping - mainly to sanity check important fields and ensure
    that exceptions aren't being raised"""
    tariffs: list[Tariff] = [
        generate_class_instance(Tariff, seed=101, optional_is_none=False),
        generate_class_instance(Tariff, seed=202, optional_is_none=True),
    ]
    tariff_component_counts = [456, 789]
    tariff_rate_counts = [987, 654]
    tariff_count = 123
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, seed=1001, optional_is_none=optional_is_none, href_prefix="/fake/prefix"
    )

    mapped = TariffProfileMapper.map_to_list_response(
        scope, zip(tariffs, tariff_component_counts, tariff_rate_counts), tariff_count, fsa_id
    )
    assert isinstance(mapped, TariffProfileListResponse)

    assert mapped.href.startswith(scope.href_prefix)
    if fsa_id is None:
        assert mapped.href.endswith(TariffProfileListUri.format(site_id=scope.display_site_id))
    else:
        assert mapped.href.endswith(TariffProfileFSAListUri.format(site_id=scope.display_site_id, fsa_id=fsa_id))

    assert mapped.all_ == tariff_count
    assert mapped.results == 2
    assert_list_type(TariffProfileResponse, mapped.TariffProfile, 2)
    assert all([f"/{scope.display_site_id}" in tp.href for tp in mapped.TariffProfile])
    assert all([f"/{scope.display_site_id}" in tp.RateComponentListLink.href for tp in mapped.TariffProfile])

    # Double check our counts get handed down to the child lists correctly
    assert mapped.TariffProfile[0].CombinedTimeTariffIntervalListLink.all_ == tariff_rate_counts[0]
    assert mapped.TariffProfile[1].CombinedTimeTariffIntervalListLink.all_ == tariff_rate_counts[1]
    assert mapped.TariffProfile[0].RateComponentListLink.all_ == tariff_component_counts[0]
    assert mapped.TariffProfile[1].RateComponentListLink.all_ == tariff_component_counts[1]


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_rate_component_create_reading_type(optional_is_none: bool):
    scope = generate_class_instance(DeviceOrAggregatorRequestScope, seed=101, href_prefix="/pfx")
    tc = generate_class_instance(TariffComponent, seed=202, optional_is_none=optional_is_none)
    result = RateComponentMapper.create_reading_type(scope, tc)
    assert isinstance(result, ReadingType)
    assert result.href and result.href.startswith("/pfx")

    # sanity checks
    assert result.uom == tc.uom
    assert result.commodity == tc.commodity
    assert result.flowDirection == tc.flow_direction


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_rate_component_map_to_response(optional_is_none: bool):
    scope = generate_class_instance(DeviceOrAggregatorRequestScope, seed=101, href_prefix="/pfx")
    tc = generate_class_instance(TariffComponent, seed=202, optional_is_none=optional_is_none)
    total_rates = 1515113
    result = RateComponentMapper.map_to_response(scope, tc, total_rates)
    assert isinstance(result, RateComponentResponse)
    all_hrefs = [result.href, result.ReadingTypeLink.href, result.TimeTariffIntervalListLink.href]
    for href in all_hrefs:
        assert href and href.startswith("/pfx")
    assert len(set(all_hrefs)) == len(all_hrefs), "All hrefs should be unique"
    assert result.TimeTariffIntervalListLink.all_ == total_rates


def test_rate_component_map_to_list_response():
    scope = generate_class_instance(DeviceOrAggregatorRequestScope, seed=101, href_prefix="/pfx")
    tcs = [
        generate_class_instance(TariffComponent, seed=202, optional_is_none=True),
        generate_class_instance(TariffComponent, seed=303, optional_is_none=False),
    ]
    total_rates = [897914, 4131]
    tariff_id = 5151968
    total_tcs = 97914

    result = RateComponentMapper.map_to_list_response(scope, tariff_id, list(zip(tcs, total_rates)), total_tcs)
    assert isinstance(result, RateComponentListResponse)

    assert result.href and result.href.startswith("/pfx")
    assert_list_type(RateComponentResponse, result.RateComponent, count=len(tcs))
    assert result.all_ == total_tcs
    assert result.results == len(tcs)

    all_hrefs = [result.href]
    for rc, expected_count in zip(result.RateComponent, total_rates):
        assert rc.TimeTariffIntervalListLink.all_ == expected_count
        all_hrefs.append(rc.href)
        all_hrefs.append(rc.ReadingTypeLink.href)
        all_hrefs.append(rc.TimeTariffIntervalListLink.href)


@pytest.mark.parametrize(
    "optional_is_none, type, cti_id",
    product([True, False], [TariffGeneratedRate, ArchiveTariffGeneratedRate], [1, 2, 3]),
)
def test_consumption_tariff_interval_map_to_response(
    optional_is_none: bool, type: Union[type[ArchiveTariffGeneratedRate], type[TariffGeneratedRate]], cti_id: int
):
    scope = generate_class_instance(DeviceOrAggregatorRequestScope, seed=101, href_prefix="/pfx")
    rate = generate_class_instance(type, seed=202, optional_is_none=optional_is_none)

    # ct_id can be 1 or 2... but only 2 if there are the optional prices specified
    expect_error = cti_id == 3 or (cti_id == 2 and optional_is_none)
    if expect_error:
        with pytest.raises(NotFoundError):
            ConsumptionTariffIntervalMapper.map_to_response(scope, rate, cti_id)
    else:
        mapped = ConsumptionTariffIntervalMapper.map_to_response(scope, rate, cti_id)
        assert isinstance(mapped, ConsumptionTariffIntervalResponse)

        if cti_id == 1:
            assert mapped.price == rate.price_pow10_encoded
            assert mapped.startValue == 0
        else:
            assert mapped.price == rate.price_pow10_encoded_block_1
            assert mapped.startValue == rate.block_1_start_pow10_encoded

        assert isinstance(mapped.consumptionBlock, ConsumptionBlockType)
        assert mapped.consumptionBlock == ConsumptionBlockType(cti_id)

        assert mapped.href and mapped.href.startswith("/pfx")
        assert f"/{cti_id}" in mapped.href
        assert str(scope.display_site_id) in mapped.href


@pytest.mark.parametrize(
    "optional_is_none, type", product([True, False], [TariffGeneratedRate, ArchiveTariffGeneratedRate])
)
def test_consumption_tariff_interval_map_to_list_response(
    optional_is_none: bool, type: Union[type[ArchiveTariffGeneratedRate], type[TariffGeneratedRate]]
):
    """Tests that the resulting object encodes all price blocks"""
    scope = generate_class_instance(DeviceOrAggregatorRequestScope, seed=101, href_prefix="/pfx")
    rate = generate_class_instance(type, seed=202, optional_is_none=optional_is_none)

    mapped = ConsumptionTariffIntervalMapper.map_to_list_response(scope, rate)
    assert isinstance(mapped, ConsumptionTariffIntervalListResponse)

    if rate.block_1_start_pow10_encoded is None or rate.price_pow10_encoded_block_1 is None:
        assert mapped.all_ == 1
        assert mapped.results == 1
        assert_list_type(ConsumptionTariffIntervalResponse, mapped.ConsumptionTariffInterval, count=1)

        assert mapped.ConsumptionTariffInterval[0].startValue == 0
        assert mapped.ConsumptionTariffInterval[0].price == rate.price_pow10_encoded
    else:
        assert mapped.all_ == 2
        assert mapped.results == 2
        assert_list_type(ConsumptionTariffIntervalResponse, mapped.ConsumptionTariffInterval, count=2)
        assert mapped.ConsumptionTariffInterval[0].startValue == 0
        assert mapped.ConsumptionTariffInterval[0].price == rate.price_pow10_encoded

        assert mapped.ConsumptionTariffInterval[1].startValue == rate.block_1_start_pow10_encoded
        assert mapped.ConsumptionTariffInterval[1].price == rate.price_pow10_encoded_block_1

    assert mapped.href and mapped.href.startswith("/pfx")
    assert mapped.ConsumptionTariffInterval[0].href.startswith("/pfx")
    assert mapped.ConsumptionTariffInterval[0].href != mapped.href


@pytest.mark.parametrize(
    "optional_is_none, type", product([True, False], [TariffGeneratedRate, ArchiveTariffGeneratedRate])
)
def test_consumption_tariff_interval_map_to_summary_list_response(
    optional_is_none: bool, type: Union[type[ArchiveTariffGeneratedRate], type[TariffGeneratedRate]]
):
    """Tests that the resulting object is a singleton list"""
    scope = generate_class_instance(DeviceOrAggregatorRequestScope, seed=101, href_prefix="/pfx")
    rate = generate_class_instance(type, seed=202, optional_is_none=optional_is_none)

    mapped = ConsumptionTariffIntervalMapper.map_to_summary_list_response(scope, rate)
    assert isinstance(mapped, ConsumptionTariffIntervalListSummaryResponse)

    if rate.block_1_start_pow10_encoded is None or rate.price_pow10_encoded_block_1 is None:
        assert mapped.all_ == 1
        assert mapped.results == 1
        assert_list_type(ConsumptionTariffIntervalResponse, mapped.ConsumptionTariffInterval, count=1)

        assert mapped.ConsumptionTariffInterval[0].startValue == 0
        assert mapped.ConsumptionTariffInterval[0].price == rate.price_pow10_encoded
        assert mapped.ConsumptionTariffInterval[0].href.startswith("/pfx")
    else:
        assert mapped.all_ == 2
        assert mapped.results == 2
        assert_list_type(ConsumptionTariffIntervalResponse, mapped.ConsumptionTariffInterval, count=2)
        assert mapped.ConsumptionTariffInterval[0].startValue == 0
        assert mapped.ConsumptionTariffInterval[0].price == rate.price_pow10_encoded
        assert mapped.ConsumptionTariffInterval[0].href.startswith("/pfx")

        assert mapped.ConsumptionTariffInterval[1].startValue == rate.block_1_start_pow10_encoded
        assert mapped.ConsumptionTariffInterval[1].price == rate.price_pow10_encoded_block_1
        assert mapped.ConsumptionTariffInterval[1].href.startswith("/pfx")

    assert mapped.href is None, "No href for the summary list - it's not a dedicated resource"


@pytest.mark.parametrize(
    "optional_is_none, time_diff, type",
    product(
        [True, False],
        [timedelta(0), timedelta(hours=1), timedelta(hours=-1)],
        [TariffGeneratedRate, ArchiveTariffGeneratedRate],
    ),
)
def test_time_tariff_interval_map_to_response(
    optional_is_none: bool,
    time_diff: timedelta,
    type: Union[type[ArchiveTariffGeneratedRate], type[TariffGeneratedRate]],
):
    """Non exhaustive test on TimeTariffInterval mapping - mainly to catch any validation issues"""

    scope = generate_class_instance(DeviceOrAggregatorRequestScope, seed=101, href_prefix="/pfx")
    rate = generate_class_instance(type, seed=202, optional_is_none=optional_is_none)

    now = rate.start_time + time_diff

    mapped = TimeTariffIntervalMapper.map_to_response(scope, now, rate)
    assert isinstance(mapped, TimeTariffIntervalResponse)

    if type == ArchiveTariffGeneratedRate and rate.deleted_time is not None:
        assert mapped.EventStatus_.currentStatus == EventStatusType.Cancelled
        assert mapped.EventStatus_.dateTime == int(rate.deleted_time.timestamp())
    elif now < rate.start_time:
        assert mapped.EventStatus_.currentStatus == EventStatusType.Scheduled
        assert mapped.EventStatus_.dateTime == int(rate.changed_time.timestamp())
    else:
        assert mapped.EventStatus_.currentStatus == EventStatusType.Active
        assert mapped.EventStatus_.dateTime == int(rate.changed_time.timestamp())

    # We can have either 1 or 2 consumption blocks
    assert mapped.ConsumptionTariffIntervalListSummary.href is None
    if rate.block_1_start_pow10_encoded is None or rate.price_pow10_encoded_block_1 is None:
        expected_consumption_blocks = 1

    else:
        expected_consumption_blocks = 2
    assert mapped.ConsumptionTariffIntervalListLink.all_ == expected_consumption_blocks
    assert mapped.ConsumptionTariffIntervalListSummary.all_ == expected_consumption_blocks
    assert mapped.ConsumptionTariffIntervalListSummary.results == expected_consumption_blocks

    assert_list_type(
        ConsumptionTariffIntervalResponse,
        mapped.ConsumptionTariffIntervalListSummary.ConsumptionTariffInterval,
        count=expected_consumption_blocks,
    )
    mapped.ConsumptionTariffIntervalListSummary.ConsumptionTariffInterval[0].price == rate.price_pow10_encoded
    mapped.ConsumptionTariffIntervalListSummary.ConsumptionTariffInterval[0].startValue == 0
    if expected_consumption_blocks > 1:
        mapped.ConsumptionTariffIntervalListSummary.ConsumptionTariffInterval[
            1
        ].price == rate.price_pow10_encoded_block_1
        mapped.ConsumptionTariffIntervalListSummary.ConsumptionTariffInterval[
            1
        ].startValue == rate.block_1_start_pow10_encoded

    all_hrefs = [mapped.href, mapped.RateComponentLink.href, mapped.ConsumptionTariffIntervalListLink.href]
    for href in all_hrefs:
        assert href and href.startswith("/pfx")
    assert len(set(all_hrefs)) == len(all_hrefs), "All hrefs should be unique"

    assert isinstance(mapped.mRID, str)
    assert len(mapped.mRID) == 32, "Expected 128 bits of hex chars"


@pytest.mark.parametrize("tariff_component_id", [None, 716874614])
def test_time_tariff_interval_map_to_list_response(tariff_component_id: Optional[int]):
    """Non exhaustive test on TimeTariffIntervalList mapping - mainly to catch any validation issues"""
    scope = generate_class_instance(DeviceOrAggregatorRequestScope, seed=1001, href_prefix="/pfx")
    rates: list[TariffGeneratedRate] = [
        generate_class_instance(TariffGeneratedRate, seed=101, optional_is_none=False),
        generate_class_instance(TariffGeneratedRate, seed=202, optional_is_none=True),
    ]
    now = datetime(2022, 1, 5, tzinfo=timezone.utc)
    tariff_id = 198774112
    total = 63251

    mapped = TimeTariffIntervalMapper.map_to_list_response(scope, tariff_id, tariff_component_id, now, rates, total)
    assert mapped.all_ == total
    assert mapped.results == len(rates)
    assert mapped.href is not None and mapped.href.startswith("/pfx")
    assert f"/{tariff_id}/" in mapped.href
    if tariff_component_id is not None:
        assert f"/{tariff_component_id}/" in mapped.href
        assert "/ctti" not in mapped.href
    else:
        assert "/ctti" in mapped.href
    assert "//" not in mapped.href

    assert_list_type(TimeTariffIntervalResponse, mapped.TimeTariffInterval, len(rates))
    list_items_mrids = [x.mRID for x in mapped.TimeTariffInterval]
    assert len(list_items_mrids) == len(set(list_items_mrids)), "Checking all list items are unique"


def test_mrid_uniqueness():
    """Test our mrid's for the mapped entities differ from each other despite sharing database ids"""
    id = 1
    now = datetime(2026, 1, 4, tzinfo=timezone.utc)

    tariff = generate_class_instance(Tariff)
    component = generate_class_instance(TariffComponent)
    rate = generate_class_instance(TariffGeneratedRate)
    tariff.tariff_id = id
    component.tariff_id = id
    component.tariff_component_id = id
    rate.tariff_id = id
    rate.tariff_component_id = id
    rate.tariff_generated_rate_id = id
    rate.site_id = id

    scope: DeviceOrAggregatorRequestScope = generate_class_instance(DeviceOrAggregatorRequestScope)

    tti = TimeTariffIntervalMapper.map_to_response(scope, now, rate)
    rc = RateComponentMapper.map_to_response(scope, component, 999)
    tp = TariffProfileMapper.map_to_response(scope, tariff, 999, 999)

    assert tti.mRID != rc.mRID
    assert tti.mRID != tp.mRID
    assert rc.mRID != tp.mRID
