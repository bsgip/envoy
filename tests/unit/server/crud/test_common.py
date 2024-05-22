import pytest

from envoy.server.crud.common import convert_lfdi_to_sfdi, sum_digits
from tests.data.certificates import certificate1, certificate2, certificate3, certificate4, certificate5


@pytest.mark.parametrize("n, expected", [(1, 1), (0, 0), (8, 8), (11, 2), (456, 15), (100001, 2)])
def test_sum_digits(n, expected):
    assert sum_digits(n) == expected
    assert sum_digits(-n) == expected, "Digit sum should be independent of sign"


@pytest.mark.parametrize(
    "lfdi, expected_sfdi",
    [
        ("3e4f45ab31edfe5b67e343e5e4562e31984e23e5", 167261211391),  # From 2030.5 standard example
        (certificate1.TEST_CERTIFICATE_LFDI, int(certificate1.TEST_CERTIFICATE_SFDI)),
        (certificate2.TEST_CERTIFICATE_LFDI, int(certificate2.TEST_CERTIFICATE_SFDI)),
        (certificate3.TEST_CERTIFICATE_LFDI, int(certificate3.TEST_CERTIFICATE_SFDI)),
        (certificate4.TEST_CERTIFICATE_LFDI, int(certificate4.TEST_CERTIFICATE_SFDI)),
        (certificate5.TEST_CERTIFICATE_LFDI, int(certificate5.TEST_CERTIFICATE_SFDI)),
    ],
)
def test_convert_lfdi_to_sfdi(lfdi: str, expected_sfdi: int):
    assert convert_lfdi_to_sfdi(lfdi) == expected_sfdi


@pytest.mark.parametrize(
    "invalid_lfdi",
    [
        "",  # Empty string
        "0x123123fff",  # Too short, lfdi should be 40 hex characters and a minimum of 10 hex chars to be convertible
        "FFFF",  # Too short, lfdi should be 40 hex characters and a minimum of 10 hex chars to be convertible
    ],
)
def test_convert_lfdi_to_sfdi__raises_exception(invalid_lfdi: str):
    with pytest.raises(ValueError):
        _ = convert_lfdi_to_sfdi(invalid_lfdi)
