import urllib.parse
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Optional
from zoneinfo import ZoneInfo

import pytest
from assertical.asserts.type import assert_list_type
from envoy_schema.server.schema import uri
from envoy_schema.server.schema.sep2.metering import ReadingType
from envoy_schema.server.schema.sep2.pricing import (
    ConsumptionTariffIntervalListResponse,
    ConsumptionTariffIntervalResponse,
    RateComponentListResponse,
    RateComponentResponse,
    TariffProfileListResponse,
    TariffProfileResponse,
    TimeTariffIntervalListResponse,
    TimeTariffIntervalResponse,
)
from freezegun import freeze_time
from httpx import AsyncClient

from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as AGG_1_VALID_CERT
from tests.integration.integration_server import cert_header
from tests.integration.request import build_paging_params
from tests.integration.response import assert_error_response, assert_response_header, read_response_body_string


@pytest.fixture
def agg_1_headers():
    return {cert_header: urllib.parse.quote(AGG_1_VALID_CERT)}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "site_id, fsa_id, start, limit, changed_after, expected_tariffs_with_count",
    [
        # basic pagination
        (1, 1, None, None, None, [("/edev/1/tp/2", 1, 1)]),
        (1, 1, 0, 99, None, [("/edev/1/tp/2", 1, 1), ("/edev/1/tp/1", 3, 4)]),
        (
            1,
            1,
            0,
            99,
            datetime(2023, 1, 2, 12, 1, 2, tzinfo=timezone.utc),
            [("/edev/1/tp/2", 1, 1)],
        ),
        (1, 1, 1, 1, None, [("/edev/1/tp/1", 3, 4)]),
        # changing site id
        (2, 1, 0, 99, None, [("/edev/2/tp/2", 1, 0), ("/edev/2/tp/1", 3, 1)]),
        (3, 1, 0, 99, None, [("/edev/3/tp/2", 1, 0), ("/edev/3/tp/1", 3, 1)]),
        # changing fsa id
        (1, 2, 0, 99, None, [("/edev/1/tp/3", 0, 0)]),
        (1, 3, 0, 99, None, []),
    ],
)
@freeze_time("2010-01-01")  # Prices are time sensitive - set time far enough in the past to ensure all pass
async def test_get_tariffprofilelist(
    client: AsyncClient,
    agg_1_headers,
    site_id: int,
    fsa_id: int,
    start: Optional[int],
    limit: Optional[int],
    changed_after: Optional[datetime],
    expected_tariffs_with_count: list[tuple[str, int]],
):
    """Tests that the list pagination works correctly on the site scoped tariff profile list

    expected_tariffs_with_count: (href, rate_component_count, combined_tti_count)"""
    path = uri.TariffProfileFSAListUri.format(site_id=site_id, fsa_id=fsa_id) + build_paging_params(
        start, limit, changed_after
    )
    response = await client.get(path, headers=agg_1_headers)
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response: TariffProfileListResponse = TariffProfileListResponse.from_xml(body)
    assert parsed_response
    assert parsed_response.href == uri.TariffProfileFSAListUri.format(site_id=site_id, fsa_id=fsa_id)
    assert parsed_response.results == len(expected_tariffs_with_count)

    if parsed_response.TariffProfile is None:
        parsed_response.TariffProfile = []
    assert len(parsed_response.TariffProfile) == len(expected_tariffs_with_count)

    # Check that the rate counts and referenced rate component counts match our expectations
    expected_tariffs = [href for (href, _, _) in expected_tariffs_with_count]
    expected_component_counts = [rate_component_count for (_, rate_component_count, _) in expected_tariffs_with_count]
    expected_ctti_counts = [combined_tti_count for (_, _, combined_tti_count) in expected_tariffs_with_count]
    assert expected_tariffs == [tp.href for tp in parsed_response.TariffProfile]
    assert expected_component_counts == [tp.RateComponentListLink.all_ for tp in parsed_response.TariffProfile]
    assert expected_ctti_counts == [tp.CombinedTimeTariffIntervalListLink.all_ for tp in parsed_response.TariffProfile]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tariff_id, site_id, expected_href, expected_ratecount, expected_tti_count",
    [
        (1, 1, "/edev/1/tp/1", 3, 4),
        (1, 2, "/edev/2/tp/1", 3, 1),
        (1, 4, "/edev/4/tp/1", 3, 0),
        (2, 1, "/edev/1/tp/2", 1, 1),
        (3, 1, "/edev/1/tp/3", 0, 0),
        (1, 3, None, None, None),  # Site 3 is NOT accessible to this Agg 1
        (4, 1, None, None, None),  # Bad tariff ID
        (1, 99, None, None, None),  # Bad site ID
    ],
)
@freeze_time("2010-01-01")  # Prices are time sensitive - set time far enough in the past to ensure all pass
async def test_get_tariffprofile(
    client: AsyncClient,
    agg_1_headers,
    tariff_id: int,
    site_id: int,
    expected_href: Optional[str],
    expected_ratecount: Optional[int],
    expected_tti_count: Optional[int],
):
    """Tests that fetching individual TariffProfiles works and correctly counts descendent lists"""
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
        assert isinstance(parsed_response.pricePowerOfTenMultiplier, int)
        assert parsed_response.RateComponentListLink
        assert parsed_response.RateComponentListLink.all_ == expected_ratecount

        assert parsed_response.CombinedTimeTariffIntervalListLink
        assert parsed_response.CombinedTimeTariffIntervalListLink.all_ == expected_tti_count

        assert parsed_response.CombinedTimeTariffIntervalListLink.href != parsed_response.RateComponentListLink.href


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tariff_id, site_id, start, limit, changed_after, expected_rates_with_count",
    [
        (
            1,
            1,
            None,
            5,
            None,
            [("/edev/1/tp/1/rc/3", 0), ("/edev/1/tp/1/rc/2", 1), ("/edev/1/tp/1/rc/1", 3)],
        ),
        (
            1,
            1,
            1,
            5,
            None,
            [("/edev/1/tp/1/rc/2", 1), ("/edev/1/tp/1/rc/1", 3)],
        ),
        (
            1,
            1,
            2,
            5,
            None,
            [("/edev/1/tp/1/rc/1", 3)],
        ),
        (
            1,
            1,
            0,
            2,
            None,
            [("/edev/1/tp/1/rc/3", 0), ("/edev/1/tp/1/rc/2", 1)],
        ),
        (
            1,
            1,
            None,
            5,
            datetime(2022, 2, 1, 2, 0, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
            [("/edev/1/tp/1/rc/3", 0), ("/edev/1/tp/1/rc/2", 1)],
        ),
        (2, 1, None, 99, None, [("/edev/1/tp/2/rc/4", 1)]),
        (1, 2, None, 99, None, [("/edev/2/tp/1/rc/3", 0), ("/edev/2/tp/1/rc/2", 0), ("/edev/2/tp/1/rc/1", 1)]),
    ],
)
@freeze_time("2010-01-01")  # Prices are time sensitive - set time far enough in the past to ensure all pass
async def test_get_ratecomponentlist(
    client: AsyncClient,
    agg_1_headers,
    tariff_id: int,
    site_id: int,
    start: Optional[int],
    limit: Optional[int],
    changed_after: Optional[datetime],
    expected_rates_with_count: list[tuple[str, int]],
):
    """Validates the complicated virtual mapping of RateComponents"""
    path = uri.RateComponentListUri.format(tariff_id=tariff_id, site_id=site_id)
    query = build_paging_params(start=start, limit=limit, changed_after=changed_after)
    response = await client.get(path + query, headers=agg_1_headers)
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    # should always be an empty list - there is no site scoping for us to lookup generated rates
    parsed_response: RateComponentListResponse = RateComponentListResponse.from_xml(body)
    assert parsed_response.results == len(expected_rates_with_count)

    if len(expected_rates_with_count) == 0:
        assert parsed_response.RateComponent is None or len(parsed_response.RateComponent) == len(
            expected_rates_with_count
        )
    else:
        assert len(parsed_response.RateComponent) == len(expected_rates_with_count)
        assert [href for href, _ in expected_rates_with_count] == [tp.href for tp in parsed_response.RateComponent]
        assert [count for _, count in expected_rates_with_count] == [
            tp.TimeTariffIntervalListLink.all_ for tp in parsed_response.RateComponent
        ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tariff_id, site_id, rc_id, expected_href, expected_tti_count",
    [
        (1, 1, 1, "/edev/1/tp/1/rc/1", 3),
        (1, 1, 2, "/edev/1/tp/1/rc/2", 1),
        (1, 1, 3, "/edev/1/tp/1/rc/3", 0),
        (2, 1, 4, "/edev/1/tp/2/rc/4", 1),
        (1, 2, 1, "/edev/2/tp/1/rc/1", 1),
        (1, 1, 4, None, None),  # RC 4 belongs to TP 2
        (1, 1, 99, None, None),  # RC doesn't exist
        (99, 1, 1, None, None),  # TP doesn't exist
        (1, 99, 1, None, None),  # Site doesn't exist
        (1, 3, 1, None, None),  # Site doesn't belong to agg
    ],
)
@freeze_time("2010-01-01")  # Prices are time sensitive - set time far enough in the past to ensure all pass
async def test_get_ratecomponent(
    client: AsyncClient,
    agg_1_headers,
    tariff_id: int,
    site_id: int,
    rc_id: str,
    expected_href: Optional[str],
    expected_tti_count: Optional[int],
):
    """Tests that single rate component lookups return the expected RateComponent / TTI list counts"""
    path = uri.RateComponentUri.format(tariff_id=tariff_id, site_id=site_id, rate_component_id=rc_id)
    response = await client.get(path, headers=agg_1_headers)

    if expected_href is None or expected_tti_count is None:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0

        parsed_response: RateComponentResponse = RateComponentResponse.from_xml(body)
        assert parsed_response.href == expected_href
        assert parsed_response.mRID
        assert parsed_response.ReadingTypeLink
        assert parsed_response.ReadingTypeLink.href
        assert parsed_response.TimeTariffIntervalListLink
        assert parsed_response.TimeTariffIntervalListLink.all_ == expected_tti_count


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tariff_id, site_id, rc_id, expected_href, expected_uom, expected_pow10, expected_direction",
    [
        (1, 1, 1, "/edev/1/tp/1/rc/1/rt", 38, 3, 1),
        (1, 1, 2, "/edev/1/tp/1/rc/2/rt", 38, None, 19),
        (1, 1, 3, "/edev/1/tp/1/rc/3/rt", None, None, None),
        (1, 1, 4, None, None, None, None),  # RC 4 belongs to TP 2
        (1, 1, 99, None, None, None, None),  # RC doesn't exist
        (99, 1, 1, None, None, None, None),  # TP doesn't exist
        (1, 99, 1, None, None, None, None),  # Site doesn't exist
        (1, 3, 1, None, None, None, None),  # Site doesn't belong to agg
    ],
)
async def test_get_ratecomponent_reading_type(
    client: AsyncClient,
    agg_1_headers,
    tariff_id: int,
    site_id: int,
    rc_id: str,
    expected_href: Optional[str],
    expected_uom: Optional[int],
    expected_pow10: Optional[int],
    expected_direction: Optional[int],
):
    """Tests that rate component ReadingType lookups return the expected data"""
    path = uri.PricingReadingTypeUri.format(tariff_id=tariff_id, site_id=site_id, rate_component_id=rc_id)
    response = await client.get(path, headers=agg_1_headers)

    if expected_href is None:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0

        parsed_response = ReadingType.from_xml(body)
        assert parsed_response.href == expected_href
        assert parsed_response.uom == expected_uom
        assert parsed_response.powerOfTenMultiplier == expected_pow10
        assert parsed_response.flowDirection == expected_direction


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tariff_id, site_id, rc_id, start, limit, changed_after, expected_ttis",
    [
        (
            1,
            1,
            1,
            None,
            5,
            None,
            [
                ("/edev/1/tp/1/rc/1/tti/1", 1111, 1000, 1001),
                ("/edev/1/tp/1/rc/1/tti/2", 2222, None, None),
                ("/edev/1/tp/1/rc/1/tti/3", 3333, 3000, 3001),
            ],
        ),
        (
            1,
            2,
            1,
            None,
            5,
            None,
            [
                ("/edev/2/tp/1/rc/1/tti/4", 4444, None, None),
            ],
        ),
        (
            1,
            1,
            2,
            None,
            5,
            None,
            [
                ("/edev/1/tp/1/rc/2/tti/6", 6666, 6000, 6001),
            ],
        ),
        # Paging
        (
            1,
            1,
            1,
            1,
            5,
            None,
            [
                ("/edev/1/tp/1/rc/1/tti/2", 2222, None, None),
                ("/edev/1/tp/1/rc/1/tti/3", 3333, 3000, 3001),
            ],
        ),
        (
            1,
            1,
            1,
            0,
            2,
            None,
            [
                ("/edev/1/tp/1/rc/1/tti/1", 1111, 1000, 1001),
                ("/edev/1/tp/1/rc/1/tti/2", 2222, None, None),
            ],
        ),
        (
            1,
            1,
            1,
            0,
            99,
            datetime(2022, 3, 4, 12, 22, 33, tzinfo=timezone.utc),  # Will exclude tti/1
            [
                ("/edev/1/tp/1/rc/1/tti/2", 2222, None, None),
                ("/edev/1/tp/1/rc/1/tti/3", 3333, 3000, 3001),
            ],
        ),
        (
            99,
            1,
            1,
            None,
            5,
            None,
            None,
        ),
        (
            1,
            1,
            4,  # RC 4 belongs to TP 1
            None,
            5,
            None,
            None,
        ),
        (
            1,
            99,
            1,
            None,
            5,
            None,
            None,
        ),
        (
            1,
            1,
            99,
            None,
            5,
            None,
            None,
        ),
    ],
)
@freeze_time("2010-01-01")  # Prices are time sensitive - set time far enough in the past to ensure all pass
async def test_get_timetariffintervallist(
    client: AsyncClient,
    agg_1_headers,
    tariff_id: int,
    site_id: int,
    rc_id: str,
    start: Optional[int],
    limit: Optional[int],
    changed_after: Optional[datetime],
    expected_ttis: Optional[list[tuple[str, int, Optional[int], Optional[int]]]],
):
    """Tests time tariff interval paging - validates the encoded URIs and prices

    expected_ttis: (href, price_block_0, block_1_start, price_block_1)"""
    path = uri.TimeTariffIntervalListUri.format(tariff_id=tariff_id, site_id=site_id, rate_component_id=rc_id)
    query = build_paging_params(start=start, limit=limit, changed_after=changed_after)
    response = await client.get(path + query, headers=agg_1_headers)
    if expected_ttis is None:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
        return

    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0

    parsed_response = TimeTariffIntervalListResponse.from_xml(body)
    assert parsed_response.results == len(expected_ttis)

    if len(expected_ttis) == 0:
        assert parsed_response.TimeTariffInterval is None or len(parsed_response.TimeTariffInterval) == len(
            expected_ttis
        )
    else:
        assert parsed_response.TimeTariffInterval
        assert_list_type(TimeTariffIntervalResponse, parsed_response.TimeTariffInterval, count=len(expected_ttis))

        # validate each of the TTI hrefs and that the CTI link encodes the correct price
        for idx, (tti_href, price, block1_start, block1_price), tti in zip(
            range(len(expected_ttis)), expected_ttis, parsed_response.TimeTariffInterval
        ):
            assert tti.href == tti_href, f"[{idx}]: expected href {tti_href} but got {tti.href}"

            expected_price_count = 2 if block1_start is not None and block1_price is not None else 1

            assert tti.ConsumptionTariffIntervalListLink
            assert tti.ConsumptionTariffIntervalListLink.all_ == expected_price_count, tti.href
            assert tti.ConsumptionTariffIntervalListSummary.all_ == expected_price_count, tti.href
            assert tti.ConsumptionTariffIntervalListSummary.results == expected_price_count, tti.href
            assert_list_type(
                ConsumptionTariffIntervalResponse,
                tti.ConsumptionTariffIntervalListSummary.ConsumptionTariffInterval,
                count=expected_price_count,
            )

            assert tti.ConsumptionTariffIntervalListSummary.ConsumptionTariffInterval[0].price == price, tti.href
            assert tti.ConsumptionTariffIntervalListSummary.ConsumptionTariffInterval[0].startValue == 0, tti.href

            if expected_price_count > 1:
                assert (
                    tti.ConsumptionTariffIntervalListSummary.ConsumptionTariffInterval[1].price == block1_price
                ), tti.href
                assert (
                    tti.ConsumptionTariffIntervalListSummary.ConsumptionTariffInterval[1].startValue == block1_start
                ), tti.href


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tariff_id, site_id, rc_id, tti_id, expected_price, expected_block1_start, expected_block1_price",
    [
        (1, 1, 1, 1, 1111, 1000, 1001),
        (1, 1, 1, 2, 2222, None, None),
        (1, 1, 1, 3, 3333, 3000, 3001),
        (1, 1, 2, 6, 6666, 6000, 6001),
        (1, 2, 1, 4, 4444, None, None),
        (99, 1, 1, 1, None, None, None),
        (1, 99, 1, 1, None, None, None),
        (1, 1, 99, 1, None, None, None),
        (1, 1, 1, 99, None, None, None),
        (1, 2, 1, 1, None, None, None),
        (1, 1, 2, 1, None, None, None),
    ],
)
async def test_get_timetariffinterval(
    client: AsyncClient,
    agg_1_headers,
    tariff_id: int,
    site_id: int,
    rc_id: int,
    tti_id: int,
    expected_price: Optional[int],
    expected_block1_start: Optional[int],
    expected_block1_price: Optional[int],
):
    """Tests time tariff interval fetching - validates the encoded URIs and prices"""
    path = uri.TimeTariffIntervalUri.format(
        tariff_id=tariff_id, site_id=site_id, rate_component_id=rc_id, tti_id=tti_id
    )
    response = await client.get(path, headers=agg_1_headers)

    if expected_price is None:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response = TimeTariffIntervalResponse.from_xml(body)

        if expected_block1_price is None or expected_block1_start is None:
            expected_block_count = 1
        else:
            expected_block_count = 2
        assert parsed_response.href == path
        assert parsed_response.ConsumptionTariffIntervalListLink.all_ == expected_block_count

        assert parsed_response.ConsumptionTariffIntervalListSummary.all_ == expected_block_count
        assert parsed_response.ConsumptionTariffIntervalListSummary.results == expected_block_count

        assert parsed_response.ConsumptionTariffIntervalListSummary.ConsumptionTariffInterval[0].price == expected_price
        assert parsed_response.ConsumptionTariffIntervalListSummary.ConsumptionTariffInterval[0].startValue == 0
        if expected_block_count > 1:
            assert (
                parsed_response.ConsumptionTariffIntervalListSummary.ConsumptionTariffInterval[1].price
                == expected_block1_price
            )
            assert (
                parsed_response.ConsumptionTariffIntervalListSummary.ConsumptionTariffInterval[1].startValue
                == expected_block1_start
            )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tariff_id, site_id, rc_id, tti_id, expected_price, expected_block1_start, expected_block1_price",
    [
        (1, 1, 1, 1, 1111, 1000, 1001),
        (1, 1, 1, 2, 2222, None, None),
        (1, 1, 1, 3, 3333, 3000, 3001),
        (1, 1, 2, 6, 6666, 6000, 6001),
        (1, 2, 1, 4, 4444, None, None),
        (99, 1, 1, 1, None, None, None),
        (1, 99, 1, 1, None, None, None),
        (1, 1, 99, 1, None, None, None),
        (1, 1, 1, 99, None, None, None),
        (1, 2, 1, 1, None, None, None),
        (1, 1, 2, 1, None, None, None),
    ],
)
async def test_get_cti_list_and_ctis(
    client: AsyncClient,
    agg_1_headers,
    tariff_id: int,
    site_id: int,
    rc_id: int,
    tti_id: int,
    expected_price: Optional[int],
    expected_block1_start: Optional[int],
    expected_block1_price: Optional[int],
):
    """Consumption Tariff Intervals aren't really a list - they're just a wrapper around a single TariffGeneratedRate.

    This test just ensures it behaves like a List AND that the summary elements can resolve"""
    path = (
        uri.ConsumptionTariffIntervalListUri.format(
            tariff_id=tariff_id,
            site_id=site_id,
            rate_component_id=rc_id,
            tti_id=tti_id,
        )
        + "?l=10"
    )
    response = await client.get(path, headers=agg_1_headers)

    if expected_price is None:
        assert_response_header(response, HTTPStatus.NOT_FOUND)
        assert_error_response(response)
    else:
        assert_response_header(response, HTTPStatus.OK)
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response = ConsumptionTariffIntervalListResponse.from_xml(body)

        if expected_block1_price is None or expected_block1_start is None:
            expected_block_count = 1
        else:
            expected_block_count = 2
        assert parsed_response.href == path.split("?")[0]
        assert parsed_response.all_ == expected_block_count
        assert parsed_response.results == expected_block_count

        assert parsed_response.ConsumptionTariffInterval[0].price == expected_price
        assert parsed_response.ConsumptionTariffInterval[0].startValue == 0
        if expected_block_count > 1:
            assert parsed_response.ConsumptionTariffInterval[1].price == expected_block1_price
            assert parsed_response.ConsumptionTariffInterval[1].startValue == expected_block1_start

        # Now resolve the CTI hrefs directly to ensure they match up
        for cti in parsed_response.ConsumptionTariffInterval:
            response = await client.get(cti.href, headers=agg_1_headers)
            assert_response_header(response, HTTPStatus.OK)
            cti_response = ConsumptionTariffIntervalResponse.from_xml(read_response_body_string(response))
            assert cti_response.price == cti.price, cti.href
            assert cti_response.startValue == cti.startValue, cti.href
            assert cti_response.consumptionBlock == cti.consumptionBlock, cti.href
