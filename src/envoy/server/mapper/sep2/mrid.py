from datetime import datetime, timezone

from envoy.server.mapper.constants import MridType, PricingReadingType, ResponseSetType
from envoy.server.request_scope import BaseRequestScope

# constant maximum values for the various mrid components (max values for an unsigned int representation)
MAX_IANA_PEN = pow(2, 32) - 1  # 32 bits
MAX_MRID_ID = pow(2, 92) - 1  # 92 bits
MAX_MRID_TYPE = pow(2, 4) - 1  # 4 bits
MAX_INT_26 = pow(2, 26) - 1
MAX_INT_32 = pow(2, 32) - 1
MAX_INT_64 = pow(2, 64) - 1

# Constants associated with certain mrid types
DEFAULT_DOE_ID = int("defa017", 16)
DER_PROGRAM_PREFIX_DOE = int("d0e", 16) << (92 - 12)  # Sets the high 12 bits for an id
RATE_COMPONENT_EPOCH = datetime(2000, 1, 1, tzinfo=timezone.utc)


def encode_mrid(mrid_type: MridType, id: int, iana_pen: int) -> str:
    """An mrid is 16 bytes (128 bit) encoded as a hexadecimal string.

    sep2 describes an mrid as a combination of an IANA PEN (lowest 32 bits) and the remaining 96 bits are an
    implementation specific unique ID

    This function will encode the following MRID format from LSB to MSB

    Bits 0-31 (32 bits): IANA Pen
    Bytes 32-123 (92 bits): Unique ID identifying the source record primary key
    Byte 124-127 (4 bits) mrid_type byte

    Will return a hex encoded mrid string like: 'abbbbbbbbbbbbbbbbbbbbbbbcccccccc' with:
        "a" representing the mrid type
        "b" representing the id
        "c" representing the iana_pen

    mrid_type:  (4 bits) Unsigned int - What is this mrid representing?
    id:  (92 bits) Unsigned int - an mrid_type specific value
    iana_pen: (32 bits) Unsigned int - The IANA Private Enterprise Number of the org hosting this server"""

    if iana_pen < 0 or iana_pen > MAX_IANA_PEN:
        raise ValueError(f"iana_pen {iana_pen} is not in the range 0 -> {MAX_IANA_PEN}")

    if id < 0 or id > MAX_MRID_ID:
        raise ValueError(f"id {id} is not in the range 0 -> {MAX_MRID_ID}")

    mrid_type_int = int(mrid_type)
    if mrid_type_int < 0 or mrid_type_int > MAX_MRID_TYPE:
        raise ValueError(f"mrid_type {mrid_type_int} is not in the range 0 -> {MAX_MRID_TYPE}")

    return f"{mrid_type_int:x}{id:023x}{iana_pen:08x}"


def decode_mrid_type(mrid: str) -> MridType:
    """Given the output of encode_mrid - Returns the MridType that was passed to the original call
    by decoding the highest 4 bits of the hex string.

    Raises a ValueError if mrid is not formatted correctly"""
    if len(mrid) != 32:
        raise ValueError(f"Expected a mrid in the form of a string. Got '{mrid}' instead")

    return MridType(int(mrid[0], 16))


def decode_mrid_id(mrid: str) -> int:
    """Given the output of encode_mrid - Returns the id that was passed to the original call
    by decoding the middle 92 bits of the hex string.

    Raises a ValueError if mrid is not formatted correctly"""
    if len(mrid) != 32:
        raise ValueError(f"Expected a mrid in the form of a string. Got '{mrid}' instead")

    return int(mrid[1:24], 16)


def decode_iana_pen(mrid: str) -> int:
    """Given the output of encode_mrid - Returns the iana_pen that was passed to the original call
    by decoding the middle 92 bits of the hex string.

    Raises a ValueError if mrid is not formatted correctly"""
    if len(mrid) != 32:
        raise ValueError(f"Expected a mrid in the form of a string. Got '{mrid}' instead")

    return int(mrid[24:], 16)


class MridMapper:

    @staticmethod
    def encode_default_doe_mrid(scope: BaseRequestScope) -> str:
        """Encodes a valid MRID for representing the default DOE"""
        return encode_mrid(MridType.DEFAULT_DOE, DEFAULT_DOE_ID, scope.iana_pen)

    @staticmethod
    def encode_doe_program_mrid(scope: BaseRequestScope, site_id: int) -> str:
        """Encodes a valid MRID for a DOE program scoped to the specified site_id

        site_id: max value is expected to be a 32 bit unsigned int."""
        return encode_mrid(MridType.DER_PROGRAM, DER_PROGRAM_PREFIX_DOE | (site_id & MAX_INT_32), scope.iana_pen)

    @staticmethod
    def encode_doe_mrid(scope: BaseRequestScope, dynamic_operating_envelope_id: int) -> str:
        """Encodes a valid MRID for a specific DOE.

        dynamic_operating_envelope_id: max value is expected to be a 64 bit unsigned int."""
        return encode_mrid(
            MridType.DYNAMIC_OPERATING_ENVELOPE, dynamic_operating_envelope_id & MAX_INT_64, scope.iana_pen
        )

    @staticmethod
    def encode_function_set_assignment_mrid(scope: BaseRequestScope, site_id: int, fsa_id: int) -> str:
        """Encodes a valid MRID for a specific function set assignment.

        site_id: max value is expected to be a 32 bit unsigned int.
        fas_id: max value is expected to be a 32 bit unsigned int."""

        id = ((site_id & MAX_INT_32) << 32) | (fsa_id & MAX_INT_32)
        return encode_mrid(MridType.FUNCTION_SET_ASSIGNMENT, id, scope.iana_pen)

    @staticmethod
    def encode_mirror_usage_point_mrid(scope: BaseRequestScope, site_reading_type_id: int) -> str:
        """Encodes a valid MRID for a specific mirror usage point.

        site_reading_type_id: max value is expected to be a 32 bit unsigned int."""
        return encode_mrid(MridType.MIRROR_USAGE_POINT, site_reading_type_id & MAX_INT_32, scope.iana_pen)

    @staticmethod
    def encode_mirror_meter_reading_mrid(scope: BaseRequestScope, site_reading_type_id: int) -> str:
        """Encodes a valid MRID for a specific mirror meter reading.

        site_reading_type_id: max value is expected to be a 32 bit unsigned int."""
        return encode_mrid(MridType.MIRROR_METER_READING, site_reading_type_id & MAX_INT_32, scope.iana_pen)

    @staticmethod
    def encode_tariff_profile_mrid(scope: BaseRequestScope, tariff_id: int) -> str:
        """Encodes a valid MRID for a specific tariff profile.

        tariff_id: max value is expected to be a 32 bit unsigned int."""
        return encode_mrid(MridType.TARIFF, tariff_id & MAX_INT_32, scope.iana_pen)

    @staticmethod
    def encode_rate_component_mrid(
        scope: BaseRequestScope,
        tariff_id: int,
        site_id: int,
        start_timestamp: datetime,
        pricing_reading_type: PricingReadingType,
    ) -> str:
        """Encodes a valid MRID for a specific rate component. Rate components don't have a relevant primary key
        in our DB model so this is derived from other values.

        tariff_id: max value is expected to be a 32 bit unsigned int.
        site_id: max value is expected to be a 32 bit unsigned int.
        start_timestamp: Must be timezone aware - will only consider this value down to the minute resolution
        pricing_reading_type: Only supports a maximum of 4 unique values"""

        # We have 92 bits to encode an ID

        # 32 bits tariff ID
        # 32 bits site id
        # 2 bits pricing_reading_type
        # 26 bits timestamp (encoded as MINUTES since unix epoch)

        prt_int = int(pricing_reading_type) - 1
        if prt_int < 0 or prt_int >= 4:
            raise ValueError(f"Invalid PricingReadingType value of {prt_int}. Expected a value in range [0, 3]")

        tariff_shifted = tariff_id << 60
        site_id_shifted = site_id << 28
        prt_shifted = prt_int << 26

        # Minutes since epoch - gives us ~127 years until we rollover if we are only encoding 26 bits
        # Do a modulo first so we can also cleanly rollover dates prior to the epoch
        total_minutes_clamped = (int((start_timestamp - RATE_COMPONENT_EPOCH).total_seconds()) // 60) % (MAX_INT_26 + 1)
        timestamp_shifted = total_minutes_clamped & MAX_INT_26

        id = tariff_shifted | site_id_shifted | prt_shifted | timestamp_shifted
        return encode_mrid(MridType.RATE_COMPONENT, id, scope.iana_pen)

    @staticmethod
    def encode_time_tariff_interval_mrid(
        scope: BaseRequestScope, tariff_generated_rate_id: int, pricing_reading_type: PricingReadingType
    ) -> str:
        """Encodes a valid MRID for a specific tariff generated rate

        tariff_generated_rate_id: max value is expected to be a 64 bit unsigned int.
        pricing_reading_type: Only supports a maximum of 4 unique values"""

        # Top 2 bits are for pricing reading type
        # Remaining 90 bits are for tariff_generated_rate_id (which will use at most 64)
        prt_int = int(pricing_reading_type) - 1
        if prt_int < 0 or prt_int >= 4:
            raise ValueError(f"Invalid PricingReadingType value of {prt_int}. Expected a value in range [0, 3]")

        id = (prt_int << 90) | (tariff_generated_rate_id & MAX_INT_64)
        return encode_mrid(MridType.TIME_TARIFF_INTERVAL, id, scope.iana_pen)

    @staticmethod
    def encode_response_set_mrid(scope: BaseRequestScope, response_set_type: ResponseSetType) -> str:
        """Encodes a valid MRID for a specific response set.

        response_set_type: max value is expected to be a 32 bit unsigned int."""
        return encode_mrid(MridType.RESPONSE_SET, int(response_set_type) & MAX_INT_32, scope.iana_pen)

    @staticmethod
    def decode_and_validate_mrid_type(scope: BaseRequestScope, mrid: str) -> MridType:
        """Attempts to decode an arbitrary mrid for this scope. If the mrid format looks invalid / doesn't match
        the current settings in scope (i.e. it's for a seperate deployed instance of this server) a ValueError will
        be raised"""
        if not mrid or len(mrid) != 32:
            raise ValueError("Expected mrid to have 32 hex characters")

        decoded_iana_pen = decode_iana_pen(mrid)
        if decoded_iana_pen != scope.iana_pen:
            raise ValueError(
                f"MRID was encoded for IANA PEN {decoded_iana_pen} which doesn't match this server {scope.iana_pen}"
            )

        return decode_mrid_type(mrid)

    @staticmethod
    def decode_doe_mrid(mrid: str) -> int:
        """Attempts to decode the ID component of the specified mrid.

        This function assumes it's a MridType.DYNAMIC_OPERATING_ENVELOPE encoding. Failure to check this before will
        result in undefined behaviour.

        returns the DynamicOperatingEnvelope.dynamic_operating_envelope_id"""
        if not mrid or len(mrid) != 32:
            raise ValueError("Expected mrid to have 32 hex characters")

        return decode_mrid_id(mrid)

    @staticmethod
    def decode_mirror_usage_point_mrid(mrid: str) -> int:
        """Attempts to decode the ID component of the specified mrid.

        This function assumes it's a MridType.MIRROR_USAGE_POINT encoding. Failure to check this before will
        result in undefined behaviour.

        returns the SiteReadingType.site_reading_type_id"""
        if not mrid or len(mrid) != 32:
            raise ValueError("Expected mrid to have 32 hex characters")

        return decode_mrid_id(mrid)

    @staticmethod
    def decode_time_tariff_interval_mrid(mrid: str) -> tuple[PricingReadingType, int]:
        """Attempts to decode the ID component of the specified mrid.

        This function assumes it's a MridType.TIME_TARIFF_INTERVAL encoding. Failure to check this before will
        result in undefined behaviour.

        returns the PricingReadingType AND TariffGeneratedRate.tariff_generated_rate_id"""
        if not mrid or len(mrid) != 32:
            raise ValueError("Expected mrid to have 32 hex characters")

        id = decode_mrid_id(mrid)
        return (PricingReadingType((id >> 90) + 1), id & 0xFFFFFFFFFFFFFFFF)
