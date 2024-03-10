from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from tzlocal import get_localzone, get_localzone_name

from envoy.server.manager.time import get_dst_info, get_tz_key, utc_now


def test_get_tz_key_via_getlocalzone():
    """Mainly testing to see if exceptions are not raised"""
    local_tz = get_localzone()
    now_time = datetime.now(tz=local_tz)
    assert get_tz_key(now_time) == get_localzone_name()


def test_get_tz_key_via_zoneinfo():
    """Mainly testing to see if exceptions are not raised"""
    now_time = datetime(2022, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("Australia/Brisbane"))
    assert get_tz_key(now_time) == "Australia/Brisbane"


# fmt: off
@pytest.mark.parametrize("dt, dst_start, dst_end, dst_offset", [
    # Currently in DST. start indicates the time in the past that DST turned on.
    # End indicates when it swaps in the near future
    (datetime(2022, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("Australia/Sydney")), 1633190400, 1648915200, 3600),

    # Currently out of DST. Start indicates October start in a few months.
    # End indicates the April end in the following year
    (datetime(2022, 6, 7, 8, 9, 10, tzinfo=ZoneInfo("Australia/Sydney")), 1664640000, 1680364800, 0),

    # Missing timezone details
    (datetime(2022, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("Australia/Brisbane")), 0, 0, 0),  # No DST
    (datetime(2022, 2, 3, 4, 5, 6), 0, 0, 0),  # No Timezone
    (datetime(2022, 2, 3, 4, 5, 6, tzinfo=timezone.utc), 0, 0, 0),  # UTC Timezone
])
# fmt: on
def test_get_dst_info(dt: datetime, dst_end: int, dst_start: int, dst_offset: int):
    result = get_dst_info(dt)

    assert result.dst_end == dst_end
    assert result.dst_start == dst_start
    assert result.dst_offset == dst_offset


def test_utc_now():
    now = utc_now()
    assert now.tzinfo is not None
