"""Shared constants should be put in here to avoid circular import"""

from enum import IntEnum, auto


class MridType(IntEnum):
    """Unique way of differentiating the different sep2 MRID types that can be encoded by this server.

    Given the restrictions on encode_mrid - Values can be a maximum of 4 bits"""

    DEFAULT_DOE = 1
    DER_PROGRAM = 2
    DYNAMIC_OPERATING_ENVELOPE = 3
    FUNCTION_SET_ASSIGNMENT = 4

    TARIFF = 7
    RATE_COMPONENT = 8
    TIME_TARIFF_INTERVAL = 9
    RESPONSE_SET = 10


class PricingReadingType(IntEnum):
    """The different types of readings that can be priced

    Increasing this beyond 4 unique values will have implications for the mrid mapper"""

    IMPORT_ACTIVE_POWER_KWH = auto()
    EXPORT_ACTIVE_POWER_KWH = auto()
    IMPORT_REACTIVE_POWER_KVARH = auto()
    EXPORT_REACTIVE_POWER_KVARH = auto()


class ResponseSetType(IntEnum):
    """The different types of response sets that are exposed via this utility server. Essentially this is a mapping
    of every type that has "response" objects associated with them"""

    TARIFF_GENERATED_RATES = auto()
    SITE_CONTROLS = auto()
