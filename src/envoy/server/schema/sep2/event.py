from typing import Optional

from pydantic_xml import element

from envoy.server.schema.sep2.identification import RespondableSubscribableIdentifiedObject
from envoy.server.schema.sep2.types import DateTimeIntervalType, OneHourRangeType, TimeType


class Event(RespondableSubscribableIdentifiedObject):
    """An Event indicates information that applies to a particular period of time. Events SHALL be executed relative
    to the time of the server, as described in the Time function set section 11.1."""

    creationTime: TimeType = element()
    interval: DateTimeIntervalType = element()


class RandomizableEvent(Event):
    """An Event that can indicate time ranges over which the start time and duration SHALL be randomized."""

    randomizeDuration: Optional[OneHourRangeType] = element()
    randomizeStart: Optional[OneHourRangeType] = element()
