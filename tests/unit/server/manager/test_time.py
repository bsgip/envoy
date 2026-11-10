from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from tzlocal import get_localzone

from envoy.server.manager.time import get_dst_info, utc_now


# fmt: off
@pytest.mark.parametrize("dt, dst_start, dst_end, dst_offset", [
    # Currently in DST. start indicates the time in the past that DST turned on.
    # End indicates when it swaps in the near future
    (datetime(2022, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("Australia/Sydney")), 1633190400, 1648915200, 3600),

    # Currently out of DST. Start indicates October start in a few months.
    # End indicates the April end in the following year
    (datetime(2022, 6, 7, 8, 9, 10, tzinfo=ZoneInfo("Australia/Sydney")), 1664640000, 1680364800, 0),

    # Exactly on the transition boundaries
    (datetime.fromtimestamp(1648915200, tz=ZoneInfo("Australia/Sydney")), 1664640000, 1680364800, 0),
    (datetime.fromtimestamp(1648915199, tz=ZoneInfo("Australia/Sydney")), 1633190400, 1648915200, 3600),
    (datetime.fromtimestamp(1664640000, tz=ZoneInfo("Australia/Sydney")), 1664640000, 1680364800, 3600),

    # Northern hemisphere (DST starts 2024-03-31T01:00Z, ends 2024-10-27T01:00Z)
    (datetime(2024, 1, 15, 12, 0, 0, tzinfo=ZoneInfo("Europe/London")), 1711846800, 1729990800, 0),
    (datetime(2024, 7, 15, 12, 0, 0, tzinfo=ZoneInfo("Europe/London")), 1711846800, 1729990800, 3600),

    # Lord Howe Island has a 30 minute DST offset (DST starts 2022-10-01T15:30Z, ends 2023-04-01T15:00Z)
    (datetime(2022, 12, 1, tzinfo=ZoneInfo("Australia/Lord_Howe")), 1664638200, 1680361200, 1800),

    # Missing timezone details
    (datetime(2022, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("Australia/Brisbane")), 0, 0, 0),  # No DST
    (datetime(2022, 2, 3, 4, 5, 6), 0, 0, 0),  # No Timezone
    (datetime(2022, 2, 3, 4, 5, 6, tzinfo=UTC), 0, 0, 0),  # UTC Timezone
    (datetime(2022, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("UTC")), 0, 0, 0),  # UTC Timezone
    (datetime(2022, 2, 3, 4, 5, 6, tzinfo=timezone(timedelta(hours=10))), 0, 0, 0),  # Fixed offset
])
# fmt: on
def test_get_dst_info(dt: datetime, dst_end: int, dst_start: int, dst_offset: int):
    result = get_dst_info(dt)

    assert result.dst_end == dst_end
    assert result.dst_start == dst_start
    assert result.dst_offset == dst_offset


def test_get_dst_info_transitions_are_exact():
    """The returned transitions should be the exact second the offset changes"""
    tz = ZoneInfo("America/New_York")
    for dt in [datetime(2023, 2, 1, tzinfo=tz), datetime(2023, 8, 1, tzinfo=tz)]:
        result = get_dst_info(dt)
        assert result.dst_start < result.dst_end

        for ts in [result.dst_start, result.dst_end]:
            before = datetime.fromtimestamp(ts - 1, tz=tz)
            after = datetime.fromtimestamp(ts, tz=tz)
            assert before.utcoffset() != after.utcoffset()

        # DST is active from dst_start (inclusive) until dst_end (exclusive)
        assert datetime.fromtimestamp(result.dst_start, tz=tz).dst() == timedelta(hours=1)
        assert datetime.fromtimestamp(result.dst_end - 1, tz=tz).dst() == timedelta(hours=1)
        assert datetime.fromtimestamp(result.dst_end, tz=tz).dst() == timedelta(0)


def test_get_dst_info_local_zone():
    """Mainly testing that whatever tzinfo tzlocal hands back is usable without exceptions"""
    result = get_dst_info(datetime.now(tz=get_localzone()))
    assert result.dst_offset >= 0
    assert (result.dst_start == 0) == (result.dst_end == 0)


def test_utc_now():
    now = utc_now()
    assert now.tzinfo is not None
