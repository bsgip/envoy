import pytest

from envoy.server.crud.common import convert_lfdi_to_sfdi
from tests.data.certificates import certificate1, certificate2, certificate3, certificate4, certificate5


@pytest.mark.parametrize(
    "lfdi, expected_sfdi",
    [
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
