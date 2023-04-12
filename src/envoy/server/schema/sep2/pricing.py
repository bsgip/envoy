from enum import IntEnum
from functools import reduce
from typing import List, Optional

from pydantic_xml import attr, element

from envoy.server.schema.csip_aus.connection_point import ConnectionPointLink as ConnectionPointLinkType
from envoy.server.schema.sep2.base import HexBinary32, Link, ListLink, SubscribableList, SubscribableResource
from envoy.server.schema.sep2.time import TimeType


class CurrencyCode(IntEnum):
    """Non exhaustive set of numerical ISO 4217 currency codes. Described in 2030.5 / ISO 4217"""
    NOT_APPLICABLE = 0
    AUSTRALIAN_DOLLAR = 36
    CANADIAN_DOLLAR = 124
    US_DOLLAR = 840
    EURO = 978

class TariffProfile(IdentifiedObject):
    currency: Optional[HexBinary32] = element()
    lFDI: Optional[str] = element()
    sFDI: int = element()


