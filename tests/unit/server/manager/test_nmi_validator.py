import pytest

from envoy.server.manager.nmi_validator import NmiValidator, MultiPatternRegexValidator, PatternGroup


@pytest.mark.parametrize(
    "includes, excludes, input_str, expected",
    [
        (
            [PatternGroup(r"\d+", r"[a-zA-Z]+")],
            [
                PatternGroup(
                    r"[^a-zA-Z0-9]",
                )
            ],
            "abc123",
            True,
        ),  # valid input
        ([PatternGroup(r"\d+", r"[a-z]+")], [], "123", False),  # missing lowercase letters
        (
            [
                PatternGroup(
                    r"\w+",
                )
            ],
            [
                PatternGroup(
                    r"\s",
                )
            ],
            "hello world",
            False,
        ),  # contains space
        ([], [], "", True),  # no includes or excludes
        (
            [],
            [
                PatternGroup(
                    r"bad",
                )
            ],
            "this is bad",
            False,
        ),  # matches exclusion
        (
            [],
            [
                PatternGroup(
                    r"bad",
                )
            ],
            "this is good",
            True,
        ),  # does not match exclusion
        ([PatternGroup(r"foo", r"bar")], [], "foo bar", True),  # matches all includes
        ([PatternGroup(r"foo", r"bar")], [], "foo baz", False),  # missing one include
    ],
)
def test_multi_pattern_regex_validator(includes, excludes, input_str, expected):
    """Basic logic tests"""
    validator = MultiPatternRegexValidator(includes=includes, excludes=excludes)
    assert validator.validate(input_str) == expected


# Examples from Appendix 3. of AEMO's National Metering Identifier Procedure V5.1 Document
#        found here:
# (https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Retail-and-metering/-/media/EBA9363B984841079712B3AAD374A859.ashx)
@pytest.mark.parametrize(
    "target, expected",
    [
        ("1234C6789A", 3),
        ("2001985732", 8),
        ("2001985733", 6),
        ("3075621875", 8),
        ("3075621876", 6),
        ("4316854005", 9),
        ("4316854006", 7),
        ("6305888444", 6),
        ("6350888444", 2),
        ("7001888333", 8),
        ("7102000001", 7),
        ("NAAAMYS582", 6),
        ("NBBBX11110", 0),
        ("NBBBX11111", 8),
        ("NCCC519495", 5),
        ("NGGG000055", 4),
        ("QAAAVZZZZZ", 3),
        ("QCDWW00010", 2),
        ("SMVEW00085", 8),
        ("VAAA000065", 7),
        ("VAAA000066", 5),
        ("VAAA000067", 2),
        ("VAAASTY576", 8),
        ("VCCCX00009", 1),
        ("VEEEX00009", 1),
        ("VKTS786150", 2),
        ("VKTS867150", 5),
        ("VKTS871650", 7),
        ("VKTS876105", 7),
        ("VKTS876150", 3),
        ("VKTS876510", 8),
    ],
)
def test_luhn_10_using_ascii_codes(target: str, expected: int):
    assert NmiValidator._luhn_10_using_ascii_codes(target) == expected


@pytest.mark.parametrize(
    "participant_id, nmi, expected",
    [
        ("ACTEWP", "NGGG1234561", True),  # Valid Evoenergy NMI
        ("ACTEWP", "70011234564", True),  # Valid Evoenergy NMI
        ("ACTEWP", "70111234564", False),  # Invalid Evoenergy NMI
        ("ACTEWP", "70011234565", False),  # Invalid Evoenergy NMI
        ("CNRGYP", "NAAA1234564", True),  # Valid Essential Energy NMI
        ("CNRGYP", "45080000009", True),  # Valid Essential Energy NMI
        ("CNRGYP", "45080000003", False),  # invalid Essential Energy NMI
        ("CNRGYP", "45180000009", False),  # invalid Essential Energy NMI
        ("ENERGYAP", "NCCC1234564", True),  # Valid Ausgrid NMI
        ("ENERGYAP", "41020000002", True),  # Valid Ausgrid NMI
        ("ENERGYAP", "41020000003", False),  # Invalid Ausgrid NMI
        ("ENERGYAP", "41220000009", False),  # Invalid Ausgrid NMI
        ("INTEGP", "NDDD1234569", True),  # Valid Endeavour Energy NMI
        ("ERGONETP", "QAAA1234560", True),  # Valid Ergon Energy NMI
        ("ENERGEXP", "QB121234569", True),  # Valid ENERGEX NMI
        ("ENERGYAP", "NCCCW123452", False),  # Contains 'W' in 5th position
        ("INTEGP", "NDDD12345OI", False),  # Contains 'O' and 'I'
        ("ERGONETP", "QAAA12345", False),  # Too short
        ("ENERGEXP", "QB12123456Z", False),  # Invalid checksum type
        ("ENERGEXP", "QB121234561", False),  # Invalid checksum val
    ],
)
def test_nmi_validator(participant_id: str, nmi: str, expected: bool):
    validator = NmiValidator(participant_id)
    result = validator.validate(nmi)
    assert result == expected
