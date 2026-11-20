from datetime import UTC, datetime, timedelta
from itertools import product

import pytest
from envoy_schema.server.schema.sep2.event import EventStatusType

from envoy.server.mapper.sep2.event import (
    EventVersion,
    calculate_event_status_and_version,
    map_to_event_status,
)

START = datetime(2023, 4, 5, 6, 7, 8, tzinfo=UTC)
END = START + timedelta(seconds=300)
BEFORE = START - timedelta(seconds=1)
DURING = START + timedelta(seconds=1)
AFTER = END + timedelta(seconds=1)


@pytest.mark.parametrize(
    "now, is_superseded, is_deleted, is_randomized, expected_status, expected_version",
    [
        (BEFORE, False, False, False, EventStatusType.Scheduled, EventVersion.SCHEDULED),
        (BEFORE, False, False, True, EventStatusType.Scheduled, EventVersion.SCHEDULED),
        (START, False, False, False, EventStatusType.Active, EventVersion.ACTIVE),
        (DURING, False, False, False, EventStatusType.Active, EventVersion.ACTIVE),
        (END, False, False, False, EventStatusType.Scheduled, EventVersion.COMPLETED),
        (AFTER, False, False, False, EventStatusType.Scheduled, EventVersion.COMPLETED),
        (BEFORE, True, False, False, EventStatusType.Superseded, EventVersion.SUPERSEDED),
        (DURING, True, False, False, EventStatusType.Superseded, EventVersion.SUPERSEDED),
        (AFTER, True, False, False, EventStatusType.Superseded, EventVersion.SUPERSEDED),
        (BEFORE, False, True, False, EventStatusType.Cancelled, EventVersion.CANCELLED),
        (DURING, True, True, False, EventStatusType.Cancelled, EventVersion.CANCELLED),
        (AFTER, False, True, True, EventStatusType.CancelledWithRandomization, EventVersion.CANCELLED),
    ],
)
def test_calculate_event_status_and_version(
    now: datetime,
    is_superseded: bool,
    is_deleted: bool,
    is_randomized: bool,
    expected_status: EventStatusType,
    expected_version: EventVersion,
):
    result = calculate_event_status_and_version(START, END, now, is_superseded, is_deleted, is_randomized)
    assert result.event_status == expected_status
    assert result.version == expected_version


def test_calculate_event_status_and_version_status_change_implies_version_change():
    """Any change in event status between two evaluations MUST result in a change in version. Randomization is a fixed
    property of an event so it's held constant between the two evaluations"""
    for is_randomized in [True, False]:
        all_inputs = list(product([BEFORE, DURING, AFTER], [True, False], [True, False], [is_randomized]))
        for a, b in product(all_inputs, all_inputs):
            result_a = calculate_event_status_and_version(START, END, *a)
            result_b = calculate_event_status_and_version(START, END, *b)
            if result_a.event_status != result_b.event_status:
                assert result_a.version != result_b.version, f"{a} vs {b}"


def test_calculate_event_status_and_version_natural_lifecycle_increments():
    """The natural progression of an event should result in a strictly increasing version"""
    versions = [
        calculate_event_status_and_version(START, END, BEFORE, False, False, False).version,
        calculate_event_status_and_version(START, END, DURING, False, False, False).version,
        calculate_event_status_and_version(START, END, AFTER, False, False, False).version,
        calculate_event_status_and_version(START, END, AFTER, True, False, False).version,
        calculate_event_status_and_version(START, END, AFTER, True, True, False).version,
    ]
    assert versions == sorted(versions)
    assert len(set(versions)) == len(versions)


def test_map_to_event_status():
    status_time = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    result = map_to_event_status(EventStatusType.Superseded, status_time)
    assert result.currentStatus == EventStatusType.Superseded
    assert result.dateTime == int(status_time.timestamp())
    assert result.potentiallySuperseded is False
