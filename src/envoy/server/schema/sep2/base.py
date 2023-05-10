import enum
from typing import Optional

from pydantic_xml import BaseXmlModel, attr, element
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


DEFAULT_POLLRATE = PollRateType(pollRate=900)


class Resource(BaseXmlModelWithNS):
    href: Optional[str] = attr()


class PENType(int):
    pass


class VersionType(int):
    pass


class HexBinary32(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if len(v) > 8:
            raise ValueError("HexBinary32 max length of 8.")
        return cls(v)


class HexBinary128(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if len(v) > 32:
            raise ValueError("HexBinary128 max length of 32.")
        return cls(v)


class mRIDType(HexBinary128):
    pass


class IdentifiedObject(Resource):
    description: Optional[str] = element()
    mRID: mRIDType = element()
    version: Optional[VersionType] = element()


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


class SubscribableIdentifiedObject(SubscribableResource):
    description: Optional[str] = element()  # The description is a human readable text describing or naming the object.
    mRID: mRIDType = element()  # The global identifier of the object
    version: Optional[VersionType] = element()  # Contains the version number of the object.


class List(Resource):
    """Container to hold a collection of object instances or references. See Design Pattern section for additional
    details."""
    all_: int = attr(name="all")  # The number specifying "all" of the items in the list. Required on GET
    results: int = attr()  # Indicates the number of items in this page of results.


class Link(Resource):
    pass


class ListLink(Link):
    all_: Optional[int] = attr(name="all")


class FunctionSetAssignmentsBase(Resource):
    # Optional (0..1) Links
    TimeLink: Optional[Link] = element()

    # Optional (0..1) ListLinks
    CustomerAccountListLink: Optional[ListLink] = element()
    DemandResponseProgramListLink: Optional[ListLink] = element()
    DERProgramListLink: Optional[ListLink] = element()
    FileListLink: Optional[ListLink] = element()
    MessagingProgramListLink: Optional[ListLink] = element()
    PrepaymentListLink: Optional[ListLink] = element()
    ResponseSetListLink: Optional[ListLink] = element()
    TariffProfileListLink: Optional[ListLink] = element()
    UsagePointListLink: Optional[ListLink] = element()
