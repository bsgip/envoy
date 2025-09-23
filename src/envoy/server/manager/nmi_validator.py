"""Validation logic for ConnectionPoint.id

NOTE: it may have been more consistent to embed this in the pydantic model
but the pattern for runtime model configurations is clunky so a custom approach
was taken.
"""

from enum import Enum
import logging
import re


logger = logging.getLogger(__name__)


class PatternGroup(tuple[str, ...]):
    """Represents a group of regex patterns that must all match (AND logic)."""

    def __new__(cls, *patterns: str) -> "PatternGroup":
        """Create a PatternGroup, ensuring all items are strings."""
        if not all(isinstance(p, str) for p in patterns):
            raise TypeError("All elements of a PatternGroup must be strings")
        return super().__new__(cls, patterns)


PatternGroups = list[PatternGroup]  # or operation across groups


class MultiPatternRegexValidator:
    """String validator using multiple inclusion and exclusion regular-expression
    patterns.

    Although a single regex can technically combine multiple constraints, this approach is often less readable,
    testable and maintainable.
    """

    def __init__(self, includes: PatternGroups, excludes: PatternGroups) -> None:
        self.includes: PatternGroups = includes
        self.excludes: PatternGroups = excludes

    @staticmethod
    def _match_pattern_group(target: str, pattern_group: PatternGroup) -> bool:
        """Check if all patterns in a group match the target string."""
        if not isinstance(pattern_group, PatternGroup):
            raise TypeError(f"Expecting {PatternGroup.__class__}")
        # Must match all within a single group
        for pattern in pattern_group:
            if re.search(pattern, target) is None:
                return False
        return True

    def validate(self, target: str) -> bool:
        """Validate the target string against inclusion and exclusion rules.

        Returns True if it matches at least one include group and no exclude groups.
        """
        # if empty includes list, then defaulting to matched=True
        inclusion_matched: bool = True
        for pattern_group in self.includes:
            if self._match_pattern_group(target, pattern_group):
                inclusion_matched = True
                break
            inclusion_matched = False
        logger.debug(f"includes matched: {inclusion_matched}")

        # empty excludes, defaulting to matched=False
        exclusion_matched: bool = False
        for pattern_group in self.excludes:
            if self._match_pattern_group(target, pattern_group):
                exclusion_matched = True
                break
        logger.debug(f"excludes matched: {exclusion_matched}")
        return inclusion_matched and not exclusion_matched


class DNSPParticipantId(str, Enum):
    # ACT
    EvoEnergy = "ACTEWP"

    # NSW
    EssentialEnergy = "CNRGYP"
    Ausgrid = "ENERGYAP"
    EndeavourEnergy = "INTEGP"

    # QLD
    Energex = "ENERGEXP"
    ErgonEnergy = "ERGONETP"

    # SA
    SAPN = "UMPLP"

    # TAS
    TasNetworks = "AURORAP"

    # VIC
    CitiPower = "CITIPP"
    Powercor = "POWCP"
    Jemena = "SOLARISP"
    AusnetServices = "EASTERN"
    UnitedEnergy = "UNITED"

    # NT
    PowerAndWaterCorporation = "PWCLNSP"

    # WA - NOTE: not true participant IDs
    WesternPower = "WAAA"
    HorizonPower = "8021"


class NmiValidator(MultiPatternRegexValidator):
    """NMI validation based on the AEMO NMI Allocation list."""

    GLOBAL_EXCLUDES = [
        PatternGroup(
            r"\s",  # no whitespace
        ),
        PatternGroup(
            r"[OI]",  # exclude 'O' and 'I'
        ),
    ]

    # NOTE:Based on AEMO's NMI Allocation List Version 13 - November 2022
    # (https://www.aemo.com.au/-/media/Files/Electricity/NEM/Retail_and_Metering/Metering-Procedures/NMI-Allocation-List.pdf)
    DNSP_PATTERNS = {
        DNSPParticipantId.EvoEnergy: {
            "includes": [PatternGroup(r"^NGGG[0-9A-Z]{6}$"), PatternGroup(r"^7001\d{6}$")],
            "excludes": [
                PatternGroup(
                    r"^.{4}W",
                )
            ],
        },
        DNSPParticipantId.EssentialEnergy: {
            "includes": [
                PatternGroup(r"^NAAA[0-9A-Z]{6}$"),
                PatternGroup(r"^NBBB[0-9A-Z]{6}$"),
                PatternGroup(r"^NEEE[0-9A-Z]{6}$"),
                PatternGroup(r"^NFFF[0-9A-Z]{6}$"),
                PatternGroup(r"^4001\d{6}$"),
                PatternGroup(r"^45080\d{5}$"),
                PatternGroup(r"^4204\d{6}$"),
                PatternGroup(r"^4407\d{6}"),
            ],
            "excludes": [
                PatternGroup(
                    r"^.{4}W",
                ),
            ],
        },
        DNSPParticipantId.Ausgrid: {
            "includes": [PatternGroup(r"^NCCC[0-9A-Z]{6}$"), PatternGroup(r"^410[2-4][0-9A-Z]{6}$")],
            "excludes": [
                PatternGroup(
                    r"^.{4}W",
                )
            ],
        },
        DNSPParticipantId.EndeavourEnergy: {
            "includes": [
                PatternGroup(r"^NDDD[0-9A-Z]{6}$"),
                PatternGroup(r"^431\d{7}"),
            ],
            "excludes": [
                PatternGroup(
                    r"^.{4}W",
                )
            ],
        },
        DNSPParticipantId.PowerAndWaterCorporation: {
            "includes": [
                PatternGroup(
                    r"^250\d{7}$",
                )
            ],
            "excludes": [],
        },
        DNSPParticipantId.ErgonEnergy: {
            "includes": [
                PatternGroup(r"^QAAA[0-9A-Z]{6}$"),
                PatternGroup(r"^QCCC[0-9A-Z]{6}$"),
                PatternGroup(r"^QDDD[0-9A-Z]{6}$"),
                PatternGroup(r"^QEEE[0-9A-Z]{6}$"),
                PatternGroup(r"^QFFF[0-9A-Z]{6}$"),
                PatternGroup(r"^QGGG[0-9A-Z]{6}$"),
                PatternGroup(r"^30\d{8}$"),
            ],
            "excludes": [
                PatternGroup(
                    r"^.{4}W",
                )
            ],
        },
        DNSPParticipantId.Energex: {
            "includes": [PatternGroup(r"^QB\d{2}[0-9A-Z]{6}$"), PatternGroup(r"^31\d{8}$")],
            "excludes": [
                PatternGroup(
                    r"^.{4}W",
                )
            ],
        },
        DNSPParticipantId.SAPN: {
            "includes": [
                PatternGroup(r"^SAAA[0-9A-Z]{6}$"),
                PatternGroup(r"^SASMPL\d{4}$"),
                PatternGroup(r"^200[1-2]\d{6}$"),
            ],
            "excludes": [
                PatternGroup(
                    r"^.{4}W",
                )
            ],
        },
        DNSPParticipantId.TasNetworks: {
            "includes": [
                PatternGroup(
                    r"^T\d{9}$",
                )
            ],
            "excludes": [],
        },
        DNSPParticipantId.CitiPower: {
            "includes": [PatternGroup(r"^VAAA[0-9A-Z]{6}$"), PatternGroup(r"^610[2-3]\d{6}$")],
            "excludes": [
                PatternGroup(
                    r"^.{4}W",
                )
            ],
        },
        DNSPParticipantId.AusnetServices: {
            "includes": [PatternGroup(r"^VBBB[0-9A-Z]{6}$"), PatternGroup(r"^630[5-6]\d{6}$")],
            "excludes": [
                PatternGroup(
                    r"^.{4}W",
                )
            ],
        },
        DNSPParticipantId.Powercor: {
            "includes": [PatternGroup(r"^VCCC[0-9A-Z]{6}$"), PatternGroup(r"^620[3-4]\d{6}$")],
            "excludes": [
                PatternGroup(
                    r"^.{4}W",
                )
            ],
        },
        DNSPParticipantId.Jemena: {
            "includes": [PatternGroup(r"^VDDD[0-9A-Z]{6}$"), PatternGroup(r"^6001\d{6}$")],
            "excludes": [
                PatternGroup(
                    r"^.{4}W",
                )
            ],
        },
        DNSPParticipantId.UnitedEnergy: {
            "includes": [PatternGroup(r"^VEEE[0-9A-Z]{6}$"), PatternGroup(r"^640[7-8]\d{6}$")],
            "excludes": [
                PatternGroup(
                    r"^.{4}W",
                )
            ],
        },
        DNSPParticipantId.WesternPower: {
            "includes": [
                PatternGroup(r"^WAAA[0-9A-Z]{6}$"),
                PatternGroup(r"^8001\d{6}$"),
                PatternGroup(r"^8020\d{6}$"),
            ],
            "excludes": [
                PatternGroup(
                    r"^.{4}W",
                )
            ],
        },
        DNSPParticipantId.HorizonPower: {
            "includes": [
                PatternGroup(
                    r"^8021{6}$",
                )
            ],
            "excludes": [],
        },
    }

    def __init__(
        self,
        participant_id: DNSPParticipantId,
        extra_includes: PatternGroups | None = None,
        extra_excludes: PatternGroups | None = None,
    ) -> None:
        """Init validator for a specific DNSP participant, can provide custom validation rules.

        Parameters:
        - participant_id: The DNSPParticipantId to validate against.
        - extra_includes: Additional include pattern groups.
        - extra_excludes: Additional exclude pattern groups.
        """
        self.participant_id = participant_id
        nsp_config = self.DNSP_PATTERNS[participant_id]
        self._resolved_includes = (extra_includes or []) + nsp_config.get("includes", [])
        self._resolved_excludes = (extra_excludes or []) + nsp_config.get("excludes", [])

        super().__init__(
            includes=self._resolved_includes,
            excludes=self._resolved_excludes + self.GLOBAL_EXCLUDES,
        )

    def validate(self, nmi: str) -> bool:
        """Validate an 11-character NMI against structure, pattern, and checksum."""
        if len(nmi) != 11:
            logger.debug("Failed validation - expected 11 characters.")
            return False

        if not super().validate(nmi[:10]):
            return False
        return self._validate_checksum(nmi)

    @classmethod
    def _validate_checksum(cls, nmi: str) -> bool:
        """Validate the NMI checksum character using Luhn-10 logic."""
        checksum_char = nmi[-1]
        if not checksum_char.isdigit():
            logger.debug("Failed validation - expected digit checksum.")
            return False
        checksum_digit = int(checksum_char)

        return checksum_digit == cls._luhn_10_using_ascii_codes(nmi[:10])

    @staticmethod
    def _luhn_10_using_ascii_codes(nmi_10: str) -> int:
        """Calculate the Luhn-10 checksum for a 10-character NMI string based on ASCII values. As described in
        Appendix 2. of AEMO's National Metering Identifier Procedure V5.1 Document
            found here:
        (https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Retail-and-metering/-/media/EBA9363B984841079712B3AAD374A859.ashx)
        """
        if len(nmi_10) != 10:
            raise ValueError("Expecting 10-char input")

        # Step 2. Read the NMI character by character, starting with the right most character.
        # Step 3. Convert the character to its ASCII value
        values = [ord(c) for c in nmi_10]
        values.reverse()

        # Step 4. Double the ASCII value if the character is the right most of the NMI or an alternate.
        alternate_doubled_values = [v * 2 if i % 2 == 0 else v for i, v in enumerate(values)]

        # Step 5. Add the individual digits of the ASCII value to the Total
        total_per_digit_sum = sum(int(c) for v in alternate_doubled_values for c in str(v))

        # The next highest multiple of 10 minus the value from step 5. is the checksum
        return (10 - (total_per_digit_sum % 10)) % 10
