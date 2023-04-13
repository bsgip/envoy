import enum
from typing import Optional

from pydantic_xml import BaseXmlModel, attr
from pydantic_xml.element import SearchMode

""" Abstract
"""
nsmap = {"": "urn:ieee:std:2030.5:ns", "csipaus": "http://csipaus.org/ns"}


class BaseXmlModelWithNS(BaseXmlModel):
    def __init_subclass__(
        cls,
        *args,
        **kwargs,
    ):
        super().__init_subclass__(*args, **kwargs)
        cls.__xml_nsmap__ = nsmap
        cls.__xml_search_mode__ = SearchMode.UNORDERED


""" Resource
"""


class PollRateType(BaseXmlModelWithNS):
    pollRate: Optional[int] = attr()


class Resource(BaseXmlModelWithNS):
    href: Optional[str] = attr()


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
    """A List to which a Subscription can be requested. """
    all_: int = attr(name="all")  # The number specifying "all" of the items in the list. Required on GET
    results: int = attr()  # Indicates the number of items in this page of results.


class List(Resource):
    """Container to hold a collection of object instances or references. See Design Pattern section for additional
    details."""
    all_: int = attr(name="all")  # The number specifying "all" of the items in the list. Required on GET
    results: int = attr()  # Indicates the number of items in this page of results.


class Link(Resource):
    pass


class ListLink(Link):
    all_: Optional[str] = attr(name="all")


class HexBinary32(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if len(v) > 8:
            raise ValueError("HexBinary32 max length of 8.")
        return cls(v)
