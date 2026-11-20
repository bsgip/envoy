from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum

from envoy_schema.server.schema.sep2.event import EventStatus, EventStatusType


class EventVersion(IntEnum):
    """The IdentifiedObject.version values that will be encoded for an Event (eg DERControl / TimeTariffInterval).

    sep2 requires that ANY change to an Event's EventStatus results in a change to IdentifiedObject.version. Because
    envoy derives event status dynamically (based on the current time and the superseded/deleted state of the
    underlying record), the version is ALSO derived dynamically by cycling through these known values. Each value
    corresponds to a distinct stage in the lifecycle of an event and the values are ordered such that the "natural"
    progression of an event (scheduled -> active -> completed and/or superseded -> cancelled) will always result in
    an increasing version number."""

    SCHEDULED = 1  # Event start is in the future
    ACTIVE = 2  # Event is currently in progress
    COMPLETED = 3  # Event has finished (it will still encode with a Scheduled status)
    SUPERSEDED = 4  # Event has been superseded by another event
    CANCELLED = 5  # Event has been deleted/cancelled (with or without randomization)


@dataclass(frozen=True)
class EventStatusAndVersion:
    event_status: EventStatusType
    version: EventVersion


def calculate_event_status_and_version(
    start_time: datetime,
    end_time: datetime,
    now: datetime,
    is_superseded: bool,
    is_deleted: bool,
    is_randomized: bool,
) -> EventStatusAndVersion:
    """Calculates the sep2 EventStatus.currentStatus for an event and the IdentifiedObject.version that should be
    encoded alongside it. The two are calculated together to ensure that any change in event status will ALWAYS
    result in a change in version.

    start_time: When the event starts (inclusive)
    end_time: When the event ends (exclusive)
    now: The current moment in time to evaluate the event against
    is_superseded: Has this event been superseded by another event
    is_deleted: Has this event been deleted (i.e. cancelled)
    is_randomized: Does this event specify a randomized start (only used to differentiate cancellation types)"""
    if is_deleted:
        return EventStatusAndVersion(
            EventStatusType.CancelledWithRandomization if is_randomized else EventStatusType.Cancelled,
            EventVersion.CANCELLED,
        )
    elif is_superseded:
        return EventStatusAndVersion(EventStatusType.Superseded, EventVersion.SUPERSEDED)
    elif now < start_time:
        return EventStatusAndVersion(EventStatusType.Scheduled, EventVersion.SCHEDULED)
    elif now < end_time:
        return EventStatusAndVersion(EventStatusType.Active, EventVersion.ACTIVE)
    else:
        # Completed events are still encoded as "Scheduled" but they need a distinct version to "Active" as the
        # status is transitioning from Active -> Scheduled
        return EventStatusAndVersion(EventStatusType.Scheduled, EventVersion.COMPLETED)


def map_to_event_status(event_status: EventStatusType, status_time: datetime) -> EventStatus:
    return EventStatus.model_validate(
        {
            "currentStatus": event_status,
            "dateTime": int(status_time.timestamp()),
            "potentiallySuperseded": False,
        }
    )
