import enum
from typing import List, Optional

from pydantic_xml import attr, element

from server.schema.sep2.base import (
    Link,
    ListLink,
    SubscribableList,
    SubscribableResource,
)
from server.schema.sep2.time import TimeType


class DeviceCategoryType(enum.Flag):
    Electric_vehicle = 65536
    Virutal_or_mixed_der = 262144
    Reciprocating_engine = 524288
    Photovoltaic_system = 2097152
    Combined_pv_and_storage = 8388608
    Other_generation_system = 16777216
    Other_storage_system = 33554432


class AbstractDevice(SubscribableResource):
    deviceCategory: Optional[DeviceCategoryType] = element()
    lFDI: Optional[int] = element()
    sFDI: int = element()
    ConfigurationLink: Optional[str] = element()
    DeviceInformationLink: Optional[Link] = element()
    DeviceStatusLink: Optional[Link] = element()
    IPInterfaceListLink: Optional[Link] = element()
    LoadSheAvailabilityListLink: Optional[ListLink] = element()
    LogEventsListLink: Optional[Link] = element()
    PowerStatusLink: Optional[Link] = element()
    FileStatusLink: Optional[Link] = element()
    DERListLink: Optional[ListLink] = element()


class EndDeviceRequest(AbstractDevice, tag="EndDevice"):
    changedTime: TimeType = element()
    enabled: Optional[bool] = element(default=True)
    postRate: Optional[int] = element()

    FunctionSetAssignmentsListLink: Optional[ListLink] = element()
    RegistrationLink: Optional[Link] = element()
    SubscriptionLink: Optional[Link] = element()
    FlowReservationRequestListLink: Optional[Link] = element()
    FlowReservationResponseListLink: Optional[Link] = element()


class EndDeviceResponse(EndDeviceRequest, tag="EndDevice"):
    href: Optional[str] = attr()


class EndDeviceListResponse(SubscribableList, tag="EndDeviceList"):
    href: Optional[str] = attr()

    EndDevice: Optional[List[EndDeviceResponse]] = element()
