from typing import Any, Optional

import pydantic_xml
import pytest
from envoy_schema.server.schema.sep2.device_capability import DeviceCapabilityResponse

from envoy.server.crud import link
from envoy.server.request_state import RequestStateParameters
from tests.postgres_testing import generate_async_session


@pytest.mark.anyio
@pytest.mark.parametrize(
    "model, prefix, expected_links, uri_parameters",
    [
        (
            DeviceCapabilityResponse,
            None,
            {
                "EndDeviceListLink": {"href": "/edev", "all_": "3"},
                "MirrorUsagePointListLink": {"href": "/mup", "all_": "3"},
            },
            {},
        ),
        (
            DeviceCapabilityResponse,
            "my/custom/prefix/",
            {
                "EndDeviceListLink": {"href": "/my/custom/prefix/edev", "all_": "3"},
                "MirrorUsagePointListLink": {"href": "/my/custom/prefix/mup", "all_": "3"},
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
    prefix: Optional[str],
    expected_links: dict[str, dict[str, str]],
    uri_parameters: dict[str, Any],
):
    async with generate_async_session(pg_base_config) as session:
        links = await link.get_supported_links(
            session=session,
            model=model,
            rs_params=RequestStateParameters(1, None, prefix),
            uri_parameters=uri_parameters,
        )
    assert links == expected_links
