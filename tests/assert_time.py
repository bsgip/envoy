from datetime import datetime
from typing import Optional, Union


def assert_fuzzy_datetime_match(
    expected_time: Union[int, float, datetime], actual_time: Union[int, float, datetime], fuzziness_seconds: int = 2
):
    """Asserts that two datetimes are within fuzziness_seconds of each other. If the times are numbers then they
    will be interpreted as a timestamp"""
    if type(expected_time) != datetime:
        expected_time = datetime.fromtimestamp(float(expected_time))

    if type(actual_time) != datetime:
        actual_time = datetime.fromtimestamp(float(actual_time))

    delta_seconds = (expected_time - actual_time).total_seconds()
    assert (
        abs(delta_seconds) < fuzziness_seconds
    ), f"Expected {expected_time} to be within {fuzziness_seconds} of {actual_time} but it was {delta_seconds}"


def assert_nowish(expected_time: Union[int, float, datetime], fuzziness_seconds: int = 20):
    """Asserts that datetime is within fuzziness_seconds of now"""
    assert_fuzzy_datetime_match(expected_time, datetime.now(), fuzziness_seconds=fuzziness_seconds)


def assert_datetime_equal(a: Optional[Union[datetime, int, float]], b: Optional[Union[datetime, int, float]]):
    """Asserts datetime equality based on timestamp (handles None too). If the times are numbers then they
    will be interpreted as a timestamp"""
    if a is None or b is None:
        assert a is None and b is None
    else:
        if not isinstance(a, datetime):
            a = datetime.fromtimestamp(float(a))
        if not isinstance(b, datetime):
            b = datetime.fromtimestamp(float(b))
        assert a.timestamp() == b.timestamp(), f"Comparing {a} ({a.timestamp()}) to {b} ({b.timestamp()})"
