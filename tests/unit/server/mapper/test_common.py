from typing import Union

import pytest

from envoy.server.mapper.common import generate_mrid


@pytest.mark.parametrize(
    "expected",
    [([1], "0001"),
     ([255], "00ff"),
     ([255, 255, 1], "00ff00ff0001"),
     ([255, 255, 1], "00ff00ff0001"),
     ([255, -255, 18], "00ff00ff0012"),
     ([], ""),
     ],
)
def test_generate_mrid(expected: tuple[list[Union[int, float]], str]):
    (args, expected_output) = expected
    assert generate_mrid(*args) == expected_output
