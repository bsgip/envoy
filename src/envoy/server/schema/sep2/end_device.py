from typing import List, Optional

from pydantic_xml import element

from envoy.server.schema.csip_aus.connection_point import ConnectionPointLink as ConnectionPointLinkType
from envoy.server.schema.sep2 import primitive_types
from envoy.server.schema.sep2.identification import Link, ListLink, SubscribableList, SubscribableResource
from envoy.server.schema.sep2.time import TimeType


class AbstractDevice(SubscribableResource):
    deviceCategory: Optional[primitive_types.HexBinary32] = element()
    lFDI: Optional[str] = element()
    sFDI: int = element()


class EndDeviceRequest(AbstractDevice, tag="EndDevice"):
    postRate: Optional[int] = element()


class EndDeviceResponse(EndDeviceRequest, tag="EndDevice"):
    changedTime: TimeType = element()
    enabled: Optional[int] = element(default=1)

    # csip extension
    ConnectionPointLink: Optional[ConnectionPointLinkType] = element(ns="csipaus")

    # sep2 Links
    ConfigurationLink: Optional[str] = element()
    DeviceInformationLink: Optional[Link] = element()
    DeviceStatusLink: Optional[Link] = element()
    IPInterfaceListLink: Optional[Link] = element()
    LoadShedAvailabilityListLink: Optional[ListLink] = element()
    LogEventListLink: Optional[Link] = element()
    PowerStatusLink: Optional[Link] = element()
    FileStatusLink: Optional[Link] = element()
    DERListLink: Optional[ListLink] = element()
    FunctionSetAssignmentsListLink: Optional[ListLink] = element()
    RegistrationLink: Optional[Link] = element()
    SubscriptionListLink: Optional[ListLink] = element()
    FlowReservationRequestListLink: Optional[Link] = element()
    FlowReservationResponseListLink: Optional[Link] = element()


class EndDeviceListResponse(SubscribableList, tag="EndDeviceList"):
    EndDevice: Optional[List[EndDeviceResponse]] = element()
