from typing import Optional

from pydantic_xml import attr, element

from envoy.server.schema import uri
from envoy.server.schema.sep2.base import DEFAULT_POLLRATE, FunctionSetAssignmentsBase, Link, ListLink, PollRateType


class DeviceCapabilityResponse(FunctionSetAssignmentsBase):
    href: str = attr(default=uri.DeviceCapabilityUri)
    pollrate: PollRateType = DEFAULT_POLLRATE

    # (0..1) Link
    SelfDeviceLink: Optional[Link] = element()

    # (0..1) ListLink
    EndDeviceListLink: Optional[ListLink] = element()
    MirrorUsagePointListLink: Optional[ListLink] = element()
