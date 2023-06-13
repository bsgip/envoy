import urllib.parse
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Optional, Sequence

import pytest
from httpx import AsyncClient
from sqlalchemy import select

import envoy.server.schema.uri as uris
from envoy.server.model.site_reading import SiteReading
from envoy.server.schema.sep2.metering_mirror import (
    MirrorMeterReading,
    MirrorUsagePoint,
    MirrorUsagePointListResponse,
    MirrorUsagePointRequest,
)
from envoy.server.schema.sep2.types import (
    AccumulationBehaviourType,
    DataQualifierType,
    FlowDirectionType,
    KindType,
    PhaseCode,
    ServiceKind,
    UomType,
)
from tests.assert_time import assert_nowish
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as AGG_1_VALID_CERT
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_FINGERPRINT as AGG_2_VALID_CERT
from tests.data.fake.generator import assert_class_instance_equality
from tests.integration.integration_server import cert_pem_header
from tests.integration.request import build_paging_params
from tests.integration.response import assert_response_header, read_location_header, read_response_body_string
from tests.postgres_testing import generate_async_session


@pytest.mark.parametrize(
    "start, changed_after, limit, cert, expected_count, expected_mup_hrefs",
    [
        # Testing start / limit
        (0, None, 99, AGG_1_VALID_CERT, 3, ["/mup/4", "/mup/3", "/mup/1"]),
        (1, None, 99, AGG_1_VALID_CERT, 3, ["/mup/3", "/mup/1"]),
        (2, None, 99, AGG_1_VALID_CERT, 3, ["/mup/1"]),
        (3, None, 99, AGG_1_VALID_CERT, 3, []),
        (0, None, 2, AGG_1_VALID_CERT, 3, ["/mup/4", "/mup/3"]),
        (1, None, 1, AGG_1_VALID_CERT, 3, ["/mup/3"]),
        # Changed time
        (
            0,
            datetime(2022, 5, 6, 11, 22, 30, tzinfo=timezone.utc),
            99,
            AGG_1_VALID_CERT,
            3,
            ["/mup/4", "/mup/3", "/mup/1"],
        ),
        (0, datetime(2022, 5, 6, 11, 22, 35, tzinfo=timezone.utc), 99, AGG_1_VALID_CERT, 2, ["/mup/4", "/mup/3"]),
        (0, datetime(2022, 5, 6, 13, 22, 35, tzinfo=timezone.utc), 99, AGG_1_VALID_CERT, 1, ["/mup/4"]),
        (0, datetime(2022, 5, 6, 14, 22, 35, tzinfo=timezone.utc), 99, AGG_1_VALID_CERT, 0, []),
        (1, datetime(2022, 5, 6, 11, 22, 36, tzinfo=timezone.utc), 2, AGG_1_VALID_CERT, 2, ["/mup/3"]),
        # Changed cert
        (0, None, 99, AGG_2_VALID_CERT, 0, []),
    ],
)
@pytest.mark.anyio
async def test_get_mirror_usage_point_list_pagination(
    client: AsyncClient,
    start: Optional[int],
    changed_after: Optional[datetime],
    limit: Optional[int],
    cert: str,
    expected_count: int,
    expected_mup_hrefs: list[int],
):
    """Simple test of pagination of MUPs for a given aggregator"""
    response = await client.get(
        uris.MirrorUsagePointListUri + build_paging_params(limit=limit, start=start, changed_after=changed_after),
        headers={cert_pem_header: urllib.parse.quote(cert)},
    )
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: MirrorUsagePointListResponse = MirrorUsagePointListResponse.from_xml(body)
    assert parsed_response.all_ == expected_count, f"received body:\n{body}"
    assert parsed_response.results == len(expected_mup_hrefs), f"received body:\n{body}"

    if len(expected_mup_hrefs) > 0:
        assert parsed_response.mirrorUsagePoints, f"received body:\n{body}"
        assert [mup.href for mup in parsed_response.mirrorUsagePoints] == expected_mup_hrefs
    else:
        assert (
            parsed_response.mirrorUsagePoints is None or len(parsed_response.mirrorUsagePoints) == 0
        ), f"received body:\n{body}"


@pytest.mark.parametrize(
    "mup, expected_href",
    [
        # Create a new mup
        (
            MirrorUsagePointRequest.validate(
                {
                    "mRID": "123",
                    "deviceLFDI": "site1-lfdi",
                    "serviceCategoryKind": ServiceKind.ELECTRICITY,
                    "roleFlags": 0,
                    "status": 0,
                    "mirrorMeterReadings": [
                        {
                            "mRID": "123abc",
                            "readingType": {
                                "powerOfTenMultiplier": 5,
                                "kind": KindType.POWER,
                                "uom": UomType.DISPLACEMENT_POWER_FACTOR_COSTHETA,
                                "phase": PhaseCode.PHASE_CA,
                                "flowDirection": FlowDirectionType.REVERSE,
                            },
                        }
                    ],
                }
            ),
            "/mup/6",
        ),
        # Update an existing mup
        (
            MirrorUsagePointRequest.validate(
                {
                    "mRID": "456",
                    "deviceLFDI": "site1-lfdi",
                    "serviceCategoryKind": ServiceKind.ELECTRICITY,
                    "roleFlags": 0,
                    "status": 0,
                    "mirrorMeterReadings": [
                        {
                            "mRID": "456abc",
                            "readingType": {
                                "powerOfTenMultiplier": 3,
                                "kind": KindType.POWER,
                                "uom": UomType.REAL_POWER_WATT,
                                "phase": PhaseCode.PHASE_B,
                                "flowDirection": FlowDirectionType.FORWARD,
                                "dataQualifier": DataQualifierType.AVERAGE,
                                "accumulationBehaviour": AccumulationBehaviourType.CUMULATIVE,
                                "intervalLength": None,
                            },
                        }
                    ],
                }
            ),
            "/mup/1",
        ),
    ],
)
@pytest.mark.anyio
async def test_create_update_mup(client: AsyncClient, mup: MirrorUsagePointRequest, expected_href: str):
    """Tests creating/updating a mup and seeing if the updates stick and can be fetched via list/direct requests"""
    now = datetime.now(tz=timezone.utc)

    # create/update the mup
    response = await client.post(
        uris.MirrorUsagePointListUri,
        content=MirrorUsagePointRequest.to_xml(mup, skip_empty=True),
        headers={cert_pem_header: urllib.parse.quote(AGG_1_VALID_CERT)},
    )
    assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)
    assert read_location_header(response) == expected_href

    # see if we can fetch the mup directly
    response = await client.get(expected_href, headers={cert_pem_header: urllib.parse.quote(AGG_1_VALID_CERT)})
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_response: MirrorUsagePoint = MirrorUsagePoint.from_xml(body)
    assert parsed_response.href == expected_href
    assert_class_instance_equality(MirrorUsagePoint, mup, parsed_response, ignored_properties=set(["href", "mRID"]))

    # see if the list endpoint can fetch it via the updated time
    response = await client.get(
        uris.MirrorUsagePointListUri + build_paging_params(limit=99, changed_after=now),
        headers={cert_pem_header: urllib.parse.quote(AGG_1_VALID_CERT)},
    )
    assert_response_header(response, HTTPStatus.OK)
    body = read_response_body_string(response)
    assert len(body) > 0
    parsed_list_response: MirrorUsagePointListResponse = MirrorUsagePointListResponse.from_xml(body)
    assert parsed_list_response.results == 1, f"received body:\n{body}"
    assert [mup.href for mup in parsed_list_response.mirrorUsagePoints] == [expected_href]


@pytest.mark.anyio
async def test_submit_mirror_meter_reading(client: AsyncClient, pg_base_config):
    """Submits a batch of readings to a mup and checks the DB to see if they are created"""
    mmr: MirrorMeterReading = MirrorMeterReading.validate(
        {
            "mRID": "1234",
            "mirrorReadingSets": [
                {
                    "mRID": "1234abc",
                    "timePeriod": {
                        "duration": 603,
                        "start": 1341579365,
                    },
                    "readings": [
                        {"value": 9, "timePeriod": {"duration": 301, "start": 1341579365}, "localID": "123"},
                        {"value": -10, "timePeriod": {"duration": 302, "start": 1341579666}, "localID": "0f0d"},
                    ],
                }
            ],
        }
    )
    mup_id = 1

    # submit the readings
    response = await client.post(
        uris.MirrorUsagePointUri.format(mup_id=mup_id),
        content=MirrorMeterReading.to_xml(mmr, skip_empty=True),
        headers={cert_pem_header: urllib.parse.quote(AGG_1_VALID_CERT)},
    )
    assert_response_header(response, HTTPStatus.CREATED, expected_content_type=None)

    # validate the DB directly
    async with generate_async_session(pg_base_config) as session:
        stmt = select(SiteReading).order_by(SiteReading.site_reading_id)

        resp = await session.execute(stmt)
        all_readings: Sequence[SiteReading] = resp.scalars().all()

        assert len(all_readings) == 6, "We should've added 2 readings"
        assert all_readings[-2].site_reading_type_id == mup_id
        assert all_readings[-2].local_id == int("123", base=16)
        assert all_readings[-2].value == 9
        assert all_readings[-2].time_period_seconds == 301
        assert all_readings[-2].time_period_start == datetime.fromtimestamp(1341579365, tz=timezone.utc)
        assert_nowish(all_readings[-2].changed_time)

        assert all_readings[-1].site_reading_type_id == mup_id
        assert all_readings[-1].local_id == int("0f0d", base=16)
        assert all_readings[-1].value == -10
        assert all_readings[-1].time_period_seconds == 302
        assert all_readings[-1].time_period_start == datetime.fromtimestamp(1341579666, tz=timezone.utc)
        assert_nowish(all_readings[-1].changed_time)
