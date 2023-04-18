import urllib.parse
from datetime import datetime
from http import HTTPStatus
from typing import Optional

import pytest
from httpx import AsyncClient

from envoy.server.mapper.sep2.pricing import PricingReadingType
from envoy.server.schema.sep2.metering import ReadingType
from envoy.server.schema.sep2.pricing import (
    RateComponentListResponse,
    RateComponentResponse,
    TariffProfileListResponse,
    TariffProfileResponse,
    TimeTariffIntervalListResponse,
)
from tests.assert_time import assert_datetime_equal, assert_nowish
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_PEM as AGG_1_VALID_PEM
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_PEM as AGG_2_VALID_PEM
from tests.data.certificates.certificate5 import TEST_CERTIFICATE_PEM as AGG_3_VALID_PEM
from tests.data.fake.generator import generate_class_instance
from tests.integration.integration_server import cert_pem_header
from tests.integration.request import build_paging_params
from tests.integration.response import (
    assert_error_response,
    assert_response_header,
    read_location_header,
    read_response_body_string,
)


@pytest.fixture
def agg_1_headers():
    return {cert_pem_header: urllib.parse.quote(AGG_1_VALID_PEM)}


@pytest.fixture
def uri_pricing_type_format():
    return "/pricing/rt/{pricing_type}"


@pytest.fixture
def uri_tariff_profile_list():
    return "/tp"


@pytest.fixture
def uri_tariff_profile_format():
    return "/tp/{tariff_id}"


@pytest.fixture
def uri_rate_component_list_no_site_format():
    return "/tp/{tariff_id}/rc"


@pytest.fixture
def uri_rate_component_list_format():
    return "/tp/{tariff_id}/{site_id}/rc"


@pytest.fixture
def uri_rate_component_format():
    return "/tp/{tariff_id}/{site_id}/rc/{rate_component_id}/{pricing_reading}"


@pytest.fixture
def uri_tti_list_format():
    return "/tp/{tariff_id}/{site_id}/rc/{rate_component_id}/{pricing_reading}/tti"


@pytest.mark.anyio
@pytest.mark.parametrize("price_reading_type", PricingReadingType)
async def test_get_pricingreadingtype(client: AsyncClient, uri_pricing_type_format: str,
                                      price_reading_type: PricingReadingType, agg_1_headers):
    """Checks we get a valid pricing reading type for each enum value."""
    response = await client.get(uri_pricing_type_format.format(pricing_type=price_reading_type.value), headers=agg_1_headers)
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    # The unit tests will do the heavy lifting - this is just a sanity check
    parsed_response: ReadingType = ReadingType.from_xml(body)
    assert parsed_response.commodity
    assert parsed_response.flowDirection


@pytest.mark.anyio
@pytest.mark.parametrize("start,limit,changed_after,expected_tariffs", [
    (None, None, None, ["/tp/3"]),
    (0, 99, None, ["/tp/3", "/tp/2", "/tp/1"]),
    (0, 99, datetime(2023, 1, 2, 12, 1, 2), ["/tp/3", "/tp/2"]),
    (1, 1, None, ["/tp/2"]),
])
async def test_get_tariffprofilelist(client: AsyncClient, uri_tariff_profile_list: str, agg_1_headers,
                                     start: Optional[int], limit: Optional[int], changed_after: Optional[datetime],
                                     expected_tariffs: list[str]):
    """Tests that the list pagination works correctly"""
    response = await client.get(uri_tariff_profile_list + build_paging_params(start, limit, changed_after), headers=agg_1_headers)
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: TariffProfileListResponse = TariffProfileListResponse.from_xml(body)
    assert parsed_response.results == len(expected_tariffs)
    assert len(parsed_response.TariffProfile) == len(expected_tariffs)
    assert expected_tariffs == [tp.href for tp in parsed_response.TariffProfile]


@pytest.mark.anyio
@pytest.mark.parametrize("tariff_id,expected_href", [
    (1, "/tp/1"),
    (2, "/tp/2"),
    (3, "/tp/3"),
    (4, None),
])
async def test_get_tariffprofile(client: AsyncClient, uri_tariff_profile_format: str, agg_1_headers,
                                 tariff_id: int, expected_href: Optional[str]):
    """Tests that the list pagination works correctly"""
    response = await client.get(uri_tariff_profile_format.format(tariff_id=tariff_id), headers=agg_1_headers)
    if expected_href is None:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0

        parsed_response: TariffProfileResponse = TariffProfileResponse.from_xml(body)
        assert parsed_response.href == expected_href
        assert parsed_response.currency


@pytest.mark.anyio
async def test_get_ratecomponentlist_nositescope(client: AsyncClient, uri_rate_component_list_no_site_format: str,
                                                 agg_1_headers):
    """The underlying implementation is a placeholder - this test will just make sure it doesn't crash out"""
    response = await client.get(uri_rate_component_list_no_site_format.format(tariff_id=1), headers=agg_1_headers)
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    # should always be an empty list - there is no site scoping for us to lookup generated rates
    parsed_response: RateComponentListResponse = RateComponentListResponse.from_xml(body)
    assert parsed_response.results == 0
    assert parsed_response.all_ == 0
    assert parsed_response.RateComponent is None or len(parsed_response.RateComponent) == 0


@pytest.mark.anyio
@pytest.mark.parametrize("tariff_id, site_id, start, limit, changed_after, expected_rates", [
    (1, 1, None, 5, None, ["/tp/1/1/rc/2022-03-05/1", "/tp/1/1/rc/2022-03-05/2", "/tp/1/1/rc/2022-03-05/3", "/tp/1/1/rc/2022-03-05/4", "/tp/1/1/rc/2022-03-06/1"]),
    (1, 1, 3, 5, None, ["/tp/1/1/rc/2022-03-05/4", "/tp/1/1/rc/2022-03-06/1", "/tp/1/1/rc/2022-03-06/2", "/tp/1/1/rc/2022-03-06/3", "/tp/1/1/rc/2022-03-06/4"]),
    (1, 1, 4, 5, None, ["/tp/1/1/rc/2022-03-06/1", "/tp/1/1/rc/2022-03-06/2", "/tp/1/1/rc/2022-03-06/3", "/tp/1/1/rc/2022-03-06/4"]),
    (1, 1, 5, 5, None, ["/tp/1/1/rc/2022-03-06/2", "/tp/1/1/rc/2022-03-06/3", "/tp/1/1/rc/2022-03-06/4"]),
    (2, 1, None, None, None, []),
    (1, 2, None, None, None, ["/tp/1/2/rc/2022-03-05/1"]),
    (1, 2, None, 5, None, ["/tp/1/2/rc/2022-03-05/1", "/tp/1/2/rc/2022-03-05/2", "/tp/1/2/rc/2022-03-05/3", "/tp/1/2/rc/2022-03-05/4"]),
])
async def test_get_ratecomponentlist(client: AsyncClient, uri_rate_component_list_format: str, agg_1_headers,
                                     tariff_id: int, site_id: int, start: Optional[int], limit: Optional[int],
                                     changed_after: Optional[datetime], expected_rates: list[str]):
    """Validates the complicated virtual mapping of RateComponents"""
    path = uri_rate_component_list_format.format(tariff_id=tariff_id, site_id=site_id)
    query = build_paging_params(start=start, limit=limit, changed_after=changed_after)
    response = await client.get(path + query, headers=agg_1_headers)
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    # should always be an empty list - there is no site scoping for us to lookup generated rates
    parsed_response: RateComponentListResponse = RateComponentListResponse.from_xml(body)
    assert parsed_response.results == len(expected_rates)

    if len(expected_rates) == 0:
        assert parsed_response.RateComponent is None or len(parsed_response.RateComponent) == len(expected_rates)
    else:
        assert len(parsed_response.RateComponent) == len(expected_rates)
        assert expected_rates == [tp.href for tp in parsed_response.RateComponent]


@pytest.mark.anyio
@pytest.mark.parametrize("tariff_id, site_id, rc_id, pricing_reading, expected_href, expected_ttis", [
    (1, 1, "2022-03-05", 1, "/tp/1/1/rc/2022-03-05/1", 2),
    (1, 1, "2022-03-05", 2, "/tp/1/1/rc/2022-03-05/2", 2),
    (1, 1, "2022-03-06", 3, "/tp/1/1/rc/2022-03-06/3", 1),
    (1, 3, "2022-03-06", 3, "/tp/1/3/rc/2022-03-06/3", 0),
    (1, 3, "2022-03-05", 1, "/tp/1/3/rc/2022-03-05/1", 0),
    (3, 1, "2022-03-05", 1, "/tp/3/1/rc/2022-03-05/1", 0),
])
async def test_get_ratecomponent(client: AsyncClient, uri_rate_component_format: str, agg_1_headers,
                                 tariff_id: int, site_id: int, rc_id: str, pricing_reading: int,
                                 expected_href: Optional[str], expected_ttis: int):
    """Tests that single rate component lookups ALWAYS return (they are virtual of course). The way we
    check whether it's working or not is by inspecting the count of TimeTariffIntervals (tti) underneath
    the RateComponent"""
    uri = uri_rate_component_format.format(tariff_id=tariff_id, site_id=site_id, rate_component_id=rc_id, pricing_reading=pricing_reading)
    response = await client.get(uri, headers=agg_1_headers)

    # always responds - doesn't always have links to TTIs
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: RateComponentResponse = RateComponentResponse.from_xml(body)
    assert parsed_response.href == expected_href
    assert parsed_response.mRID
    assert parsed_response.ReadingTypeLink
    assert parsed_response.ReadingTypeLink.href
    assert parsed_response.TimeTariffIntervalListLink
    assert parsed_response.TimeTariffIntervalListLink.all_ == expected_ttis


@pytest.mark.anyio
@pytest.mark.parametrize("tariff_id, site_id, rc_id, pricing_reading, start, limit, changed_after, expected_ttis", [
    (1, 1, "2022-03-05", 1, None, 5, None, ["/tp/1/1/rc/2022-03-05/1/tti/01:02", "/tp/1/1/rc/2022-03-05/1/tti/03:04"]),
    (1, 1, "2022-03-06", 3, None, 5, None, ["/tp/1/1/rc/2022-03-06/3/tti/01:02"]),
    (1, 1, "2022-03-07", 1, None, 5, None, []),
    (1, 1, "2022-03-05", 2, None, None, None, ["/tp/1/1/rc/2022-03-05/2/tti/01:02"]),
    (1, 1, "2022-03-05", 1, 1, 5, None, ["/tp/1/1/rc/2022-03-05/1/tti/03:04"]),
    (1, 1, "2022-03-05", 1, 2, 5, None, []),
    (1, 2, "2022-03-05", 1, None, 99, None, ["/tp/1/2/rc/2022-03-05/1/tti/01:02"]),
])
async def test_get_timetariffintervallist(client: AsyncClient, uri_tti_list_format: str, agg_1_headers,
                                          tariff_id: int, site_id: int, rc_id: str, pricing_reading: int,
                                          start: Optional[int], limit: Optional[int], changed_after: Optional[datetime],
                                          expected_ttis: list[str]):
    """Tests time tariff interval paging"""
    path = uri_tti_list_format.format(tariff_id=tariff_id, site_id=site_id, rate_component_id=rc_id, pricing_reading=pricing_reading)
    query = build_paging_params(start=start, limit=limit, changed_after=changed_after)
    response = await client.get(path + query, headers=agg_1_headers)
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    # should always be an empty list - there is no site scoping for us to lookup generated rates
    parsed_response: TimeTariffIntervalListResponse = TimeTariffIntervalListResponse.from_xml(body)
    assert parsed_response.results == len(expected_ttis)

    if len(expected_ttis) == 0:
        assert parsed_response.TimeTariffInterval is None or len(parsed_response.TimeTariffInterval) == len(expected_ttis)
    else:
        assert len(parsed_response.TimeTariffInterval) == len(expected_ttis)
        assert expected_ttis == [tp.href for tp in parsed_response.TimeTariffInterval]

