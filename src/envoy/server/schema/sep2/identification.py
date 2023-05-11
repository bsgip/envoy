from typing import Optional

from pydantic_xml import attr, element

from envoy.server.schema.sep2 import base, types


class Resource(base.BaseXmlModelWithNS):
    href: Optional[str] = attr()


class IdentifiedObject(Resource):
    description: Optional[str] = element()
    mRID: types.mRIDType = element()
    version: Optional[types.VersionType] = element()


class SubscribableResource(Resource):
    subscribable: Optional[types.SubscribableType] = attr()


class SubscribableList(SubscribableResource):
    """A List to which a Subscription can be requested."""

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
    all_: Optional[int] = attr(name="all")
