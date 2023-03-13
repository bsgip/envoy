import enum
from typing import Optional

from pydantic_xml import BaseXmlModel, attr

""" Abstract
"""
nsmap = {"": "urn:ieee:std:2030.5:ns"}


class BaseXmlModelWithNS(BaseXmlModel, nsmap=nsmap):
    pass


""" Resource
"""


class PollRateType(BaseXmlModelWithNS):
    pollRate: Optional[int] = attr()


class Resource(BaseXmlModelWithNS):
    pass


class PENType(int):
    pass


class VersionType(int):
    pass


class mRIDType(int):
    pass


class IdentifiedObject(Resource):
    description: Optional[str]
    mRID: mRIDType
    version: Optional[VersionType]


class SubscribableType(enum.IntEnum):
    resource_does_not_support_subscriptions = 0
    resource_supports_non_conditional_subscriptions = 1
    resource_supports_conditional_subscriptions = 2
    resource_supports_both_conditional_and_non_conditional_subscriptions = 3


class SubscribableResource(Resource):
    subscribable: Optional[SubscribableType] = attr()


class SubscribableList(SubscribableResource):
    all_: int = attr(name="all")
    result: int = attr()


class Link(Resource):
    href: str = attr()


class ListLink(Link):
    all_: Optional[str] = attr(name="all")
