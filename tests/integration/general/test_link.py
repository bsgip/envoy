from typing import Any

import pydantic_xml
import pytest
from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse

from envoy.server.crud import link
from tests.postgres_testing import generate_async_session


@pytest.mark.anyio
@pytest.mark.parametrize(
    "model, expected_links, uri_parameters",
    [
        (
            DeviceCapabilityResponse,
            {
                "EndDeviceListLink": {"href": "/edev", "all_": "3"},
                "MirrorUsagePointListLink": {"href": "/mup", "all_": "3"},
            },
            {},
        ),
        # (
        #     EndDeviceListResponse,
        #     {"EndDeviceListLink": {"href": "/edev", "all_": "3"},},
        #     {"site_id": 123}
        # ),
        # (
        #     EndDeviceResponse,
        #     {"EndDeviceListLink": {"href": "/edev", "all_": "3"}},
        #     {"site_id": 123}
        # ),
    ],
)
async def test_get_supported_links(
    pg_base_config,
    model: pydantic_xml.BaseXmlModel,
    expected_links: dict[str, dict[str, str]],
    uri_parameters: dict[str, Any],
):
    async with generate_async_session(pg_base_config) as session:
        links = await link.get_supported_links(
            session=session, model=model, aggregator_id=1, uri_parameters=uri_parameters
        )
    assert links == expected_links
