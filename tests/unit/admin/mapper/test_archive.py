from datetime import datetime, timezone

from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.time import assert_nowish
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from envoy_schema.admin.schema.archive import (
    ArchivePageResponse,
    ArchiveSiteControlResponse,
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
    assert isinstance(all_mapped, ArchiveSiteControlResponse)
    assert_class_instance_equality(
        ArchiveSiteControlResponse,
        all,
        all_mapped,
        {
            "site_control_id",
            "archive_time",
            "set_connect",
            "import_limit_watts",
            "generation_limit_watts",
            "load_limit_watts",
            "storage_target_watts",
        },
    )
    assert all_mapped.site_control_id == all.dynamic_operating_envelope_id
    assert all_mapped.set_connect == all.set_connected
    assert all_mapped.import_limit_watts == all.import_limit_active_watts
    assert all_mapped.generation_limit_watts == all.generation_limit_active_watts
    assert all_mapped.load_limit_watts == all.load_limit_active_watts
    assert all_mapped.storage_target_watts is None

    optional_mapped = ArchiveMapper.map_to_doe_response(optional)
    assert isinstance(optional_mapped, ArchiveSiteControlResponse)
    assert_class_instance_equality(
        ArchiveSiteControlResponse,
        optional,
        optional_mapped,
        {
            "site_control_id",
            "archive_time",
            "set_connect",
            "import_limit_watts",
            "generation_limit_watts",
            "load_limit_watts",
            "storage_target_watts",
        },
    )  # These should just map 1-1
    assert optional_mapped.site_control_id == optional.dynamic_operating_envelope_id
    assert optional_mapped.set_connect == optional.set_connected
    assert optional_mapped.import_limit_watts == optional.import_limit_active_watts
    assert optional_mapped.generation_limit_watts == optional.generation_limit_active_watts
    assert optional_mapped.load_limit_watts == optional.load_limit_active_watts
    assert optional_mapped.storage_target_watts is None
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
    assert_list_type(ArchiveSiteControlResponse, page_response.entities, len(does))
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
