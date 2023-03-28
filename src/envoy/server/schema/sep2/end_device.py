import enum
from typing import List, Optional

from pydantic_xml import attr, element

from envoy.server.schema.sep2.base import (
    HexBinary32,
    Link,
    ListLink,
    SubscribableList,
    SubscribableResource,
)
from envoy.server.schema.sep2.time import TimeType


class AbstractDevice(SubscribableResource):
    deviceCategory: Optional[HexBinary32] = element()
    lFDI: Optional[str] = element()
    sFDI: int = element()


class EndDeviceRequest(AbstractDevice, tag="EndDevice"):
    postRate: Optional[int] = element()


class EndDeviceResponse(EndDeviceRequest, tag="EndDevice"):
    href: Optional[str] = attr()

    changedTime: TimeType = element()
    enabled: Optional[int] = element(default=1)

    # Links
    ConfigurationLink: Optional[str] = element()
    DeviceInformationLink: Optional[Link] = element()
    DeviceStatusLink: Optional[Link] = element()
    IPInterfaceListLink: Optional[Link] = element()
    LoadSheAvailabilityListLink: Optional[ListLink] = element()
    LogEventsListLink: Optional[Link] = element()
    PowerStatusLink: Optional[Link] = element()
    FileStatusLink: Optional[Link] = element()
    DERListLink: Optional[ListLink] = element()
    FunctionSetAssignmentsListLink: Optional[ListLink] = element()
    RegistrationLink: Optional[Link] = element()
    SubscriptionLink: Optional[Link] = element()
    FlowReservationRequestListLink: Optional[Link] = element()
    FlowReservationResponseListLink: Optional[Link] = element()


class EndDeviceListResponse(SubscribableList, tag="EndDeviceList"):
    href: Optional[str] = attr()

    EndDevice: Optional[List[EndDeviceResponse]] = element()
