import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, tzinfo

logger = logging.getLogger(__name__)

# How far to search (forwards/backwards) from a point in time for a timezone transition. DST observing timezones
# transition at least twice per year so anything beyond this is treated as "no DST".
TRANSITION_SEARCH_HORIZON_SECONDS = 400 * 24 * 60 * 60

# Coarse step used when scanning for a transition. Must be smaller than the shortest gap between two consecutive
# transitions (otherwise a pair of transitions could cancel out and be missed). There exist timezones with transitions
# as short as 9 days.
TRANSITION_SEARCH_STEP_SECONDS = 24 * 60 * 60 * 5  # ~5 days


@dataclass
class DaylightSavingsTimeInfo:
    dst_end: int  # Unix (UTC) timestamp at which daylight savings next ends begins (apply dst_offset)
    dst_start: int  # Unix (UTC) timestamp at which daylight savings next begins (remove dst_offset)
    dst_offset: int  # Daylight savings time offset (in seconds) from local time (if DST in effect), 0 otherwise.


def _tz_state(tz: tzinfo, timestamp: int) -> tuple[timedelta | None, timedelta | None]:
    """Returns the (utcoffset, dst) pair in effect for tz at the specified UTC unix timestamp"""
    dt = datetime.fromtimestamp(timestamp, tz=tz)
    return (dt.utcoffset(), dt.dst())


def _find_transition(tz: tzinfo, timestamp: int, forward: bool) -> int | None:
    """Finds the nearest timezone transition (a change in utcoffset/dst) relative to timestamp.

    If forward is True - returns the first transition strictly after timestamp. Otherwise returns the most recent
    transition at or before timestamp. The returned value is the first whole second (UTC unix timestamp) for which the
    new offset applies. Returns None if no transition is found within TRANSITION_SEARCH_HORIZON_SECONDS"""

    step = TRANSITION_SEARCH_STEP_SECONDS if forward else -TRANSITION_SEARCH_STEP_SECONDS
    origin_state = _tz_state(tz, timestamp)

    # Coarse scan until the state changes
    probe = timestamp
    while abs(probe - timestamp) < TRANSITION_SEARCH_HORIZON_SECONDS:
        next_probe = probe + step
        if _tz_state(tz, next_probe) != origin_state:
            break
        probe = next_probe
    else:
        return None

    # Bisect down to the exact second. "same" always shares origin_state, "changed" never does
    same, changed = probe, next_probe
    while abs(changed - same) > 1:
        mid = (same + changed) // 2
        if _tz_state(tz, mid) == origin_state:
            same = mid
        else:
            changed = mid

    # The transition instant is the first second of the later of the two states
    return max(same, changed)


def get_dst_info(now_time: datetime) -> DaylightSavingsTimeInfo:
    """Returns the start and end daylight savings time relative to a specified time.

    If DST is currently in effect, dst_start will be the (past) time it began and dst_end the (future) time it ends.
    If DST isn't currently in effect, dst_start will be the next (future) time it begins and dst_end the subsequent
    time that it ends.

    The transitions are discovered by searching the public utcoffset()/dst() behaviour of the tzinfo (so this works
    for any tzinfo implementation - eg zoneinfo or the tzlocal pytz shim).

    Args:
        now_time (datetime.datetime): datetime with timezone for which daylight savings time details will be returned.

    Returns:
        DaylightSavingsTimeInfo:

    """
    dst_zero = DaylightSavingsTimeInfo(0, 0, 0)

    tz = now_time.tzinfo
    if tz is None:
        logger.warning("No tzinfo specified on supplied datetime, returning zero dst info.")
        return dst_zero

    now_ts = int(now_time.timestamp())

    # Fail fast on timezones that won't have any upcoming transitions (eg UTC / non DST zones)
    next_transition = _find_transition(tz, now_ts, forward=True)
    if next_transition is None:
        return dst_zero

    now_dst = now_time.dst()
    dst_offset_total_seconds = int(now_dst.total_seconds()) if now_dst is not None else 0

    if dst_offset_total_seconds > 0:
        # In DST - it started at the most recent transition and ends at the next
        dst_start_time = _find_transition(tz, now_ts, forward=False)
        dst_end_time: int | None = next_transition
    else:
        # Not in DST - it starts at the next transition and ends at the one after that
        dst_start_time = next_transition
        dst_end_time = _find_transition(tz, next_transition, forward=True)

    if dst_start_time is None or dst_end_time is None:
        logger.warning(f"Unable to resolve DST transitions for {tz} at {now_time}, returning zero dst info.")
        return dst_zero

    return DaylightSavingsTimeInfo(dst_end=dst_end_time, dst_start=dst_start_time, dst_offset=dst_offset_total_seconds)


def utc_now() -> datetime:
    """Returns an unambiguous timezone aware (UTC) datetime representing this moment (according to server time)"""
    return datetime.now(tz=UTC)
