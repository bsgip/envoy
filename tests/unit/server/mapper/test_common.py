from datetime import datetime
from typing import Any, Optional, Union

import pytest

from envoy.server.mapper.common import generate_href, generate_mrid, remove_href_prefix
from envoy.server.request_state import RequestStateParameters


@pytest.mark.parametrize(
    "args_to_pass, expected_output",
    [
        ([1], "0001"),
        ([255], "00ff"),
        ([255, 255, 1], "00ff00ff0001"),
        ([255, 255, 1], "00ff00ff0001"),
        ([255, -255, 18], "00ff00ff0012"),
        ([], ""),
    ],
)
def test_generate_mrid(args_to_pass: list[Union[int, float]], expected_output: str):
    assert generate_mrid(*args_to_pass) == expected_output


def test_generate_mrid_128_bit():
    """Takes a 'representative' mrid generation from RateComponent and checks
    to see if it's within 128 bit as that one has potential to get quite large"""

    # These values have no specific meaning - they're just there to capture some "long" and "short" values when
    # being converted to a string
    result = generate_mrid(87, 128363, 45, int(datetime.now().timestamp()))
    assert len(result) < 32, "32 hex chars is 16 bytes which is 128 bit"


@pytest.mark.parametrize(
    "uri_format, prefix, args, kwargs, expected",
    [
        # Test kwargs are applied
        ("abc/{val1}/{val2}", None, None, {"val1": "def", "val2": 54}, "abc/def/54"),
        ("abc/def", None, None, None, "abc/def"),
        # Test args are applied
        ("abc/{0}/{1}/{2}", None, [1, 2, "bob"], None, "abc/1/2/bob"),
        ("abc/{0}/{val1}/{1}", None, [1, 2], {"val1": "baz"}, "abc/1/baz/2"),
        # Test leading slash is correctly applied
        ("abc/{val1}", None, None, {"val1": "1234"}, "abc/1234"),
        ("/abc/{val1}", None, None, {"val1": "1234"}, "/abc/1234"),
        ("abc/{val1}", "prefix", None, {"val1": "1234"}, "prefix/abc/1234"),
        ("abc/{val1}", "/prefix", None, {"val1": "1234"}, "prefix/abc/1234"),
        ("/abc/{val1}", "prefix", None, {"val1": "1234"}, "/prefix/abc/1234"),
        ("/abc/{val1}", "/prefix", None, {"val1": "1234"}, "/prefix/abc/1234"),
        # Test prefix joining
        ("abc/{val1}/", "/prefix", None, {"val1": "1234"}, "prefix/abc/1234"),
        ("abc/{val1}/", "/prefix/", None, {"val1": "1234"}, "prefix/abc/1234"),
        ("/abc/{val1}/", "/prefix/", None, {"val1": "1234"}, "/prefix/abc/1234"),
        ("abc/{val1}/", "/prefix/with/parts", None, {"val1": "1234"}, "prefix/with/parts/abc/1234"),
        ("/abc/{val1}/", "/prefix/with/parts/", None, {"val1": "1234"}, "/prefix/with/parts/abc/1234"),
    ],
)
def test_generate_href(uri_format: str, prefix: Optional[str], args: Any, kwargs: Any, expected: str):
    """Tests various combinations of args/kwargs/prefixes"""
    if args is not None and kwargs is not None:
        assert generate_href(uri_format, RequestStateParameters(1, prefix), *args, **kwargs) == expected
    elif args is not None:
        assert generate_href(uri_format, RequestStateParameters(1, prefix), *args) == expected
    elif kwargs is not None:
        assert generate_href(uri_format, RequestStateParameters(1, prefix), **kwargs) == expected
    else:
        assert generate_href(uri_format, RequestStateParameters(1, prefix)) == expected


@pytest.mark.parametrize(
    "uri, prefix, expected",
    [
        ("/", None, "/"),
        ("/path/part", None, "/path/part"),
        ("/path/part", "/bad/path/part", "/path/part"),  # Bad prefix
        ("/path/part", "/path", "/part"),
        ("/path/part", "/path/", "/part"),
        ("/path/part/thats/longer/", "/path/part", "/thats/longer/"),
        ("/path/part/thats/longer/", "/path/part/", "/thats/longer/"),
    ],
)
def test_remove_href_prefix(uri: str, prefix: Optional[str], expected: str):
    ps = RequestStateParameters(1, prefix)
    assert remove_href_prefix(uri, ps) == expected


def test_generate_href_format_errors():
    """Ensures that errors raised by format propogate up"""

    with pytest.raises(KeyError):
        generate_href("{p1}/{p2}", RequestStateParameters(1, None), p1="val1")

    with pytest.raises(KeyError):
        generate_href("{p1}/{p2}", RequestStateParameters(1, "prefix/"), p1="val1")
