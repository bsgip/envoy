"""Basic tests that valid no exceptions are being raised"""

from datetime import datetime, timedelta, UTC

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.fake.generator import generate_class_instance
from envoy_schema.admin.schema.pricing import (
    TariffComponentRequest,
    TariffGeneratedRatePageResponse,
    TariffGeneratedRateRequest,
    TariffGeneratedRateResponse,
    TariffRequest,
    TariffResponse,
)
from envoy_schema.server.schema.sep2.types import CurrencyCode

from envoy.admin.mapper.pricing import TariffComponentMapper, TariffGeneratedRateListMapper, TariffMapper
from envoy.server.exception import InvalidMappingError
from envoy.server.model.tariff import Tariff, TariffGeneratedRate


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_tariff_mapper_roundtrip(optional_is_none: bool):
    expected = generate_class_instance(TariffRequest, optional_is_none=optional_is_none)
    changed_time = datetime(2023, 4, 5, 6, 7, 8, 9)
    created_time = datetime(2024, 4, 5, 6, 7, 8, 9)
    mdl = TariffMapper.map_from_request(changed_time, expected)
    mdl.tariff_id = 123321
    mdl.created_time = created_time
    actual = TariffMapper.map_to_response(mdl)

    assert_class_instance_equality(TariffRequest, expected, actual)
    assert actual.changed_time == changed_time
    assert actual.created_time == created_time
    assert actual.tariff_id == 123321


def test_tariff_mapper_from_request():
    req = generate_class_instance(TariffRequest)
    changed_time = datetime(2023, 4, 5, 6, 7, 8, 9)
    mdl = TariffMapper.map_from_request(changed_time, req)

    assert isinstance(mdl, Tariff)
    assert mdl.changed_time == changed_time
    assert mdl.tariff_id == None  # noqa


def test_tariff_mapper_to_response():
    mdl = generate_class_instance(Tariff)
    mdl.currency_code = CurrencyCode.AUSTRALIAN_DOLLAR

    resp = TariffMapper.map_to_response(mdl)

    assert isinstance(resp, TariffResponse)
    assert_class_instance_equality(TariffResponse, mdl, resp)


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_tariff_component_mapper_roundtrip(optional_is_none: bool):
    expected = generate_class_instance(TariffComponentRequest, optional_is_none=optional_is_none)
    changed_time = datetime(2023, 4, 5, 6, 7, 8, 9)
    created_time = datetime(2024, 4, 5, 6, 7, 8, 9)
    mdl = TariffComponentMapper.map_from_request(changed_time, expected)
    mdl.tariff_component_id = 123321
    mdl.created_time = created_time
    actual = TariffComponentMapper.map_to_response(mdl)

    assert_class_instance_equality(TariffComponentRequest, expected, actual)
    assert actual.changed_time == changed_time
    assert actual.created_time == created_time
    assert actual.tariff_component_id == 123321


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_tariff_genrate_mapper_from_request(optional_is_none: bool):
    req = generate_class_instance(TariffGeneratedRateRequest, optional_is_none=optional_is_none)
    changed_time = datetime(2022, 4, 5, 6, 7, 8, 9)
    mdl = TariffGeneratedRateListMapper.map_from_request(
        changed_time, [req], {(req.tariff_component_id + 1): 99, req.tariff_component_id: 1234}
    ).pop()

    assert isinstance(mdl, TariffGeneratedRate)

    assert_class_instance_equality(
        TariffGeneratedRate,
        mdl,
        req,
        ignored_properties={"tariff_generated_rate_id", "tariff_id", "created_time", "changed_time", "end_time"},
    )

    assert mdl.tariff_id == 1234, "Should come via dict lookup"
    assert mdl.end_time == mdl.start_time + timedelta(seconds=mdl.duration_seconds)
    assert mdl.end_time.tzinfo == mdl.start_time.tzinfo

    assert mdl.changed_time == changed_time

    assert mdl.tariff_generated_rate_id == None  # noqa
    assert mdl.created_time == None, "This should be set in the DB"  # noqa


def test_tariff_genrate_mapper_from_request_mismatch_component_id():
    """If the tariff_component_id can't be found in the supplied dict, raise an error"""
    req: TariffGeneratedRateRequest = generate_class_instance(TariffGeneratedRateRequest)
    changed_time = datetime(2022, 4, 5, 6, 7, 8, 9)
    with pytest.raises(InvalidMappingError):
        TariffGeneratedRateListMapper.map_from_request(changed_time, [req], {(req.tariff_component_id + 1): 99, 0: 99})


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_tariff_genrate_mapper_roundtrip(optional_is_none: bool):
    initial = generate_class_instance(TariffGeneratedRateRequest, optional_is_none=optional_is_none)
    changed_time = datetime(2022, 4, 5, 6, 7, 8, 9)
    created_time = datetime(2023, 5, 6, 6, 7, 8, 9)
    tariff_id = 1515152
    tariff_gen_rate_id = 981471

    mdl = TariffGeneratedRateListMapper.map_from_single_rate_request(changed_time, initial, tariff_id)
    mdl.tariff_generated_rate_id = tariff_gen_rate_id  # This would be set by the DB normally
    mdl.created_time = created_time  # This would be set by the DB normally

    result = TariffGeneratedRateListMapper.map_to_single_rate_response(mdl)

    assert_class_instance_equality(
        TariffGeneratedRateRequest,
        initial,
        result,
        ignored_properties={"tariff_id", "tariff_generated_rate_id"},
    )
    assert result.changed_time == changed_time
    assert result.created_time == created_time
    assert result.tariff_id == tariff_id
    assert result.tariff_generated_rate_id == tariff_gen_rate_id


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_tariff_genrate_mapper_to_response(optional_is_none: bool):
    mdl = generate_class_instance(TariffGeneratedRate, optional_is_none=optional_is_none)

    resp = TariffGeneratedRateListMapper.map_to_response(mdl)

    assert isinstance(resp, TariffGeneratedRateResponse)
    assert resp.tariff_generated_rate_id == mdl.tariff_generated_rate_id
    assert resp.tariff_id == mdl.tariff_id
    assert resp.site_id == mdl.site_id
    assert resp.calculation_log_id == mdl.calculation_log_id
    assert resp.start_time == mdl.start_time
    assert resp.duration_seconds == mdl.duration_seconds
    assert resp.import_active_price == mdl.import_active_price
    assert resp.export_active_price == mdl.export_active_price
    assert resp.import_reactive_price == mdl.import_reactive_price
    assert resp.export_reactive_price == mdl.export_reactive_price
    assert resp.created_time == mdl.created_time
    assert resp.changed_time == mdl.changed_time


def test_tariff_genrate_mapper_to_page_response():
    rate1 = generate_class_instance(TariffGeneratedRate, seed=1)
    rate2 = generate_class_instance(TariffGeneratedRate, seed=2)
    period_start = datetime(2022, 1, 1, tzinfo=UTC)
    period_end = datetime(2022, 1, 2, tzinfo=UTC)

    page = TariffGeneratedRateListMapper.map_to_page_response(
        total_count=42,
        rates=[rate1, rate2],
        start=5,
        limit=10,
        period_start=period_start,
        period_end=period_end,
        site_id=7,
    )

    assert isinstance(page, TariffGeneratedRatePageResponse)
    assert page.total_count == 42
    assert page.start == 5
    assert page.limit == 10
    assert page.period_start == period_start
    assert page.period_end == period_end
    assert page.site_id == 7
    assert len(page.rates) == 2
    assert page.rates[0].tariff_generated_rate_id == rate1.tariff_generated_rate_id
    assert page.rates[1].tariff_generated_rate_id == rate2.tariff_generated_rate_id


def test_tariff_genrate_mapper_to_page_response_no_site_filter():
    page = TariffGeneratedRateListMapper.map_to_page_response(
        total_count=0,
        rates=[],
        start=0,
        limit=100,
        period_start=datetime(2022, 1, 1, tzinfo=UTC),
        period_end=datetime(2022, 1, 2, tzinfo=UTC),
        site_id=None,
    )

    assert page.site_id is None
    assert page.rates == []
    assert page.total_count == 0
