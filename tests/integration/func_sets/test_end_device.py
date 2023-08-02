import urllib.parse
from datetime import datetime, timezone
from http import HTTPStatus

import pytest
from envoy_schema.server.schema.sep2.end_device import EndDeviceListResponse, EndDeviceRequest, EndDeviceResponse
from envoy_schema.server.schema.sep2.types import DeviceCategory
from httpx import AsyncClient

from tests.assert_time import assert_nowish
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as AGG_1_VALID_CERT
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_FINGERPRINT as AGG_2_VALID_CERT
from tests.data.certificates.certificate5 import TEST_CERTIFICATE_FINGERPRINT as AGG_3_VALID_CERT
from tests.data.fake.generator import generate_class_instance
from tests.integration.integration_server import cert_header
from tests.integration.request import build_paging_params
from tests.integration.response import (
    assert_error_response,
    assert_response_header,
    read_location_header,
    read_response_body_string,
)


@pytest.fixture
def edev_base_uri():
    return "/edev"


@pytest.fixture
def edev_fetch_uri_format():
    return "/edev/{site_id}"


@pytest.mark.parametrize(
    "site_sfdis,cert",
    [([4444, 2222, 1111], AGG_1_VALID_CERT), ([3333], AGG_2_VALID_CERT), ([], AGG_3_VALID_CERT)],
)
@pytest.mark.anyio
async def test_get_end_device_list_by_aggregator(
    client: AsyncClient, edev_base_uri: str, site_sfdis: list[int], cert: str
):
    """Simple test of a valid get for different aggregator certs - validates that the response looks like XML
    and that it contains the expected end device SFDI's associated with each aggregator"""
    response = await client.get(
        edev_base_uri + build_paging_params(limit=100), headers={cert_header: urllib.parse.quote(cert)}
    )
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: EndDeviceListResponse = EndDeviceListResponse.from_xml(body)
    assert parsed_response.all_ == len(site_sfdis), f"received body:\n{body}"
    assert parsed_response.results == len(site_sfdis), f"received body:\n{body}"

    if len(site_sfdis) > 0:
        assert parsed_response.EndDevice, f"received body:\n{body}"
        assert len(parsed_response.EndDevice) == len(site_sfdis), f"received body:\n{body}"
        assert [ed.sFDI for ed in parsed_response.EndDevice] == site_sfdis


@pytest.mark.parametrize(
    "query_string, site_sfdis, expected_total, cert",
    [
        (build_paging_params(limit=1), [4444], 3, AGG_1_VALID_CERT),
        (build_paging_params(limit=2), [4444, 2222], 3, AGG_1_VALID_CERT),
        (build_paging_params(limit=2, start=1), [2222, 1111], 3, AGG_1_VALID_CERT),
        (build_paging_params(limit=1, start=1), [2222], 3, AGG_1_VALID_CERT),
        (build_paging_params(limit=1, start=2), [1111], 3, AGG_1_VALID_CERT),
        (build_paging_params(limit=1, start=3), [], 3, AGG_1_VALID_CERT),
        (build_paging_params(limit=2, start=2), [1111], 3, AGG_1_VALID_CERT),
        # add in timestamp filtering
        # This will filter down to Site 2,3,4
        (
            build_paging_params(limit=5, changed_after=datetime(2022, 2, 3, 5, 0, 0, tzinfo=timezone.utc)),
            [4444, 2222],
            2,
            AGG_1_VALID_CERT,
        ),
        (
            build_paging_params(limit=5, start=1, changed_after=datetime(2022, 2, 3, 5, 0, 0, tzinfo=timezone.utc)),
            [2222],
            2,
            AGG_1_VALID_CERT,
        ),
        (build_paging_params(limit=2, start=1), [], 1, AGG_2_VALID_CERT),
        (build_paging_params(limit=2, start=1), [], 0, AGG_3_VALID_CERT),
        (build_paging_params(), [], 0, AGG_3_VALID_CERT),
    ],
)
@pytest.mark.anyio
async def test_get_end_device_list_pagination(
    client: AsyncClient, edev_base_uri: str, query_string: str, site_sfdis: list[str], expected_total: int, cert: str
):
    """Tests that pagination variables on the list endpoint are respected"""
    response = await client.get(edev_base_uri + query_string, headers={cert_header: urllib.parse.quote(cert)})
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: EndDeviceListResponse = EndDeviceListResponse.from_xml(body)
    assert parsed_response.all_ == expected_total, f"received body:\n{body}"
    assert parsed_response.results == len(site_sfdis), f"received body:\n{body}"

    if len(site_sfdis) > 0:
        assert parsed_response.EndDevice, f"received body:\n{body}"
        assert len(parsed_response.EndDevice) == len(site_sfdis), f"received body:\n{body}"
        assert [ed.sFDI for ed in parsed_response.EndDevice] == site_sfdis


@pytest.mark.anyio
async def test_get_enddevice(client: AsyncClient, edev_fetch_uri_format: str):
    """Tests that fetching named end device's works / fails in simple cases"""

    # check fetching within aggregator
    uri = edev_fetch_uri_format.format(site_id=2)
    response = await client.get(uri, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)})
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: EndDeviceResponse = EndDeviceResponse.from_xml(body)
    assert parsed_response.changedTime == int(datetime(2022, 2, 3, 5, 6, 7, tzinfo=timezone.utc).timestamp())
    assert parsed_response.href == uri
    assert parsed_response.enabled == 1
    assert parsed_response.lFDI == "site2-lfdi"
    assert parsed_response.sFDI == 2222
    assert parsed_response.deviceCategory == "1"

    # check fetching outside aggregator
    uri = edev_fetch_uri_format.format(site_id=3)  # This belongs to agg2
    response = await client.get(uri, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)})
    assert_response_header(response, HTTPStatus.NOT_FOUND)
    assert_error_response(response)

    # check fetching an ID that does not exist
    uri = edev_fetch_uri_format.format(site_id=9999)  # This does not exist
    response = await client.get(uri, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)})
    assert_response_header(response, HTTPStatus.NOT_FOUND)
    assert_error_response(response)


@pytest.mark.anyio
async def test_create_end_device(client: AsyncClient, edev_base_uri: str):
    """When creating an end_device check to see if it persists and is correctly assigned to the aggregator"""

    insert_request: EndDeviceRequest = generate_class_instance(EndDeviceRequest)
    insert_request.postRate = 123
    insert_request.deviceCategory = "{0:x}".format(int(DeviceCategory.HOT_TUB))
    response = await client.post(
        edev_base_uri,
        headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)},
        content=EndDeviceRequest.to_xml(insert_request),
    )
    assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)
    assert len(read_response_body_string(response)) == 0
    inserted_href = read_location_header(response)

    # now lets grab the end device we just created
    response = await client.get(inserted_href, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)})
    assert_response_header(response, HTTPStatus.OK)
    response_body = read_response_body_string(response)
    assert len(response_body) > 0
    parsed_response: EndDeviceResponse = EndDeviceResponse.from_xml(response_body)
    assert_nowish(parsed_response.changedTime)
    assert parsed_response.href == inserted_href
    assert parsed_response.enabled == 1
    assert parsed_response.lFDI == insert_request.lFDI
    assert parsed_response.sFDI == insert_request.sFDI
    assert parsed_response.deviceCategory == insert_request.deviceCategory

    # check that other aggregators can't fetch it
    response = await client.get(inserted_href, headers={cert_header: urllib.parse.quote(AGG_2_VALID_CERT)})
    assert_response_header(response, HTTPStatus.NOT_FOUND)
    assert_error_response(response)

    # check the new end_device count for aggregator 1
    response = await client.get(
        edev_base_uri + build_paging_params(limit=100), headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)}
    )
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: EndDeviceListResponse = EndDeviceListResponse.from_xml(body)
    assert parsed_response.all_ == 4, f"received body:\n{body}"


@pytest.mark.anyio
async def test_update_end_device(client: AsyncClient, edev_base_uri: str):
    """Test that an aggregator can update its own end_device but another aggregator cannot"""

    # Fire off an update that will succeed
    updated_device_category = "{0:x}".format(int(DeviceCategory.INTERIOR_LIGHTING))
    update_request: EndDeviceRequest = generate_class_instance(EndDeviceRequest)
    update_request.lFDI = "site1-lfdi"
    update_request.sFDI = 1111
    update_request.deviceCategory = updated_device_category  # update device category
    response = await client.post(
        edev_base_uri,
        headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)},
        content=EndDeviceRequest.to_xml(update_request),
    )
    assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)
    assert len(read_response_body_string(response)) == 0
    inserted_href = read_location_header(response)
    assert inserted_href.endswith("/1"), "Updating site 1"

    # now lets grab the end device we just updated
    response = await client.get(inserted_href, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)})
    assert_response_header(response, HTTPStatus.OK)
    response_body = read_response_body_string(response)
    assert len(response_body) > 0
    parsed_response: EndDeviceResponse = EndDeviceResponse.from_xml(response_body)
    assert_nowish(parsed_response.changedTime)
    assert parsed_response.href == inserted_href
    assert parsed_response.enabled == 1
    assert parsed_response.lFDI == update_request.lFDI
    assert parsed_response.sFDI == update_request.sFDI
    assert parsed_response.deviceCategory == updated_device_category

    # now fire off a similar request that's with the wrong aggregator
    update_request.deviceCategory = "{0:x}".format(
        int(DeviceCategory.COMBINED_HEAT_AND_POWER)
    )  # update device category
    response = await client.post(
        edev_base_uri,
        headers={cert_header: urllib.parse.quote(AGG_2_VALID_CERT)},
        content=EndDeviceRequest.to_xml(update_request),
    )
    assert_response_header(response, HTTPStatus.CONFLICT)  # conflict because the LFDI isn't unique to this agg
    assert_error_response(response)

    # double check the deviceCategory is left alone
    response = await client.get(inserted_href, headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)})
    assert_response_header(response, HTTPStatus.OK)
    response_body = read_response_body_string(response)
    assert len(response_body) > 0
    parsed_response: EndDeviceResponse = EndDeviceResponse.from_xml(response_body)
    assert abs(parsed_response.changedTime - int(datetime.now().timestamp())) < 20, "Expected changedTime to be nowish"
    assert parsed_response.href == inserted_href
    assert parsed_response.enabled == 1
    assert parsed_response.lFDI == update_request.lFDI
    assert parsed_response.sFDI == update_request.sFDI
    assert parsed_response.deviceCategory == updated_device_category

    # check the new end_device count for aggregator 1
    response = await client.get(
        edev_base_uri + build_paging_params(limit=100), headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)}
    )
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: EndDeviceListResponse = EndDeviceListResponse.from_xml(body)
    assert parsed_response.all_ == 3, f"received body:\n{body}"


@pytest.mark.anyio
async def test_update_end_device_bad_device_category(
    client: AsyncClient, edev_base_uri: str, edev_fetch_uri_format: str
):
    """Test that specifying a bad DeviceCategory returns a HTTP BadRequest"""

    # Fire off an update that will bad request due to a bad device
    update_request: EndDeviceRequest = generate_class_instance(EndDeviceRequest)
    update_request.lFDI = "site1-lfdi"
    update_request.sFDI = 1111
    update_request.deviceCategory = "efffffff"  # bad value
    response = await client.post(
        edev_base_uri,
        headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)},
        content=EndDeviceRequest.to_xml(update_request),
    )
    assert_response_header(response, HTTPStatus.BAD_REQUEST, expected_content_type=None)
    assert_error_response(response)

    # double check the deviceCategory is left alone
    response = await client.get(
        edev_fetch_uri_format.format(site_id=1), headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)}
    )
    assert_response_header(response, HTTPStatus.OK)
    response_body = read_response_body_string(response)
    assert len(response_body) > 0
    parsed_response: EndDeviceResponse = EndDeviceResponse.from_xml(response_body)
    assert parsed_response.deviceCategory == "0"  # Default value from the DB base config
