import pydantic_xml
import pytest

from envoy.server.crud import link
from envoy.server.schema.sep2.device_capability import DeviceCapabilityResponse
from envoy.server.schema.sep2.end_device import EndDeviceListResponse, EndDeviceResponse
from tests.postgres_testing import generate_async_session


@pytest.mark.anyio
@pytest.mark.parametrize(
    "model, expected_links",
    [
        (
            DeviceCapabilityResponse,
            {"SelfDeviceLink": {"href": "/sdev"}, "EndDeviceListLink": {"href": "/edev", "all_": "3"}},
        ),
        (
            EndDeviceListResponse,
            {"SelfDeviceLink": {"href": "/sdev"}, "EndDeviceListLink": {"href": "/edev", "all_": "3"}},
        ),
        (EndDeviceResponse, {"SelfDeviceLink": {"href": "/sdev"}, "EndDeviceListLink": {"href": "/edev", "all_": "3"}}),
    ],
)
async def test_get_supported_links(
    pg_base_config, model: pydantic_xml.BaseXmlModel, expected_links: dict[str, dict[str, str]]
):
    async with generate_async_session(pg_base_config) as session:
        links = await link.get_supported_links(session=session, model=DeviceCapabilityResponse, aggregator_id=1)
        print(links)
    assert links == expected_links
