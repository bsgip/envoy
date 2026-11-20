import pytest

from envoy.server.mapper.nmi import combine_nmi, split_nmi


@pytest.mark.parametrize(
    "nmi, expected",
    [
        (None, (None, None)),
        ("", ("", None)),
        ("abc", ("abc", None)),
        ("1234567890", ("1234567890", None)),
        ("12345678901", ("1234567890", "1")),
        ("123456789012", ("1234567890", "12")),  # Too long for DB - will fail on write (as it did previously)
    ],
)
def test_split_nmi(nmi: str | None, expected: tuple[str | None, str | None]):
    assert split_nmi(nmi) == expected


@pytest.mark.parametrize(
    "nmi, nmi_checksum, expected",
    [
        (None, None, None),
        ("", None, ""),
        ("abc", None, "abc"),
        ("1234567890", None, "1234567890"),
        ("1234567890", "1", "12345678901"),
        ("1234567890", "", "1234567890"),
    ],
)
def test_combine_nmi(nmi: str | None, nmi_checksum: str | None, expected: str | None):
    assert combine_nmi(nmi, nmi_checksum) == expected


@pytest.mark.parametrize("nmi", [None, "", "abc", "1234567890", "12345678901"])
def test_split_combine_roundtrip(nmi: str | None):
    assert combine_nmi(*split_nmi(nmi)) == nmi
