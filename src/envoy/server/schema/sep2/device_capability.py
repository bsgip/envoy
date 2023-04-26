from typing import Optional

from pydantic_xml import attr, element

from envoy.server.schema import uri
from envoy.server.schema.sep2.base import FunctionSetAssignmentBase, Link, ListLink


class DeviceCapabilityResponse(FunctionSetAssignmentBase):
    href: str = attr(default=uri.DeviceCapabilityUri)
    pollrate: int = attr(default=900)

    # (0..1) Link
    SelfDeviceLink: Optional[Link] = element()

    # (0..1) ListLink
    EndDeviceListLink: Optional[ListLink] = element()
    MirrorUsagePointListLink: Optional[ListLink] = element()
