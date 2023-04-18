import urllib.parse
from datetime import datetime
from http import HTTPStatus
from typing import Optional

import pytest
from httpx import AsyncClient

from envoy.server.mapper.sep2.pricing import PricingReadingType
from envoy.server.schema.sep2.metering import ReadingType
from envoy.server.schema.sep2.pricing import TariffProfileListResponse, TariffProfileResponse
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
    if expected_href == None:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0

        parsed_response: TariffProfileResponse = TariffProfileResponse.from_xml(body)
        assert parsed_response.href == expected_href
        assert parsed_response.currency

