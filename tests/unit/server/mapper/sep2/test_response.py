import re
from itertools import product
from typing import Optional, Union

import pytest
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from envoy_schema.server.schema.sep2.response import (
    DERControlResponse,
    PriceResponse,
    Response,
    ResponseListResponse,
    ResponseSet,
    ResponseSetList,
)

from envoy.server.mapper.constants import MridType, PricingReadingType, ResponseSetType
from envoy.server.mapper.sep2.mrid import decode_mrid_type
from envoy.server.mapper.sep2.response import (
    ResponseListMapper,
    ResponseMapper,
    ResponseSetMapper,
    href_to_response_set_type,
    response_set_type_to_href,
)
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.response import DynamicOperatingEnvelopeResponse, TariffGeneratedRateResponse
from envoy.server.model.site import Site
from envoy.server.model.tariff import TariffGeneratedRate
from envoy.server.request_scope import BaseRequestScope, DeviceOrAggregatorRequestScope


def test_response_set_type_to_href():
    """Ensure all calls to response_set_type_to_href generate unique values"""
    hrefs = []
    for response_set_type in ResponseSetType:
        href = response_set_type_to_href(response_set_type)
        assert isinstance(href, str)
        assert re.match("[^a-z0-9]", href) is None, "href slug should just be alphanumeric"
        assert href == response_set_type_to_href(response_set_type), "Value should be stable across multiple calls"
        hrefs.append(href)

    assert len(hrefs) > 0
    assert len(hrefs) == len(set(hrefs)), "All values should be unique"


@pytest.mark.parametrize("t", ResponseSetType)
def test_response_set_type_to_href_roundtrip(t: ResponseSetType):
    """Tests that response_set_type_to_href is reversed by href_to_response_set_type"""
    href = response_set_type_to_href(t)
    result = href_to_response_set_type(href)
    assert isinstance(result, ResponseSetType)
    assert result == t


@pytest.mark.parametrize("bad_value", [None, "foo", "/doe", "doe/"])
def test_href_to_response_set_type_bad_values(bad_value: Optional[str]):
    with pytest.raises(ValueError):
        href_to_response_set_type(bad_value)


@pytest.mark.parametrize("href_prefix, optional_is_none", product([None, "/my/href/prefix/"], [True, False]))
def test_ResponseMapper_map_to_price_response(href_prefix: Optional[str], optional_is_none: bool):
    """Sanity checks that we generate valid models and avoid runtime errors"""
    # Arrange
    scope = generate_class_instance(BaseRequestScope, optional_is_none=optional_is_none, href_prefix=href_prefix)
    site = generate_class_instance(Site, seed=101, optional_is_none=optional_is_none)
    response = generate_class_instance(
        TariffGeneratedRateResponse, seed=202, optional_is_none=optional_is_none, site=site, site_id=site.site_id
    )  # Includes the site relationship

    # Act
    result = ResponseMapper.map_to_price_response(scope, response)

    # Assert
    assert isinstance(result, PriceResponse)
    if href_prefix is not None:
        assert result.href.startswith(href_prefix)
    assert result.endDeviceLFDI == site.lfdi
    assert result.status == response.response_type
    assert isinstance(result.subject, str)
    assert len(result.subject) == 32, "Expected 128 bits of hex chars"


@pytest.mark.parametrize("optional_is_none, response_type", product([True, False], [Response, DERControlResponse]))
def test_ResponseMapper_map_from_price_request(optional_is_none: bool, response_type: type[Response]):
    price_response = generate_class_instance(response_type, seed=101, optional_is_none=optional_is_none)
    tariff_generated_rate = generate_class_instance(TariffGeneratedRate, seed=202, optional_is_none=optional_is_none)
    for prt in PricingReadingType:
        result = ResponseMapper.map_from_price_request(price_response, tariff_generated_rate, prt)
        assert isinstance(result, TariffGeneratedRateResponse)
        assert result.tariff_generated_rate_response_id is None, "Assigned by the database"
        assert result.created_time is None, "Assigned by the database"
        assert result.site_id == tariff_generated_rate.site_id
        assert result.tariff_generated_rate_id_snapshot == tariff_generated_rate.tariff_generated_rate_id
        assert result.pricing_reading_type == prt


@pytest.mark.parametrize("href_prefix, optional_is_none", product([None, "/my/href/prefix/"], [True, False]))
def test_ResponseMapper_map_to_doe_response(href_prefix: Optional[str], optional_is_none: bool):
    """Sanity checks that we generate valid models and avoid runtime errors"""
    # Arrange
    scope = generate_class_instance(BaseRequestScope, optional_is_none=optional_is_none, href_prefix=href_prefix)
    site = generate_class_instance(Site, seed=101, optional_is_none=optional_is_none)
    response = generate_class_instance(
        DynamicOperatingEnvelopeResponse, seed=202, optional_is_none=optional_is_none, site=site, site_id=site.site_id
    )  # Includes the site relationship

    # Act
    result = ResponseMapper.map_to_doe_response(scope, response)

    # Assert
    assert isinstance(result, DERControlResponse)
    if href_prefix is not None:
        assert result.href.startswith(href_prefix)
    assert result.endDeviceLFDI == site.lfdi
    assert result.status == response.response_type
    assert isinstance(result.subject, str)
    assert len(result.subject) == 32, "Expected 128 bits of hex chars"


@pytest.mark.parametrize(
    "doe_type, optional_is_none, response_type",
    product([DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope], [True, False], [Response, DERControlResponse]),
)
def test_ResponseMapper_map_from_doe_request(
    doe_type: Union[type[DynamicOperatingEnvelope], type[ArchiveDynamicOperatingEnvelope]],
    optional_is_none: bool,
    response_type: type[Response],
):
    response = generate_class_instance(response_type, seed=101, optional_is_none=optional_is_none)
    doe = generate_class_instance(doe_type, seed=202, optional_is_none=optional_is_none)

    result = ResponseMapper.map_from_doe_request(response, doe)
    assert isinstance(result, DynamicOperatingEnvelopeResponse)
    assert result.dynamic_operating_envelope_response_id is None, "Assigned by the database"
    assert result.created_time is None, "Assigned by the database"
    assert result.site_id == doe.site_id
    assert result.dynamic_operating_envelope_id_snapshot == doe.dynamic_operating_envelope_id


@pytest.mark.parametrize(
    "href_prefix, optional_is_none, response_set_type",
    product([None, "/prefix"], [True, False], ResponseSetType),
)
def test_ResponseListMapper_response_list_href(
    href_prefix: Optional[str], optional_is_none: bool, response_set_type: ResponseSetType
):
    """Quick sanity check to make sure there isn't obvious runtime exception when generating various list hrefs"""
    scope = generate_class_instance(
        BaseRequestScope,
        seed=1001,
        optional_is_none=optional_is_none,
        href_prefix=href_prefix,
    )
    display_site_id = 9988776655
    href = ResponseListMapper.response_list_href(scope, display_site_id, response_set_type)
    assert isinstance(href, str)
    if href_prefix is not None:
        href.startswith(href_prefix)
    assert str(display_site_id) in href


@pytest.mark.parametrize(
    "href_prefix, optional_is_none, response_count", product([None, "/my/href/prefix/"], [True, False], [0, 2])
)
def test_ResponseListMapper_map_to_price_response(
    href_prefix: Optional[str], optional_is_none: bool, response_count: int
):
    """Attempts to trip up the list mappers with a runtime error for various input combinations"""

    # Arrange
    display_site_id = 87618732141
    scope = generate_class_instance(
        DeviceOrAggregatorRequestScope,
        optional_is_none=optional_is_none,
        href_prefix=href_prefix,
        display_site_id=display_site_id,
    )
    site = generate_class_instance(Site, optional_is_none=optional_is_none)
    responses: list[TariffGeneratedRateResponse] = [
        generate_class_instance(
            TariffGeneratedRateResponse, seed=101 * (i + 1), optional_is_none=optional_is_none, site=site
        )
        for i in range(response_count)
    ]
    total_responses = 15125

    # Act
    result = ResponseListMapper.map_to_price_response(scope, responses, total_responses)

    # Assert
    assert isinstance(result, ResponseListResponse)
    assert_list_type(PriceResponse, result.Response_, count=response_count)
    assert result.all_ == total_responses
    assert result.results == response_count
    if href_prefix is not None:
        assert result.href.startswith(href_prefix)
    assert str(display_site_id) in result.href

    # Check the child mrids
    child_mrids = [e.subject for e in result.Response_]
    assert all([len(mrid) == 32 for mrid in child_mrids])
    assert all([decode_mrid_type(mrid) == MridType.TIME_TARIFF_INTERVAL for mrid in child_mrids])
    assert len(child_mrids) == len(set(child_mrids)), "Each MRID should be unique"


@pytest.mark.parametrize(
    "href_prefix, optional_is_none, response_count", product([None, "/my/href/prefix/"], [True, False], [0, 2])
)
def test_ResponseListMapper_map_to_doe_response(
    href_prefix: Optional[str], optional_is_none: bool, response_count: int
):
    """Attempts to trip up the list mappers with a runtime error for various input combinations"""
    # Arrange
    display_site_id = 87618732555
    scope = generate_class_instance(
        DeviceOrAggregatorRequestScope,
        optional_is_none=optional_is_none,
        href_prefix=href_prefix,
        display_site_id=display_site_id,
    )
    site = generate_class_instance(Site, optional_is_none=optional_is_none)
    responses: list[DynamicOperatingEnvelopeResponse] = [
        generate_class_instance(
            DynamicOperatingEnvelopeResponse, seed=101 * (i + 1), optional_is_none=optional_is_none, site=site
        )
        for i in range(response_count)
    ]
    total_responses = 151266

    # Act
    result = ResponseListMapper.map_to_doe_response(scope, responses, total_responses)

    # Assert
    assert isinstance(result, ResponseListResponse)
    assert_list_type(DERControlResponse, result.Response_, count=response_count)
    assert result.all_ == total_responses
    assert result.results == response_count
    if href_prefix is not None:
        assert result.href.startswith(href_prefix)
    assert str(display_site_id) in result.href

    # Check the child mrids
    child_mrids = [e.subject for e in result.Response_]
    assert all([len(mrid) == 32 for mrid in child_mrids])
    assert all([decode_mrid_type(mrid) == MridType.DYNAMIC_OPERATING_ENVELOPE for mrid in child_mrids])
    assert len(child_mrids) == len(set(child_mrids)), "Each MRID should be unique"


@pytest.mark.parametrize("href_prefix, optional_is_none", product([None, "/my/href/prefix/"], [True, False]))
def test_ResponseSetMapper_map_to_set_response(href_prefix: Optional[str], optional_is_none: bool):
    """Checks that sets are created with unique mrids/hrefs"""
    display_site_id = 87618432555
    scope = generate_class_instance(
        DeviceOrAggregatorRequestScope,
        optional_is_none=optional_is_none,
        href_prefix=href_prefix,
        display_site_id=display_site_id,
    )

    all_hrefs: list[str] = []
    all_mrids: list[str] = []
    for response_set_type in ResponseSetType:
        result = ResponseSetMapper.map_to_set_response(scope, response_set_type)
        assert isinstance(result, ResponseSet)

        assert decode_mrid_type(result.mRID) == MridType.RESPONSE_SET
        all_mrids.append(result.mRID)

        assert result.href != result.ResponseListLink.href
        assert str(display_site_id) in result.href
        assert str(display_site_id) in result.ResponseListLink.href
        all_hrefs.append(result.href)
        all_hrefs.append(result.ResponseListLink.href)

        if href_prefix is not None:
            assert result.href.startswith(href_prefix)
            assert result.ResponseListLink.href.startswith(href_prefix)

    assert len(all_hrefs) == len(set(all_hrefs)), "All hrefs should be unique"
    assert len(all_mrids) == len(set(all_mrids)), "All mrids should be unique"


@pytest.mark.parametrize(
    "href_prefix, optional_is_none, set_count", product([None, "/my/href/prefix/"], [True, False], [0, 2])
)
def test_ResponseSetMapper_map_to_list_response(href_prefix: Optional[str], optional_is_none: bool, set_count: int):
    """Checks that set lists don't generate runtime errors"""
    display_site_id = 87618732555
    scope = generate_class_instance(
        DeviceOrAggregatorRequestScope,
        optional_is_none=optional_is_none,
        href_prefix=href_prefix,
        display_site_id=display_site_id,
    )
    response_sets: list[ResponseSet] = [
        generate_class_instance(ResponseSet, seed=101 * (i + 1), optional_is_none=optional_is_none)
        for i in range(set_count)
    ]
    total_sets = 151266

    result = ResponseSetMapper.map_to_list_response(scope, response_sets, total_sets)
    assert isinstance(result, ResponseSetList)
    assert_list_type(ResponseSet, result.ResponseSet_, count=set_count)

    assert str(display_site_id) in result.href
    assert result.all_ == total_sets
    assert result.results == set_count

    if href_prefix is not None:
        assert result.href.startswith(href_prefix)
