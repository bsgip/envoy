from datetime import datetime, timedelta, timezone
from itertools import product
from typing import Callable

import pytest
from assertical.fake.generator import generate_class_instance

from envoy.server.mapper.constants import MridType, PricingReadingType, ResponseSetType
from envoy.server.mapper.sep2.mrid import (
    MAX_IANA_PEN,
    MAX_INT_26,
    MAX_INT_32,
    MAX_INT_64,
    MAX_MRID_ID,
    MAX_MRID_TYPE,
    MridMapper,
    decode_iana_pen,
    decode_mrid_id,
    decode_mrid_type,
    encode_mrid,
)
from envoy.server.request_scope import BaseRequestScope


def assert_mrid(mrid: str):
    assert isinstance(mrid, str)
    assert len(mrid) == 32, "MRID is a 128 bit type, so 32 hex chars"
    valid_chars = set(f"{i:x}" for i in range(0, 16))
    assert len(valid_chars) == 16, "Sanity check"
    assert all(c in valid_chars for c in mrid), "Should be only a set of chars in 0-9 or a-f"


def assert_and_append_mrid(mrid: str, mrids: list[str]):
    """Simple utility - runs assert_mrid and then appends the value to the mrids list"""
    assert_mrid(mrid)
    mrids.append(mrid)


@pytest.mark.parametrize("mrid_type", MridType)
def test_encode_mrid_all_types(mrid_type: MridType):
    """All values of MridType enum should generate valid mrids"""
    assert_mrid(encode_mrid(mrid_type, 1, 2))


@pytest.mark.parametrize("mrid_type", MridType)
def test_decode_mrid_all_types(mrid_type: MridType):
    """All values of MridType enum should decode via decode_mrid_type"""
    mrid = encode_mrid(mrid_type, 1, 2)
    decoded_mrid_type = decode_mrid_type(mrid)
    assert isinstance(decoded_mrid_type, MridType)
    assert decoded_mrid_type == mrid_type

    assert decode_mrid_type(mrid.upper()) == mrid_type, "hex case shouldn't affect decoding"
    assert decode_mrid_type(mrid.lower()) == mrid_type, "hex case shouldn't affect decoding"


@pytest.mark.parametrize("expected_id", [0, MAX_MRID_ID, 13, 97982371, 2])
def test_decode_mrid_id_values(expected_id: int):
    """Various values of id should decode via decode_mrid_id"""

    for iana_pen in [0, 123124, MAX_IANA_PEN]:
        mrid = encode_mrid(MridType.DYNAMIC_OPERATING_ENVELOPE, expected_id, iana_pen)
        decoded_mrid_id = decode_mrid_id(mrid)
        assert isinstance(decoded_mrid_id, int)
        assert decoded_mrid_id == expected_id

        assert decode_mrid_id(mrid.upper()) == expected_id, "hex case shouldn't affect decoding"
        assert decode_mrid_id(mrid.lower()) == expected_id, "hex case shouldn't affect decoding"


@pytest.mark.parametrize("expected_iana_pen", [0, MAX_IANA_PEN, 11, 131515, 2])
def test_decode_iana_pen_values(expected_iana_pen: int):
    """Various values of id should decode via decode_iana_pen"""

    for id in [0, 151, MAX_MRID_ID]:
        mrid = encode_mrid(MridType.DYNAMIC_OPERATING_ENVELOPE, id, expected_iana_pen)
        decoded_iana_pen = decode_iana_pen(mrid)
        assert isinstance(decoded_iana_pen, int)
        assert decoded_iana_pen == expected_iana_pen

        assert decode_iana_pen(mrid.upper()) == expected_iana_pen, "hex case shouldn't affect decoding"
        assert decode_iana_pen(mrid.lower()) == expected_iana_pen, "hex case shouldn't affect decoding"


@pytest.mark.parametrize(
    "mrid_type, id, iana_pen",
    [
        (MridType.DEFAULT_DOE, 1, 2),
        (MridType.FUNCTION_SET_ASSIGNMENT, 3, 4),
        (MAX_MRID_TYPE, MAX_MRID_ID, MAX_IANA_PEN),
    ],
)
def test_encode_mrid_stable_values(mrid_type, id, iana_pen):
    """Tests that mrid calls are stable for the same query params"""
    assert encode_mrid(mrid_type, id, iana_pen) == encode_mrid(mrid_type, id, iana_pen)


def test_encode_mrid_unique_values():
    """All values of MridType enum should generate valid mrids that are distinct from eachother"""

    all_generated_mrids = []

    # Min values
    assert_and_append_mrid(encode_mrid(0, 0, 0), all_generated_mrids)

    # Max values
    assert_and_append_mrid(encode_mrid(MAX_MRID_TYPE, 0, 0), all_generated_mrids)
    assert_and_append_mrid(encode_mrid(0, MAX_MRID_ID, 0), all_generated_mrids)
    assert_and_append_mrid(encode_mrid(0, 0, MAX_IANA_PEN), all_generated_mrids)
    assert_and_append_mrid(encode_mrid(MAX_MRID_TYPE, MAX_MRID_ID, MAX_IANA_PEN), all_generated_mrids)

    # General values
    assert_and_append_mrid(encode_mrid(1, 1, 2), all_generated_mrids)
    assert_and_append_mrid(encode_mrid(MridType.FUNCTION_SET_ASSIGNMENT, 1, 2), all_generated_mrids)
    assert_and_append_mrid(encode_mrid(MridType.FUNCTION_SET_ASSIGNMENT, 986239112321, 124), all_generated_mrids)

    assert len(all_generated_mrids) > 0
    assert len(all_generated_mrids) == len(set(all_generated_mrids)), "All values should be unique"


def test_encode_mrid_out_of_range_values():
    """Check encode_mrid raises ValueError on invalid values"""

    # Check negative values
    with pytest.raises(ValueError):
        encode_mrid(-1, 0, 0)

    with pytest.raises(ValueError):
        encode_mrid(0, -1, 0)

    with pytest.raises(ValueError):
        encode_mrid(0, 0, -1)

    # Check large values
    with pytest.raises(ValueError):
        encode_mrid(0, 0, MAX_IANA_PEN + 1)

    with pytest.raises(ValueError):
        encode_mrid(0, MAX_MRID_ID + 1, 0)

    with pytest.raises(ValueError):
        encode_mrid(MAX_MRID_TYPE + 1, 0, 0)


def test_all_default_encodings_unique():
    """Sanity check that all the encoding methods when called with default values will still return unique mrids (due
    to the mrid type)"""
    scope1 = generate_class_instance(BaseRequestScope, seed=1, iana_pen=0)
    all_generated_mrids = []

    assert_and_append_mrid(MridMapper.encode_default_doe_mrid(scope1), all_generated_mrids)
    assert_and_append_mrid(MridMapper.encode_doe_program_mrid(scope1, 0, 0), all_generated_mrids)
    assert_and_append_mrid(MridMapper.encode_doe_mrid(scope1, 0), all_generated_mrids)
    assert_and_append_mrid(MridMapper.encode_function_set_assignment_mrid(scope1, 0, 0), all_generated_mrids)
    for prt in PricingReadingType:
        assert_and_append_mrid(
            MridMapper.encode_rate_component_mrid(scope1, 0, 0, datetime.min.replace(tzinfo=timezone.utc), prt),
            all_generated_mrids,
        )
        assert_and_append_mrid(MridMapper.encode_time_tariff_interval_mrid(scope1, 0, prt), all_generated_mrids)
    assert_and_append_mrid(MridMapper.encode_tariff_profile_mrid(scope1, 0), all_generated_mrids)
    assert_and_append_mrid(MridMapper.encode_response_set_mrid(scope1, 0), all_generated_mrids)

    assert len(all_generated_mrids) == len(set(all_generated_mrids)), "Each MRID should be unique"


def test_encode_default_doe_mrid():
    scope1 = generate_class_instance(BaseRequestScope, seed=1, iana_pen=123)
    scope2 = generate_class_instance(BaseRequestScope, seed=1, iana_pen=456)

    mrid1 = MridMapper.encode_default_doe_mrid(scope1)
    assert_mrid(mrid1)
    assert mrid1 == MridMapper.encode_default_doe_mrid(scope1), "Mrid should be stable"
    assert mrid1 != MridMapper.encode_default_doe_mrid(scope2), "PEN number should affect things"

    assert decode_mrid_type(mrid1) == MridType.DEFAULT_DOE


def test_encode_doe_program_mrid():
    scope1 = generate_class_instance(BaseRequestScope, seed=1, iana_pen=123)
    scope2 = generate_class_instance(BaseRequestScope, seed=1, iana_pen=456)

    all_generated_mrids = []

    for scope in [scope1, scope2]:
        assert_and_append_mrid(MridMapper.encode_doe_program_mrid(scope, 0, 0), all_generated_mrids)
        assert_and_append_mrid(MridMapper.encode_doe_program_mrid(scope, 123, 456), all_generated_mrids)
        assert_and_append_mrid(MridMapper.encode_doe_program_mrid(scope, MAX_INT_32, MAX_INT_32), all_generated_mrids)

    assert len(all_generated_mrids) == len(set(all_generated_mrids)), "Each MRID should be unique"
    assert all(decode_mrid_type(m) == MridType.DER_PROGRAM for m in all_generated_mrids)


def test_encode_doe_mrid():
    scope1 = generate_class_instance(BaseRequestScope, seed=1, iana_pen=123)
    scope2 = generate_class_instance(BaseRequestScope, seed=1, iana_pen=456)

    all_generated_mrids = []

    for scope in [scope1, scope2]:
        assert_and_append_mrid(MridMapper.encode_doe_mrid(scope, 0), all_generated_mrids)
        assert_and_append_mrid(MridMapper.encode_doe_mrid(scope, 123), all_generated_mrids)
        assert_and_append_mrid(MridMapper.encode_doe_mrid(scope, MAX_INT_64), all_generated_mrids)

    assert len(all_generated_mrids) == len(set(all_generated_mrids)), "Each MRID should be unique"
    assert all(decode_mrid_type(m) == MridType.DYNAMIC_OPERATING_ENVELOPE for m in all_generated_mrids)


def test_encode_fsa_mrid():
    scope1 = generate_class_instance(BaseRequestScope, seed=1, iana_pen=123)
    scope2 = generate_class_instance(BaseRequestScope, seed=1, iana_pen=456)

    all_generated_mrids = []

    for scope in [scope1, scope2]:
        assert_and_append_mrid(MridMapper.encode_function_set_assignment_mrid(scope, 0, 0), all_generated_mrids)
        assert_and_append_mrid(MridMapper.encode_function_set_assignment_mrid(scope, 123, 456), all_generated_mrids)
        assert_and_append_mrid(
            MridMapper.encode_function_set_assignment_mrid(scope, MAX_INT_32, MAX_INT_32), all_generated_mrids
        )
        assert_and_append_mrid(
            MridMapper.encode_function_set_assignment_mrid(scope, 111, MAX_INT_32), all_generated_mrids
        )
        assert_and_append_mrid(
            MridMapper.encode_function_set_assignment_mrid(scope, MAX_INT_32, 222), all_generated_mrids
        )

    assert len(all_generated_mrids) == len(set(all_generated_mrids)), "Each MRID should be unique"
    assert all(decode_mrid_type(m) == MridType.FUNCTION_SET_ASSIGNMENT for m in all_generated_mrids)


def test_encode_tariff_profile_mrid():
    scope1 = generate_class_instance(BaseRequestScope, seed=1, iana_pen=123)
    scope2 = generate_class_instance(BaseRequestScope, seed=1, iana_pen=456)

    all_generated_mrids = []

    for scope in [scope1, scope2]:
        assert_and_append_mrid(MridMapper.encode_tariff_profile_mrid(scope, 0), all_generated_mrids)
        assert_and_append_mrid(MridMapper.encode_tariff_profile_mrid(scope, 123), all_generated_mrids)
        assert_and_append_mrid(MridMapper.encode_tariff_profile_mrid(scope, MAX_INT_32), all_generated_mrids)

    assert len(all_generated_mrids) == len(set(all_generated_mrids)), "Each MRID should be unique"
    assert all(decode_mrid_type(m) == MridType.TARIFF for m in all_generated_mrids)


def test_encode_rate_component_mrid():
    scope1 = generate_class_instance(BaseRequestScope, seed=1, iana_pen=123)
    scope2 = generate_class_instance(BaseRequestScope, seed=1, iana_pen=456)

    all_generated_mrids = []

    for scope, tariff_id, site_id, timestamp, prt in product(
        [scope1, scope2],
        [0, 123, MAX_INT_32],
        [0, 123, MAX_INT_32],
        [
            datetime(2000, 1, 1, tzinfo=timezone.utc),
            datetime(2000, 1, 1, tzinfo=timezone.utc) - timedelta(minutes=1),
            datetime(2000, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=1),
            datetime(2000, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=MAX_INT_26 - 1),
        ],
        PricingReadingType,
    ):
        assert_and_append_mrid(
            MridMapper.encode_rate_component_mrid(scope, tariff_id, site_id, timestamp, prt),
            all_generated_mrids,
        )

    assert len(all_generated_mrids) == len(set(all_generated_mrids)), "Each MRID should be unique"
    assert all(decode_mrid_type(m) == MridType.RATE_COMPONENT for m in all_generated_mrids)


def test_encode_rate_component_mrid_bad_pricing_reading_type():
    """Checks that invalid values for pricing_reading_type raise ValueError"""
    scope = generate_class_instance(BaseRequestScope)
    tariff_id = 1
    site_id = 2
    timestamp = datetime(2024, 1, 2, tzinfo=timezone.utc)

    # Valid values to act as a sanity check - these should all be OK
    assert_mrid(MridMapper.encode_rate_component_mrid(scope, tariff_id, site_id, timestamp, 1))
    assert_mrid(MridMapper.encode_rate_component_mrid(scope, tariff_id, site_id, timestamp, 2))
    assert_mrid(MridMapper.encode_rate_component_mrid(scope, tariff_id, site_id, timestamp, 3))
    assert_mrid(MridMapper.encode_rate_component_mrid(scope, tariff_id, site_id, timestamp, 4))

    # This is our actual tests for out of range values
    with pytest.raises(ValueError):
        MridMapper.encode_rate_component_mrid(scope, tariff_id, site_id, timestamp, 0)
    with pytest.raises(ValueError):
        MridMapper.encode_rate_component_mrid(scope, tariff_id, site_id, timestamp, -1)
    with pytest.raises(ValueError):
        MridMapper.encode_rate_component_mrid(scope, tariff_id, site_id, timestamp, 5)  # Too high


def test_encode_response_set_mrid():
    scope1 = generate_class_instance(BaseRequestScope, seed=1, iana_pen=123)
    scope2 = generate_class_instance(BaseRequestScope, seed=1, iana_pen=456)

    all_mrids = []
    for r in ResponseSetType:
        for scope in [scope1, scope2]:
            assert_and_append_mrid(MridMapper.encode_response_set_mrid(scope, r), all_mrids)

    assert len(all_mrids) == len(set(all_mrids)), "Each MRID should be unique"


def test_encode_time_tariff_interval_mrid():
    scope1 = generate_class_instance(BaseRequestScope, seed=1, iana_pen=123)
    scope2 = generate_class_instance(BaseRequestScope, seed=1, iana_pen=456)

    all_generated_mrids = []

    for scope, time_tariff_interval_id, prt in product(
        [scope1, scope2],
        [0, 123, MAX_INT_32, MAX_INT_64],
        PricingReadingType,
    ):
        assert_and_append_mrid(
            MridMapper.encode_time_tariff_interval_mrid(scope, time_tariff_interval_id, prt),
            all_generated_mrids,
        )

    assert len(all_generated_mrids) == len(set(all_generated_mrids)), "Each MRID should be unique"
    assert all(decode_mrid_type(m) == MridType.TIME_TARIFF_INTERVAL for m in all_generated_mrids)


def test_encode_time_tariff_interval_mrid_bad_pricing_reading_type():
    """Checks that invalid values for pricing_reading_type raise ValueError"""
    scope = generate_class_instance(BaseRequestScope)
    tariff_generated_rate_id = 1

    # Valid values to act as a sanity check - these should all be OK
    assert_mrid(MridMapper.encode_time_tariff_interval_mrid(scope, tariff_generated_rate_id, 1))
    assert_mrid(MridMapper.encode_time_tariff_interval_mrid(scope, tariff_generated_rate_id, 2))
    assert_mrid(MridMapper.encode_time_tariff_interval_mrid(scope, tariff_generated_rate_id, 3))
    assert_mrid(MridMapper.encode_time_tariff_interval_mrid(scope, tariff_generated_rate_id, 4))

    # This is our actual tests for out of range values
    with pytest.raises(ValueError):
        MridMapper.encode_time_tariff_interval_mrid(scope, tariff_generated_rate_id, 0)
    with pytest.raises(ValueError):
        MridMapper.encode_time_tariff_interval_mrid(scope, tariff_generated_rate_id, -1)
    with pytest.raises(ValueError):
        MridMapper.encode_time_tariff_interval_mrid(scope, tariff_generated_rate_id, 5)  # Too high


def test_decode_and_validate_mrid_type():
    """Validates that decode_and_validate_mrid_type works for the various encodings"""

    # This does the body of the test - just need to inject the ability to generate a MRID for a given scope
    def do_test(encode: Callable[[BaseRequestScope], str]):
        scope1 = generate_class_instance(BaseRequestScope, iana_pen=11)
        scope2 = generate_class_instance(BaseRequestScope, iana_pen=22)

        mrid1 = encode(scope1)
        assert_mrid(mrid1)

        # Return value looks OK when run normally
        mrid_type = MridMapper.decode_and_validate_mrid_type(scope1, mrid1)
        assert isinstance(mrid_type, MridType)
        assert mrid_type == decode_mrid_type(mrid1)

        # Ensure IANA PEN is validated
        with pytest.raises(ValueError):
            # This is using a different scope (pen) and is therefore an error
            MridMapper.decode_and_validate_mrid_type(scope2, mrid1)

    do_test(lambda s: MridMapper.encode_default_doe_mrid(s))
    do_test(lambda s: MridMapper.encode_doe_program_mrid(s, 1, 2))
    do_test(lambda s: MridMapper.encode_doe_mrid(s, 1))
    do_test(lambda s: MridMapper.encode_function_set_assignment_mrid(s, 1, 2))
    do_test(
        lambda s: MridMapper.encode_rate_component_mrid(
            s, 1, 2, datetime(2021, 2, 3, tzinfo=timezone.utc), PricingReadingType.EXPORT_REACTIVE_POWER_KVARH
        )
    )
    do_test(lambda s: MridMapper.encode_time_tariff_interval_mrid(s, 1, PricingReadingType.EXPORT_REACTIVE_POWER_KVARH))
    do_test(lambda s: MridMapper.encode_tariff_profile_mrid(s, 1))
    do_test(lambda s: MridMapper.encode_response_set_mrid(s, 1))


@pytest.mark.parametrize("doe_id", [0, MAX_INT_32, MAX_INT_64, 123, 4])
def test_decode_doe_mrid(doe_id: int):
    scope = generate_class_instance(BaseRequestScope)
    mrid = MridMapper.encode_doe_mrid(scope, doe_id)
    assert_mrid(mrid)
    decoded_id = MridMapper.decode_doe_mrid(mrid)

    assert isinstance(decoded_id, int)
    assert decoded_id == doe_id


@pytest.mark.parametrize("rate_id, prt", product([0, MAX_INT_32, MAX_INT_64, 123, 4], PricingReadingType))
def test_decode_time_tariff_interval_mrid(rate_id: int, prt: PricingReadingType):
    scope = generate_class_instance(BaseRequestScope)
    mrid = MridMapper.encode_time_tariff_interval_mrid(scope, rate_id, prt)
    assert_mrid(mrid)
    decoded_prt, decoded_id = MridMapper.decode_time_tariff_interval_mrid(mrid)

    assert isinstance(decoded_id, int)
    assert isinstance(decoded_prt, PricingReadingType)
    assert decoded_id == rate_id
    assert decoded_prt == prt
