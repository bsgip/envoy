from enum import IntFlag, auto
from functools import reduce
from typing import List, Optional

from pydantic_xml import attr, element

from envoy.server.schema.sep2.base import HexBinary32, Link, ListLink, SubscribableList, SubscribableResource
from envoy.server.schema.sep2.time import TimeType


class DeviceCategory(IntFlag):
    """DeviceCategory is a series of bit flags describing a category of EndDevice. Described in 2030.5"""
    PROGRAMMABLE_COMMUNICATING_THERMOSTAT = auto()
    STRIP_HEATERS = auto()
    BASEBOARD_HEATERS = auto()
    WATER_HEATER = auto()
    POOL_PUMP = auto()
    SAUNA = auto()
    HOT_TUB = auto()
    SMART_APPLIANCE = auto()
    IRRIGATION_PUMP = auto()
    MANAGED_COMMERCIAL_AND_INDUSTRIAL_LOADS = auto()
    SIMPLE_MISC_LOADS = auto()
    EXTERIOR_LIGHTING = auto()
    INTERIOR_LIGHTING = auto()
    LOAD_CONTROL_SWITCH = auto()
    ENERGY_MANAGEMENT_SYSTEM = auto()
    SMART_ENERGY_MODULE = auto()
    ELECTRIC_VEHICLE = auto()
    ELECTRIC_VEHICLE_SUPPLY_EQUIPMENT = auto()
    VIRTUAL_OR_MIXED_DER = auto()
    RECIPROCATING_ENGINE = auto()
    FUEL_CELL = auto()
    PHOTOVOLTAIC_SYSTEM = auto()
    COMBINED_HEAT_AND_POWER = auto()
    COMBINED_PV_AND_STORAGE = auto()
    OTHER_GENERATION_SYSTEM = auto()
    OTHER_STORAGE_SYSTEM = auto()


# The combination of ALL DeviceCategory bit flags
DEVICE_CATEGORY_ALL_SET: DeviceCategory = reduce(lambda a, b: a | b, DeviceCategory)


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
