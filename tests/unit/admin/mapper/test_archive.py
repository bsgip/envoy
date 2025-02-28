from datetime import datetime, timezone

from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_nowish
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from envoy_schema.admin.schema.archive import (
    ArchiveDynamicOperatingEnvelopeResponse,
    ArchivePageResponse,
    ArchiveSiteResponse,
    ArchiveTariffGeneratedRateResponse,
)

from envoy.admin.mapper.archive import ArchiveListMapper, ArchiveMapper
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.archive.site import ArchiveSite
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate


def test_map_to_site_response():
    all = generate_class_instance(ArchiveSite, seed=101, optional_is_none=False)
    optional = generate_class_instance(ArchiveSite, seed=202, optional_is_none=True)

    all_mapped = ArchiveMapper.map_to_site_response(all)
    assert isinstance(all_mapped, ArchiveSiteResponse)
    assert_class_instance_equality(ArchiveSite, all, all_mapped, {"registration_pin"})  # These should just map 1-1
    assert all_mapped.groups == []
    assert all_mapped.der_availability is None
    assert all_mapped.der_config is None
    assert all_mapped.der_status is None

    optional_mapped = ArchiveMapper.map_to_site_response(optional)
    assert isinstance(optional_mapped, ArchiveSiteResponse)
    assert_class_instance_equality(
        ArchiveSite, optional, optional_mapped, {"archive_time", "registration_pin"}
    )  # These should just map 1-1
    assert_nowish(optional_mapped.archive_time)  # This is a workaround in case we get some bad data


def test_map_to_paged_site_response():
    sites = [
        generate_class_instance(ArchiveSite, seed=101, optional_is_none=False),
        generate_class_instance(ArchiveSite, seed=202, optional_is_none=True),
        generate_class_instance(ArchiveSite, seed=303, optional_is_none=True, generate_relationships=True),
    ]

    limit = 123
    start = 456
    total_count = 789
    period_start = datetime(2022, 11, 12, 4, 5, 6, tzinfo=timezone.utc)
    period_end = datetime(2023, 12, 13, 5, 6, 7, tzinfo=timezone.utc)

    page_response = ArchiveListMapper.map_to_sites_response(total_count, sites, start, limit, period_start, period_end)
    assert isinstance(page_response, ArchivePageResponse)
    assert_list_type(ArchiveSiteResponse, page_response.entities, len(sites))
    assert page_response.period_end == period_end
    assert page_response.period_start == period_start
    assert page_response.limit == limit
    assert page_response.start == start
    assert page_response.total_count == total_count


def test_map_to_doe_response():
    all = generate_class_instance(ArchiveDynamicOperatingEnvelope, seed=101, optional_is_none=False)
    optional = generate_class_instance(ArchiveDynamicOperatingEnvelope, seed=202, optional_is_none=True)

    all_mapped = ArchiveMapper.map_to_doe_response(all)
    assert isinstance(all_mapped, ArchiveDynamicOperatingEnvelopeResponse)
    assert_class_instance_equality(
        ArchiveDynamicOperatingEnvelopeResponse, all, all_mapped
    )  # These should just map 1-1

    optional_mapped = ArchiveMapper.map_to_doe_response(optional)
    assert isinstance(optional_mapped, ArchiveDynamicOperatingEnvelopeResponse)
    assert_class_instance_equality(
        ArchiveDynamicOperatingEnvelopeResponse, optional, optional_mapped, {"archive_time"}
    )  # These should just map 1-1
    assert_nowish(optional_mapped.archive_time)  # This is a workaround in case we get some bad data


def test_map_to_paged_doe_response():
    does = [
        generate_class_instance(ArchiveDynamicOperatingEnvelope, seed=101, optional_is_none=False),
        generate_class_instance(ArchiveDynamicOperatingEnvelope, seed=202, optional_is_none=True),
        generate_class_instance(
            ArchiveDynamicOperatingEnvelope, seed=303, optional_is_none=True, generate_relationships=True
        ),
    ]

    limit = 123
    start = 456
    total_count = 789
    period_start = datetime(2022, 11, 12, 4, 5, 6, tzinfo=timezone.utc)
    period_end = datetime(2023, 12, 13, 5, 6, 7, tzinfo=timezone.utc)

    page_response = ArchiveListMapper.map_to_does_response(total_count, does, start, limit, period_start, period_end)
    assert isinstance(page_response, ArchivePageResponse)
    assert_list_type(ArchiveDynamicOperatingEnvelopeResponse, page_response.entities, len(does))
    assert page_response.period_end == period_end
    assert page_response.period_start == period_start
    assert page_response.limit == limit
    assert page_response.start == start
    assert page_response.total_count == total_count


def test_map_to_rate_response():
    all = generate_class_instance(ArchiveTariffGeneratedRate, seed=101, optional_is_none=False)
    optional = generate_class_instance(ArchiveTariffGeneratedRate, seed=202, optional_is_none=True)

    all_mapped = ArchiveMapper.map_to_rate_response(all)
    assert isinstance(all_mapped, ArchiveTariffGeneratedRateResponse)
    assert_class_instance_equality(ArchiveTariffGeneratedRateResponse, all, all_mapped)  # These should just map 1-1

    optional_mapped = ArchiveMapper.map_to_rate_response(optional)
    assert isinstance(optional_mapped, ArchiveTariffGeneratedRateResponse)
    assert_class_instance_equality(
        ArchiveTariffGeneratedRateResponse, optional, optional_mapped, {"archive_time"}
    )  # These should just map 1-1
    assert_nowish(optional_mapped.archive_time)  # This is a workaround in case we get some bad data


def test_map_to_paged_rate_response():
    rates = [
        generate_class_instance(ArchiveTariffGeneratedRate, seed=101, optional_is_none=False),
        generate_class_instance(ArchiveTariffGeneratedRate, seed=202, optional_is_none=True),
        generate_class_instance(
            ArchiveTariffGeneratedRate, seed=303, optional_is_none=True, generate_relationships=True
        ),
    ]

    limit = 123
    start = 456
    total_count = 789
    period_start = datetime(2022, 11, 12, 4, 5, 6, tzinfo=timezone.utc)
    period_end = datetime(2023, 12, 13, 5, 6, 7, tzinfo=timezone.utc)

    page_response = ArchiveListMapper.map_to_rates_response(total_count, rates, start, limit, period_start, period_end)
    assert isinstance(page_response, ArchivePageResponse)
    assert_list_type(ArchiveTariffGeneratedRateResponse, page_response.entities, len(rates))
    assert page_response.period_end == period_end
    assert page_response.period_start == period_start
    assert page_response.limit == limit
    assert page_response.start == start
    assert page_response.total_count == total_count
