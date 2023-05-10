from datetime import datetime
from typing import Union

import pytest

from envoy.server.mapper.common import generate_mrid


@pytest.mark.parametrize(
    "args_to_pass, expected_output",
    [([1], "0001"),
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
