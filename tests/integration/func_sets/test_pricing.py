import urllib.parse
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Optional

import pytest
from httpx import AsyncClient

from envoy.server.mapper.sep2.pricing import PricingReadingType
from envoy.server.model.tariff import PRICE_DECIMAL_PLACES
from envoy.server.schema import uri
from envoy.server.schema.sep2.metering import ReadingType
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
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_PEM as AGG_1_VALID_PEM
from tests.integration.integration_server import cert_pem_header
from tests.integration.request import build_paging_params
from tests.integration.response import assert_error_response, assert_response_header, read_response_body_string


@pytest.fixture
def agg_1_headers():
    return {cert_pem_header: urllib.parse.quote(AGG_1_VALID_PEM)}


@pytest.mark.anyio
@pytest.mark.parametrize("price_reading_type", PricingReadingType)
async def test_get_pricingreadingtype(client: AsyncClient, price_reading_type: PricingReadingType, agg_1_headers):
    """Checks we get a valid pricing reading type for each enum value."""
    path = uri.PricingReadingTypeUri.format(reading_type=price_reading_type.value)
    response = await client.get(path, headers=agg_1_headers)
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
    (0, 99, datetime(2023, 1, 2, 12, 1, 2, tzinfo=timezone.utc), ["/tp/3", "/tp/2"]),
    (1, 1, None, ["/tp/2"]),
])
async def test_get_tariffprofilelist_nosite(client: AsyncClient, agg_1_headers, start: Optional[int],
                                            limit: Optional[int], changed_after: Optional[datetime],
                                            expected_tariffs: list[str]):
    """Tests that the list pagination works correctly on the unscoped tariff profile list"""
    path = uri.TariffProfileListUnscopedUri + build_paging_params(start, limit, changed_after)
    response = await client.get(path, headers=agg_1_headers)
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: TariffProfileListResponse = TariffProfileListResponse.from_xml(body)
    assert parsed_response.results == len(expected_tariffs)
    assert len(parsed_response.TariffProfile) == len(expected_tariffs)
    assert expected_tariffs == [tp.href for tp in parsed_response.TariffProfile]


@pytest.mark.anyio
@pytest.mark.parametrize("site_id, start, limit, changed_after, expected_tariffs_with_count", [
    # basic pagination
    (1, None, None, None, [("/tp/3/1", 0)]),
    (1, 0, 99, None, [("/tp/3/1", 0), ("/tp/2/1", 0), ("/tp/1/1", 8)]),
    (1, 0, 99, datetime(2023, 1, 2, 12, 1, 2, tzinfo=timezone.utc), [("/tp/3/1", 0), ("/tp/2/1", 0)]),
    (1, 1, 1, None, [("/tp/2/1", 0)]),

    # changing site id
    (2, 0, 99, None, [("/tp/3/2", 0), ("/tp/2/2", 0), ("/tp/1/2", 4)]),
    (3, 0, 99, None, [("/tp/3/3", 0), ("/tp/2/3", 0), ("/tp/1/3", 0)]),  # no access to this site
])
async def test_get_tariffprofilelist(client: AsyncClient, agg_1_headers, site_id: int, start: Optional[int],
                                     limit: Optional[int], changed_after: Optional[datetime],
                                     expected_tariffs_with_count: list[tuple[str, int]]):
    """Tests that the list pagination works correctly on the site scoped tariff profile list"""
    path = uri.TariffProfileListUri.format(site_id=site_id) + build_paging_params(start, limit, changed_after)
    response = await client.get(path, headers=agg_1_headers)
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: TariffProfileListResponse = TariffProfileListResponse.from_xml(body)
    assert parsed_response
    assert parsed_response.results == len(expected_tariffs_with_count)
    assert len(parsed_response.TariffProfile) == len(expected_tariffs_with_count)

    # Check that the rate counts and referenced rate component counts match our expectations
    expected_tariffs = [href for (href, _) in expected_tariffs_with_count]
    expected_rate_counts = [rate_count for (_, rate_count) in expected_tariffs_with_count]
    assert expected_tariffs == [tp.href for tp in parsed_response.TariffProfile]
    assert expected_rate_counts == [tp.RateComponentListLink.all_ for tp in parsed_response.TariffProfile]

@pytest.mark.anyio
@pytest.mark.parametrize("tariff_id,expected_href", [
    (1, "/tp/1"),
    (2, "/tp/2"),
    (3, "/tp/3"),
    (4, None),
])
async def test_get_tariffprofile_nosite(client: AsyncClient, agg_1_headers, tariff_id: int,
                                        expected_href: Optional[str]):
    """Tests that the single entity fetch works correctly"""
    path = uri.TariffProfileUnscopedUri.format(tariff_id=tariff_id)
    response = await client.get(path, headers=agg_1_headers)
    if expected_href is None:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0

        # Sanity check that the response looks like valid XML. Unit test coverage will do the heavy lifting
        # to validate the contents in greater details
        parsed_response: TariffProfileResponse = TariffProfileResponse.from_xml(body)
        assert parsed_response.href == expected_href, "We received the wrong reading type"
        assert parsed_response.currency
        assert parsed_response.pricePowerOfTenMultiplier == PRICE_DECIMAL_PLACES


@pytest.mark.anyio
@pytest.mark.parametrize("tariff_id, site_id, expected_href, expected_ratecount", [
    (1, 1, "/tp/1/1", 8),
    (1, 2, "/tp/1/2", 4),
    (1, 3, "/tp/1/3", 0),
    (1, 4, "/tp/1/4", 0),
    (2, 1, "/tp/2/1", 0),
    (3, 1, "/tp/3/1", 0),
    (4, 1, None, None),
])
async def test_get_tariffprofile(client: AsyncClient, agg_1_headers, tariff_id: int, site_id: int,
                                 expected_href: Optional[str], expected_ratecount: Optional[int]):
    """Tests that the list pagination works correctly"""
    path = uri.TariffProfileUri.format(tariff_id=tariff_id, site_id=site_id)
    response = await client.get(path, headers=agg_1_headers)
    if expected_href is None:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0

        # Sanity check that the response looks like valid XML. Unit test coverage will do the heavy lifting
        # to validate the contents in greater details
        parsed_response: TariffProfileResponse = TariffProfileResponse.from_xml(body)
        assert parsed_response.href == expected_href, "We received the wrong entity id"
        assert parsed_response.currency
        assert parsed_response.pricePowerOfTenMultiplier == PRICE_DECIMAL_PLACES
        assert parsed_response.RateComponentListLink
        assert parsed_response.RateComponentListLink.all_ == expected_ratecount


@pytest.mark.anyio
async def test_get_ratecomponentlist_nositescope(client: AsyncClient, agg_1_headers):
    """The underlying endpoint implementation is just fulfilling the requirements of sep2. It doesnt do anything
    useful and this test will just make sure it doesn't raise on error upon execution"""
    path = uri.RateComponentListUnscopedUri.format(tariff_id=1)
    response = await client.get(path, headers=agg_1_headers)
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
async def test_get_ratecomponentlist(client: AsyncClient, agg_1_headers, tariff_id: int, site_id: int,
                                     start: Optional[int], limit: Optional[int], changed_after: Optional[datetime],
                                     expected_rates: list[str]):
    """Validates the complicated virtual mapping of RateComponents"""
    path = uri.RateComponentListUri.format(tariff_id=tariff_id, site_id=site_id)
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
async def test_get_ratecomponent(client: AsyncClient, agg_1_headers, tariff_id: int, site_id: int, rc_id: str,
                                 pricing_reading: int, expected_href: Optional[str], expected_ttis: int):
    """Tests that single rate component lookups ALWAYS return (they are virtual of course). The way we
    check whether it's working or not is by inspecting the count of TimeTariffIntervals (tti) underneath
    the RateComponent"""
    path = uri.RateComponentUri.format(tariff_id=tariff_id, site_id=site_id, rate_component_id=rc_id,
                                       pricing_reading=pricing_reading)
    response = await client.get(path, headers=agg_1_headers)

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
    (1, 1, "2022-03-05", 1, None, 5, None, [("/tp/1/1/rc/2022-03-05/1/tti/01:02", 11000), ("/tp/1/1/rc/2022-03-05/1/tti/03:04", 21000)]),
    (1, 1, "2022-03-06", 3, None, 5, None, [("/tp/1/1/rc/2022-03-06/3/tti/01:02", 43330)]),
    (1, 1, "2022-03-07", 1, None, 5, None, []),  # bad date
    (1, 1, "2022-03-05", 4, None, None, None, [("/tp/1/1/rc/2022-03-05/4/tti/01:02", -14444)]),
    (1, 1, "2022-03-05", 2, 1, 5, None, [("/tp/1/1/rc/2022-03-05/2/tti/03:04", -22200)]),
    (1, 1, "2022-03-05", 1, 2, 5, None, []),  # page off the end
    (1, 2, "2022-03-05", 1, None, 99, None, [("/tp/1/2/rc/2022-03-05/1/tti/01:02", 31000)]),
])
async def test_get_timetariffintervallist(client: AsyncClient, agg_1_headers, tariff_id: int, site_id: int, rc_id: str,
                                          pricing_reading: int, start: Optional[int], limit: Optional[int],
                                          changed_after: Optional[datetime], expected_ttis: list[tuple[str, int]]):
    """Tests time tariff interval paging - validates the encoded URIs and prices"""
    path = uri.TimeTariffIntervalListUri.format(tariff_id=tariff_id, site_id=site_id, rate_component_id=rc_id,
                                                pricing_reading=pricing_reading)
    query = build_paging_params(start=start, limit=limit, changed_after=changed_after)
    response = await client.get(path + query, headers=agg_1_headers)
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: TimeTariffIntervalListResponse = TimeTariffIntervalListResponse.from_xml(body)
    assert parsed_response.results == len(expected_ttis)

    if len(expected_ttis) == 0:
        assert parsed_response.TimeTariffInterval is None or len(parsed_response.TimeTariffInterval) == len(expected_ttis)
    else:
        assert len(parsed_response.TimeTariffInterval) == len(expected_ttis)

        # validate each of the TTI hrefs and that the CTI link encodes the correct price
        for (idx, (tti_href, price), tti) in zip(range(len(expected_ttis)), expected_ttis, parsed_response.TimeTariffInterval):
            assert tti.href == tti_href, f"[{idx}]: expected href {tti_href} but got {tti.href}"
            assert tti.ConsumptionTariffIntervalListLink
            assert tti.ConsumptionTariffIntervalListLink.href.endswith(f"/{price}"), f"[{idx}] expected CTI href {tti.ConsumptionTariffIntervalListLink.href} to encode price {price}"


@pytest.mark.anyio
@pytest.mark.parametrize("tariff_id, site_id, rc_id, pricing_reading, tti_id, expected_price", [
    (1, 1, "2022-03-05", 1, '01:02', 11000),
    (1, 1, "2022-03-05", 2, '01:02', -12200),
    (1, 2, "2022-03-05", 2, '01:02', -32200),
    (1, 1, "2022-03-06", 3, '01:02', 43330),
    (1, 1, "2022-03-05", 4, '03:04', -24444),

    (1, 1, "2022-03-05", 1, '01:03', None),  # bad time
    (4, 1, "2022-03-05", 1, '01:02', None),  # bad tariff
    (1, 3, "2022-03-05", 1, '01:02', None),  # bad site
    (1, 1, "2022-03-07", 1, '01:02', None),  # bad date
])
async def test_get_timetariffinterval(client: AsyncClient, agg_1_headers, tariff_id: int, site_id: int, rc_id: str,
                                      pricing_reading: int, tti_id: str, expected_price: Optional[int]):
    """Tests time tariff interval paging - validates the encoded URIs and prices"""
    path = uri.TimeTariffIntervalUri.format(tariff_id=tariff_id, site_id=site_id, rate_component_id=rc_id,
                                            pricing_reading=pricing_reading, tti_id=tti_id)
    response = await client.get(path, headers=agg_1_headers)

    if expected_price is None:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response: TimeTariffIntervalResponse = TimeTariffIntervalResponse.from_xml(body)
        assert parsed_response.href == path
        cti_href = parsed_response.ConsumptionTariffIntervalListLink.href
        assert cti_href
        assert cti_href.endswith(f"/{expected_price}"), f"expected CTI href {cti_href} to encode price {expected_price}"


@pytest.mark.anyio
@pytest.mark.parametrize("tariff_id, site_id, rc_id, pricing_reading, tti_id, expected_price", [
    (1, 1, "2022-03-05", 1, '01:02', 11000),
    (1, 1, "2022-03-05", 2, '01:02', -12200),

    (1, 3, "2022-03-05", 2, '01:02', None),  # bad site
])
async def test_get_cti_list(client: AsyncClient, agg_1_headers, tariff_id: int, site_id: int, rc_id: str,
                            pricing_reading: int, tti_id: str, expected_price: Optional[int]):
    """Consumption Tariff Intervals aren't really a list - they're just a wrapper around a single already encoded
    price. This test validates that the prices sent match the prices returned and that the response is always a
    single CTI entity"""
    sent_price = 1 if expected_price is None else expected_price
    path = uri.ConsumptionTariffIntervalListUri.format(tariff_id=tariff_id, site_id=site_id, rate_component_id=rc_id,
                                                       pricing_reading=pricing_reading, tti_id=tti_id,
                                                       sep2_price=sent_price)
    response = await client.get(path, headers=agg_1_headers)

    if expected_price is None:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response: ConsumptionTariffIntervalListResponse = ConsumptionTariffIntervalListResponse.from_xml(body)
        assert parsed_response.all_ == 1
        assert parsed_response.results == 1
        assert len(parsed_response.ConsumptionTariffInterval) == 1
        cti_href = parsed_response.ConsumptionTariffInterval[0].href
        assert cti_href
        assert cti_href.endswith(f"/{expected_price}/1"), f"expected CTI href {cti_href} to have price {expected_price}"


@pytest.mark.anyio
@pytest.mark.parametrize("tariff_id, site_id, rc_id, pricing_reading, tti_id, expected_price", [
    (1, 1, "2022-03-05", 1, '01:02', 11000),
    (1, 1, "2022-03-05", 2, '01:02', -12200),

    (1, 3, "2022-03-05", 2, '01:02', None),  # bad site
])
async def test_get_cti(client: AsyncClient, agg_1_headers, tariff_id: int, site_id: int, rc_id: str,
                       pricing_reading: int, tti_id: str, expected_price: Optional[int]):
    """Consumption Tariff Intervals don't map to anything in the db - they're just a wrapper around a single already
    encoded price. This test validates that the prices sent match the prices returned and that requesting an
    invalid site returns a HTTP 404"""
    sent_price = 1
    if expected_price is not None:
        sent_price = expected_price
    path = uri.ConsumptionTariffIntervalUri.format(tariff_id=tariff_id, site_id=site_id, rate_component_id=rc_id,
                                                   pricing_reading=pricing_reading, tti_id=tti_id,
                                                   sep2_price=sent_price)
    response = await client.get(path, headers=agg_1_headers)

    if expected_price is None:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response: ConsumptionTariffIntervalResponse = ConsumptionTariffIntervalResponse.from_xml(body)
        assert parsed_response.price == expected_price
        cti_href = parsed_response.href
        assert cti_href
        assert cti_href.endswith(f"/{expected_price}/1"), f"expected CTI href {cti_href} to have price {expected_price}"
