from typing import Optional

from pydantic_xml import attr, element

from envoy.server.schema.sep2.base import HexBinary32, HexBinary128, Resource, SubscribableType, VersionType
from envoy.server.schema.sep2.time import DateTimeIntervalType, TimeType


class OneHourRangeType(int):
    """A signed time offset, typically applied to a Time value, expressed in seconds, with range -3600 to 3600."""
    pass


class RespondableResource(Resource):
    """A Resource to which a Response can be requested."""
    replyTo: Optional[str] = attr()
    responseRequired: Optional[HexBinary32] = attr()


class RespondableSubscribableIdentifiedObject(RespondableResource):
    """An IdentifiedObject to which a Response can be requested."""
    subscribable: Optional[SubscribableType] = attr()

    description: Optional[str] = element()
    mRID: HexBinary128 = element()
    version: Optional[VersionType] = element()


class Event(RespondableSubscribableIdentifiedObject):
    """An Event indicates information that applies to a particular period of time. Events SHALL be executed relative
    to the time of the server, as described in the Time function set section 11.1."""

    creationTime: TimeType = element()
    interval: DateTimeIntervalType = element()


class RandomizableEvent(Event):
    """An Event that can indicate time ranges over which the start time and duration SHALL be randomized."""
    randomizeDuration: Optional[OneHourRangeType] = element()
    randomizeStart: Optional[OneHourRangeType] = element()
