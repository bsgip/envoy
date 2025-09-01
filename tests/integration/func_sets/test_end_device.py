import os
import urllib.parse
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Optional

import pytest
from assertical.asserts.time import assert_datetime_equal, assert_nowish
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.server.schema.sep2.end_device import (
    EndDeviceListResponse,
    EndDeviceRequest,
    EndDeviceResponse,
    RegistrationResponse,
)
from envoy_schema.server.schema.sep2.types import DeviceCategory
from httpx import AsyncClient
from sqlalchemy import func, select

from envoy.admin.crud.site import count_all_sites
from envoy.server.model.archive.site import ArchiveSite
from envoy.server.model.site import Site
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as AGG_1_VALID_CERT
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_LFDI as AGG_1_LFDI_FROM_VALID_CERT
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_SFDI as AGG_1_SFDI_FROM_VALID_CERT
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_FINGERPRINT as AGG_2_VALID_CERT
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_SFDI as AGG_2_SFDI_FROM_VALID_CERT
from tests.data.certificates.certificate5 import TEST_CERTIFICATE_FINGERPRINT as AGG_3_VALID_CERT
from tests.data.certificates.certificate5 import TEST_CERTIFICATE_SFDI as AGG_3_SFDI_FROM_VALID_CERT
from tests.data.certificates.certificate6 import TEST_CERTIFICATE_LFDI as OTHER_REGISTERED_CERT_LFDI
from tests.data.certificates.certificate6 import TEST_CERTIFICATE_SFDI as OTHER_REGISTERED_CERT_SFDI
from tests.data.certificates.certificate7 import TEST_CERTIFICATE_LFDI as REGISTERED_CERT_LFDI
from tests.data.certificates.certificate7 import TEST_CERTIFICATE_PEM as REGISTERED_CERT
from tests.data.certificates.certificate7 import TEST_CERTIFICATE_SFDI as REGISTERED_CERT_SFDI
from tests.data.certificates.certificate8 import TEST_CERTIFICATE_LFDI as UNREGISTERED_CERT_LFDI
from tests.data.certificates.certificate8 import TEST_CERTIFICATE_PEM as UNREGISTERED_CERT
from tests.data.certificates.certificate8 import TEST_CERTIFICATE_SFDI as UNREGISTERED_CERT_SFDI
from tests.data.certificates.certificate9 import TEST_CERTIFICATE_LFDI as OTHER_CERT_LFDI
from tests.data.certificates.certificate9 import TEST_CERTIFICATE_SFDI as OTHER_CERT_SFDI
from tests.integration.integration_server import cert_header
from tests.integration.request import build_paging_params
from tests.integration.response import (
    assert_error_response,
    assert_response_header,
    read_location_header,
    read_response_body_string,
)

HREF_PREFIX = "/href/prefix/"


@pytest.fixture
def edev_base_uri():
    return "/edev"


@pytest.fixture
def edev_fetch_uri_format():
    return "/edev/{site_id}"


@pytest.fixture
def edev_registration_fetch_uri_format():
    return "/edev/{site_id}/rg"


@pytest.mark.parametrize(
    "site_sfdis,cert",
    [
        ([int(AGG_1_SFDI_FROM_VALID_CERT), 4444, 2222, 1111], AGG_1_VALID_CERT),
        ([int(AGG_2_SFDI_FROM_VALID_CERT), 3333], AGG_2_VALID_CERT),
        ([int(AGG_3_SFDI_FROM_VALID_CERT)], AGG_3_VALID_CERT),
        ([int(REGISTERED_CERT_SFDI)], REGISTERED_CERT_LFDI),
        ([], UNREGISTERED_CERT_LFDI),
    ],
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

    # According to Sep2: "results" will always be less than or equal to “all.”
    assert parsed_response.results <= parsed_response.all_

    if len(site_sfdis) > 0:
        assert parsed_response.EndDevice, f"received body:\n{body}"
        assert len(parsed_response.EndDevice) == len(site_sfdis), f"received body:\n{body}"
        assert [ed.sFDI for ed in parsed_response.EndDevice] == site_sfdis


@pytest.mark.parametrize(
    "query_string, cert",
    [
        (build_paging_params(limit=-1), AGG_1_VALID_CERT),
        (build_paging_params(limit=-1), REGISTERED_CERT),
        (build_paging_params(start=-1), AGG_1_VALID_CERT),
        (build_paging_params(start=-1), REGISTERED_CERT),
    ],
)
@pytest.mark.anyio
async def test_get_end_device_list_invalid_pagination(
    client: AsyncClient, edev_base_uri: str, query_string: str, cert: str
):
    """Tests that invalid pagination variables on the list endpoint return bad requests"""
    response = await client.get(edev_base_uri + query_string, headers={cert_header: urllib.parse.quote(cert)})
    assert_response_header(response, HTTPStatus.BAD_REQUEST)
    assert_error_response(response)


@pytest.mark.parametrize(
    "query_string, site_sfdis, expected_total, cert",
    [
        (build_paging_params(limit=1), [int(AGG_1_SFDI_FROM_VALID_CERT)], 4, AGG_1_VALID_CERT),
        (build_paging_params(limit=2), [int(AGG_1_SFDI_FROM_VALID_CERT), 4444], 4, AGG_1_VALID_CERT),
        (build_paging_params(limit=2, start=1), [4444, 2222], 4, AGG_1_VALID_CERT),
        (build_paging_params(limit=1, start=1), [4444], 4, AGG_1_VALID_CERT),
        (build_paging_params(limit=1, start=2), [2222], 4, AGG_1_VALID_CERT),
        (build_paging_params(limit=1, start=4), [], 4, AGG_1_VALID_CERT),
        (build_paging_params(limit=2, start=3), [1111], 4, AGG_1_VALID_CERT),
        # add in timestamp filtering
        # This will filter down to Site 2,3,4
        (
            build_paging_params(limit=5, changed_after=datetime(2022, 2, 3, 5, 0, 0, tzinfo=timezone.utc)),
            [int(AGG_1_SFDI_FROM_VALID_CERT), 4444, 2222],
            3,
            AGG_1_VALID_CERT,
        ),
        (
            build_paging_params(limit=5, start=2, changed_after=datetime(2022, 2, 3, 5, 0, 0, tzinfo=timezone.utc)),
            [2222],
            3,
            AGG_1_VALID_CERT,
        ),
        (build_paging_params(limit=2, start=2), [], 2, AGG_2_VALID_CERT),
        (build_paging_params(limit=2, start=1), [], 1, AGG_3_VALID_CERT),
        (build_paging_params(), [633600933412], 1, AGG_3_VALID_CERT),
        (build_paging_params(start=1), [], 1, AGG_3_VALID_CERT),
        # Request sites changed after any change_time values in the DB
        # Should only return the virtual site associated with the aggregator
        (
            build_paging_params(changed_after=datetime(2024, 9, 11, 0, 0, 0, tzinfo=timezone.utc)),
            [int(AGG_1_SFDI_FROM_VALID_CERT)],
            1,
            AGG_1_VALID_CERT,
        ),
        (
            build_paging_params(changed_after=datetime(2024, 9, 11, 0, 0, 0, tzinfo=timezone.utc)),
            [372641169614],
            1,
            AGG_2_VALID_CERT,
        ),
        # Testing a device certificate
        (build_paging_params(limit=10), [int(REGISTERED_CERT_SFDI)], 1, REGISTERED_CERT),
        # Validating edge cases where a zero limit caused issues
        (build_paging_params(limit=0), [], 4, AGG_1_VALID_CERT),
        (build_paging_params(limit=0), [], 1, REGISTERED_CERT),
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

    # According to Sep2: "results" will always be less than or equal to “all.”
    assert parsed_response.results <= parsed_response.all_

    if len(site_sfdis) > 0:
        assert parsed_response.EndDevice, f"received body:\n{body}"
        assert len(parsed_response.EndDevice) == len(site_sfdis), f"received body:\n{body}"
        assert [ed.sFDI for ed in parsed_response.EndDevice] == site_sfdis


@pytest.mark.anyio
@pytest.mark.parametrize(
    "cert,site_id, expected_status, expected_lfdi, expected_sfdi",
    [
        (AGG_1_VALID_CERT, 2, HTTPStatus.OK, "site2-lfdi", 2222),
        (AGG_1_VALID_CERT, 0, HTTPStatus.OK, AGG_1_LFDI_FROM_VALID_CERT, int(AGG_1_SFDI_FROM_VALID_CERT)),
        (REGISTERED_CERT.decode(), 6, HTTPStatus.OK, REGISTERED_CERT_LFDI, int(REGISTERED_CERT_SFDI)),
        (
            REGISTERED_CERT.decode(),
            2,
            HTTPStatus.FORBIDDEN,
            None,
            None,
        ),  # Device cert trying to reach out to another EndDevice (aggregator owned)
        (
            REGISTERED_CERT.decode(),
            5,
            HTTPStatus.FORBIDDEN,
            None,
            None,
        ),  # Device cert trying to reach out to another EndDevice (different device cert)
        (AGG_1_VALID_CERT, 3, HTTPStatus.NOT_FOUND, None, None),  # Wrong Aggregator
        (AGG_1_VALID_CERT, 9999, HTTPStatus.NOT_FOUND, None, None),  # Bad site ID
        (AGG_1_VALID_CERT, 5, HTTPStatus.NOT_FOUND, None, None),  # Aggregator trying to reach a device cert
    ],
)
async def test_get_enddevice(
    client: AsyncClient,
    edev_fetch_uri_format: str,
    cert: str,
    site_id: int,
    expected_status: HTTPStatus,
    expected_lfdi: Optional[str],
    expected_sfdi: Optional[int],
):
    """Tests that fetching named end device's works / fails in simple cases"""

    # check fetching within aggregator
    uri = edev_fetch_uri_format.format(site_id=site_id)
    response = await client.get(uri, headers={cert_header: urllib.parse.quote(cert)})
    assert_response_header(response, expected_status)

    if expected_status == HTTPStatus.OK:
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response: EndDeviceResponse = EndDeviceResponse.from_xml(body)
        assert parsed_response.href == uri
        assert parsed_response.enabled == 1
        assert parsed_response.lFDI == expected_lfdi
        assert parsed_response.sFDI == expected_sfdi

        if site_id == 0:
            assert parsed_response.FunctionSetAssignmentsListLink is None, "No FSA for the aggregator end device"
        else:
            assert parsed_response.FunctionSetAssignmentsListLink is not None, "FSA should exist for a end device"
    else:
        assert_error_response(response)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "cert,site_id, is_device_cert, expected_status",
    [
        (AGG_1_VALID_CERT, 2, False, HTTPStatus.NO_CONTENT),
        (AGG_1_VALID_CERT, 0, False, HTTPStatus.FORBIDDEN),  # Can't delete the aggregator end device
        (REGISTERED_CERT.decode(), 6, True, HTTPStatus.NO_CONTENT),
        (
            REGISTERED_CERT.decode(),
            2,
            True,
            HTTPStatus.FORBIDDEN,
        ),  # Device cert trying to reach out to another EndDevice (aggregator owned)
        (
            REGISTERED_CERT.decode(),
            5,
            True,
            HTTPStatus.FORBIDDEN,
        ),  # Device cert trying to reach out to another EndDevice (different device cert)
        (AGG_1_VALID_CERT, 3, False, HTTPStatus.NOT_FOUND),  # Wrong Aggregator
        (AGG_1_VALID_CERT, 9999, False, HTTPStatus.NOT_FOUND),  # Bad site ID
        (AGG_1_VALID_CERT, 5, False, HTTPStatus.NOT_FOUND),  # Aggregator trying to reach a device cert
    ],
)
async def test_delete_enddevice(
    pg_base_config,
    client: AsyncClient,
    edev_fetch_uri_format: str,
    cert: str,
    site_id: int,
    is_device_cert: bool,
    expected_status: HTTPStatus,
):
    """Tests that deleting named end device's works / fails in simple cases"""

    uri = edev_fetch_uri_format.format(site_id=site_id)
    response = await client.delete(uri, headers={cert_header: urllib.parse.quote(cert)})
    assert_response_header(response, expected_status, expected_content_type=None)

    if response.status_code == HTTPStatus.NO_CONTENT:
        # If the delete succeeded - fire off a get to the same resource to see if it now 404's
        response = await client.get(uri, headers={cert_header: urllib.parse.quote(cert)})

        # Device certs fetching a "missing" EndDevice behave slightly differently
        if is_device_cert:
            assert_response_header(response, HTTPStatus.FORBIDDEN)
        else:
            assert_response_header(response, HTTPStatus.NOT_FOUND)

        # Won't exhaustively check archive use - but sanity check that the archive is receiving records
        async with generate_async_session(pg_base_config) as session:
            site_archive_count = (await session.execute(select(func.count()).select_from(ArchiveSite))).scalar_one()
            assert site_archive_count == 1, "Validate that the archive functionality was utilised"
    else:
        assert response.status_code in [HTTPStatus.NOT_FOUND, HTTPStatus.FORBIDDEN]

        # Won't exhaustively check archive use - but sanity check that the archive is NOT receiving records
        async with generate_async_session(pg_base_config) as session:
            site_archive_count = (await session.execute(select(func.count()).select_from(ArchiveSite))).scalar_one()
            assert site_archive_count == 0, "Nothing should be archived"


@pytest.mark.anyio
async def test_create_end_device_shinehub(client: AsyncClient, edev_base_uri: str):
    """Represents an error found by Shinehub during their testing - it was found that a blank sfdi
    was NOT triggering a validation error - it was instead returning a Unknown error"""
    content = """<EndDevice xmlns="urn:ieee:std:2030.5:ns">
    <sFDI></sFDI>
    <lFDI></lFDI>
    <deviceCategory>14</deviceCategory>
    </EndDevice>"""

    response = await client.post(
        edev_base_uri,
        headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)},
        content=content,
    )

    assert_response_header(response, HTTPStatus.BAD_REQUEST, expected_content_type=None)
    assert_error_response(response)


@pytest.mark.anyio
async def test_create_end_device_specified_sfdi(client: AsyncClient, edev_base_uri: str):
    """When creating an end_device check to see if it persists and is correctly assigned to the aggregator"""

    insert_request: EndDeviceRequest = generate_class_instance(
        EndDeviceRequest, postRate=123, deviceCategory="{0:x}".format(int(DeviceCategory.HOT_TUB)), lFDI="123ABCdef"
    )
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
    assert parsed_response.all_ == 5, f"received body:\n{body}"


@pytest.mark.anyio
async def test_create_end_device_no_sfdi(client: AsyncClient, edev_base_uri: str):
    """When creating an end_device check to see if it persists and is correctly assigned to the aggregator
    (with sfdi be generated on the server side)"""
    insert_request: EndDeviceRequest = generate_class_instance(EndDeviceRequest)
    insert_request.sFDI = 0
    insert_request.lFDI = ""
    insert_request.postRate = 123
    insert_request.deviceCategory = "{0:x}".format(int(DeviceCategory.ENERGY_MANAGEMENT_SYSTEM))
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
    assert parsed_response.lFDI.strip() != ""
    assert parsed_response.sFDI != 0
    assert parsed_response.deviceCategory == insert_request.deviceCategory


@pytest.mark.anyio
@pytest.mark.href_prefix(HREF_PREFIX)
async def test_create_end_device_href_prefix(client: AsyncClient, edev_base_uri: str):
    """Checks that the Location header encodes the HREF_PREFIX"""

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
    assert inserted_href.startswith(HREF_PREFIX)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "site_id, cert, lfdi, sfdi, expected_status",
    [
        (
            1,
            AGG_1_VALID_CERT,
            "site1-lfdi",
            1111,
            HTTPStatus.CREATED,
        ),  # Agg cert updating aggregator
        (
            1,
            AGG_2_VALID_CERT,
            "site1-lfdi",
            1111,
            HTTPStatus.CONFLICT,
        ),  # LFDI belongs to agg 1
        (
            6,
            REGISTERED_CERT.decode(),
            REGISTERED_CERT_LFDI,
            int(REGISTERED_CERT_SFDI),
            HTTPStatus.CREATED,
        ),  # Device cert updating its device
        (
            5,
            REGISTERED_CERT.decode(),
            OTHER_REGISTERED_CERT_LFDI,
            int(OTHER_REGISTERED_CERT_SFDI),
            HTTPStatus.FORBIDDEN,
        ),  # Device cert cant update a seperate DeviceCert
        (
            1,
            REGISTERED_CERT.decode(),
            "site1-lfdi",
            1111,
            HTTPStatus.FORBIDDEN,
        ),  # Device cert cant update a seperate Aggregator device
    ],
)
async def test_update_end_device(
    client: AsyncClient,
    pg_base_config,
    edev_base_uri: str,
    site_id: int,
    cert: str,
    lfdi: str,
    sfdi: int,
    expected_status: HTTPStatus,
):
    """Test that an aggregator can update its own end_device but another aggregator cannot"""

    async with generate_async_session(pg_base_config) as session:
        stmt = select(Site).where(Site.site_id == site_id)
        db_site = (await session.execute(stmt)).scalar_one()
        old_device_category = db_site.device_category
        old_changed_time = db_site.changed_time
        old_created_time = db_site.created_time

    UPDATED_DEVICE_CATEGORY = int(DeviceCategory.INTERIOR_LIGHTING | DeviceCategory.STRIP_HEATERS)

    # Fire off an update that will succeed
    update_request: EndDeviceRequest = generate_class_instance(
        EndDeviceRequest, lFDI=lfdi, sFDI=sfdi, deviceCategory="{0:x}".format(UPDATED_DEVICE_CATEGORY)
    )
    response = await client.post(
        edev_base_uri,
        headers={cert_header: urllib.parse.quote(cert)},
        content=EndDeviceRequest.to_xml(update_request),
    )

    if expected_status != HTTPStatus.CREATED:
        assert_error_response(response)
    else:
        assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)
        assert len(read_response_body_string(response)) == 0
        inserted_href = read_location_header(response)
        assert inserted_href.endswith(f"/{site_id}")

    # Now validate the site in the DB
    async with generate_async_session(pg_base_config) as session:
        stmt = select(Site).where(Site.site_id == site_id)
        db_site = (await session.execute(stmt)).scalar_one()

        if expected_status != HTTPStatus.CREATED:
            assert db_site.device_category == old_device_category
            assert_datetime_equal(old_created_time, db_site.created_time)
            assert_datetime_equal(old_changed_time, db_site.changed_time)
        else:
            assert db_site.device_category == UPDATED_DEVICE_CATEGORY
            assert_datetime_equal(old_created_time, db_site.created_time)
            assert_nowish(db_site.changed_time)


@pytest.mark.anyio
@pytest.mark.href_prefix(HREF_PREFIX)
async def test_update_end_device_href_prefix(client: AsyncClient, edev_base_uri: str):
    """Test that an aggregator end_device and the Location header includes HREF_PREFIX"""

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
    assert inserted_href.startswith(HREF_PREFIX)


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
    assert parsed_response.deviceCategory == "00"  # Default value from the DB base config


@pytest.mark.anyio
@pytest.mark.parametrize(
    "unregistered_cert_header, lfdi, sfdi, expected",
    [
        (UNREGISTERED_CERT.decode(), UNREGISTERED_CERT_LFDI.lower(), int(UNREGISTERED_CERT_SFDI), HTTPStatus.CREATED),
        (UNREGISTERED_CERT.decode(), UNREGISTERED_CERT_LFDI.upper(), int(UNREGISTERED_CERT_SFDI), HTTPStatus.CREATED),
        (UNREGISTERED_CERT_LFDI, UNREGISTERED_CERT_LFDI.lower(), int(UNREGISTERED_CERT_SFDI), HTTPStatus.CREATED),
        (UNREGISTERED_CERT_LFDI, UNREGISTERED_CERT_LFDI.upper(), int(UNREGISTERED_CERT_SFDI), HTTPStatus.CREATED),
        # Trying bad combos of lfdi/sfdi
        (UNREGISTERED_CERT_LFDI, REGISTERED_CERT_LFDI, int(UNREGISTERED_CERT_SFDI), HTTPStatus.FORBIDDEN),
        (UNREGISTERED_CERT_LFDI, UNREGISTERED_CERT_LFDI, int(REGISTERED_CERT_SFDI), HTTPStatus.FORBIDDEN),
        (UNREGISTERED_CERT_LFDI, REGISTERED_CERT_LFDI, int(REGISTERED_CERT_SFDI), HTTPStatus.FORBIDDEN),
        (REGISTERED_CERT_LFDI, UNREGISTERED_CERT_LFDI, int(UNREGISTERED_CERT_SFDI), HTTPStatus.FORBIDDEN),
        (UNREGISTERED_CERT_LFDI, OTHER_CERT_LFDI, int(OTHER_CERT_SFDI), HTTPStatus.FORBIDDEN),
        (UNREGISTERED_CERT.decode(), OTHER_CERT_LFDI, int(OTHER_CERT_SFDI), HTTPStatus.FORBIDDEN),
    ],
)
async def test_create_end_device_device_registration(
    edev_base_uri,
    client: AsyncClient,
    pg_base_config,
    unregistered_cert_header: str,
    lfdi: str,
    sfdi: int,
    expected: HTTPStatus,
):
    """Can a certificate register itself as a new end device"""

    async with generate_async_session(pg_base_config) as session:
        site_count_before = await count_all_sites(session, None, None)

    insert_request: EndDeviceRequest = generate_class_instance(EndDeviceRequest)
    insert_request.postRate = 123
    insert_request.deviceCategory = "{0:x}".format(int(DeviceCategory.HOT_TUB))
    insert_request.lFDI = lfdi
    insert_request.sFDI = int(sfdi)
    response = await client.post(
        edev_base_uri,
        headers={cert_header: urllib.parse.quote(unregistered_cert_header)},
        content=EndDeviceRequest.to_xml(insert_request),
    )
    assert_response_header(response, expected, expected_content_type=None)

    if expected == HTTPStatus.CREATED:
        assert len(read_response_body_string(response)) == 0
        expected_site_count = site_count_before + 1
    else:
        assert_error_response(response)
        expected_site_count = site_count_before

    async with generate_async_session(pg_base_config) as session:
        assert expected_site_count == await count_all_sites(session, None, None)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "unregistered_cert_header, lfdi, sfdi",
    [
        (UNREGISTERED_CERT.decode(), UNREGISTERED_CERT_LFDI, int(UNREGISTERED_CERT_SFDI)),
        (UNREGISTERED_CERT_LFDI, UNREGISTERED_CERT_LFDI.lower(), int(UNREGISTERED_CERT_SFDI)),
        (UNREGISTERED_CERT_LFDI, UNREGISTERED_CERT_LFDI.upper(), int(UNREGISTERED_CERT_SFDI)),
    ],
)
@pytest.mark.disable_device_registration
async def test_create_end_device_device_registration_disabled(
    edev_base_uri,
    client: AsyncClient,
    pg_base_config,
    unregistered_cert_header: str,
    lfdi: str,
    sfdi: int,
):
    """Do attempts for a certificate to register itself as a new end device fail if the device registration is
    disabled"""

    async with generate_async_session(pg_base_config) as session:
        site_count_before = await count_all_sites(session, None, None)

    insert_request: EndDeviceRequest = generate_class_instance(EndDeviceRequest)
    insert_request.postRate = 123
    insert_request.deviceCategory = "{0:x}".format(int(DeviceCategory.HOT_TUB))
    insert_request.lFDI = lfdi
    insert_request.sFDI = int(sfdi)
    response = await client.post(
        edev_base_uri,
        headers={cert_header: urllib.parse.quote(unregistered_cert_header)},
        content=EndDeviceRequest.to_xml(insert_request),
    )
    assert_response_header(response, HTTPStatus.FORBIDDEN, expected_content_type=None)
    assert_error_response(response)

    async with generate_async_session(pg_base_config) as session:
        assert site_count_before == await count_all_sites(session, None, None)


@pytest.mark.parametrize("static_pin_raw, expected_pin", [("123", 1236), ("55221", 552215)])
@pytest.mark.anyio
async def test_create_end_device_device_static_registration_pin(
    preserved_environment,
    edev_base_uri,
    client: AsyncClient,
    pg_base_config,
    static_pin_raw: str,
    expected_pin: str,
):
    """If the registration PIN is forced to be static (by config) - Ensure it's being set"""

    os.environ["STATIC_REGISTRATION_PIN"] = static_pin_raw

    insert_request: EndDeviceRequest = generate_class_instance(EndDeviceRequest)
    insert_request.postRate = 123
    insert_request.deviceCategory = "{0:x}".format(int(DeviceCategory.HOT_TUB))
    insert_request.lFDI = UNREGISTERED_CERT_LFDI
    insert_request.sFDI = int(UNREGISTERED_CERT_SFDI)
    response = await client.post(
        edev_base_uri,
        headers={cert_header: urllib.parse.quote(UNREGISTERED_CERT)},
        content=EndDeviceRequest.to_xml(insert_request),
    )
    assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)
    edev_location = read_location_header(response)

    # Now fetch the Registration - it should be the static value
    response = await client.get(edev_location + "/rg", headers={cert_header: urllib.parse.quote(UNREGISTERED_CERT)})
    assert_response_header(response, HTTPStatus.OK)
    parsed_response: RegistrationResponse = RegistrationResponse.from_xml(read_response_body_string(response))
    assert parsed_response.pIN == expected_pin

    # The registration PIN for other sites should be what's in the DB (and not static)
    response = await client.get("/edev/1/rg", headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)})
    assert_response_header(response, HTTPStatus.OK)
    parsed_response: RegistrationResponse = RegistrationResponse.from_xml(read_response_body_string(response))
    assert parsed_response.pIN == 111115, "This is defined in base_config.sql for site 1"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "cert,site_id, expected_status, expected_pin",
    [
        (AGG_1_VALID_CERT, 1, HTTPStatus.OK, 111115),
        (AGG_1_VALID_CERT, 2, HTTPStatus.OK, 222220),
        (AGG_1_VALID_CERT, 0, HTTPStatus.FORBIDDEN, None),  # No registration for aggregator end device
        (REGISTERED_CERT.decode(), 6, HTTPStatus.OK, 666660),
        (
            REGISTERED_CERT.decode(),
            2,
            HTTPStatus.FORBIDDEN,
            None,
        ),  # Device cert trying to reach out to another EndDevice (aggregator owned)
        (
            REGISTERED_CERT.decode(),
            5,
            HTTPStatus.FORBIDDEN,
            None,
        ),  # Device cert trying to reach out to another EndDevice (different device cert)
        (AGG_1_VALID_CERT, 3, HTTPStatus.NOT_FOUND, None),  # Wrong Aggregator
        (AGG_1_VALID_CERT, 9999, HTTPStatus.NOT_FOUND, None),  # Bad site ID
        (AGG_1_VALID_CERT, 5, HTTPStatus.NOT_FOUND, None),  # Aggregator trying to reach a device cert
    ],
)
async def test_get_enddevice_registration(
    client: AsyncClient,
    edev_registration_fetch_uri_format: str,
    cert: str,
    site_id: int,
    expected_status: HTTPStatus,
    expected_pin: Optional[int],
):
    """Tests that fetching named end device's works / fails in simple cases"""

    # check fetching within aggregator
    uri = edev_registration_fetch_uri_format.format(site_id=site_id)
    response = await client.get(uri, headers={cert_header: urllib.parse.quote(cert)})
    assert_response_header(response, expected_status)

    if expected_status == HTTPStatus.OK:
        body = read_response_body_string(response)
        assert len(body) > 0
        parsed_response: RegistrationResponse = RegistrationResponse.from_xml(body)
        assert parsed_response.href == uri
        assert parsed_response.pIN == expected_pin
    else:
        assert_error_response(response)
