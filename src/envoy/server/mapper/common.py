from decimal import Decimal
from itertools import chain
from typing import Any, Optional, Union

from envoy_schema.server.schema.sep2.types import DEVICE_CATEGORY_ALL_SET, DeviceCategory

from envoy.server.exception import InvalidMappingError
from envoy.server.request_state import RequestStateParameters


def generate_mrid(*args: Union[int, float]) -> str:
    """Generates an mRID from a set of numbers by concatenating them (hex encoded) - padded to a minimum of 4 digits

    This isn't amazingly robust but for our purposes should allow us to generate a (likely) distinct mrid for
    entities that don't have a corresponding unique ID (eg the entity is entirely virtual with no corresponding
    database model)"""
    return "".join([f"{abs(a):04x}" for a in args])


def generate_href(uri_format: str, request_state_params: RequestStateParameters, *args: Any, **kwargs: Any) -> str:
    """Generates a href from a format string and an optional static prefix. Any args/kwargs will be forwarded to
    str.format (being applied to uri_format).

    If a prefix is applied - the state of the leading slash will mirror uri_format"""
    uri = uri_format.format(*args, **kwargs)
    prefix = request_state_params.href_prefix
    if prefix is None:
        return uri

    # The uri_format dictates whether the uri should be relative/absolute
    join_parts = (p for p in chain(prefix.split("/"), uri.split("/")) if p)
    joined = "/".join(join_parts)
    if uri_format.startswith("/"):
        if joined.startswith("/"):
            return joined
        else:
            return "/" + joined
    else:
        if joined.startswith("/"):
            return joined[1:]
        else:
            return joined


def remove_href_prefix(href: str, request_state_params: RequestStateParameters) -> str:
    """Reverses the href_prefix applied during generate_href (if any).
    Returns X such that generate_href(X, request_state_params) == uri"""
    if not request_state_params.href_prefix:
        return href

    # Safety check
    if not href.startswith(request_state_params.href_prefix):
        return href

    # Initial strip
    href = href[len(request_state_params.href_prefix) :]  # noqa: E203

    # Cleanup
    if href.startswith("/"):
        return href
    else:
        return "/" + href


def parse_device_category(device_category_str: Optional[str]) -> DeviceCategory:
    """Parse a hex string representation of a device category into a DeviceCategory"""
    if not device_category_str:
        return DeviceCategory(0)

    raw_dc = int(device_category_str, 16)
    if raw_dc > DEVICE_CATEGORY_ALL_SET or raw_dc < 0:
        raise InvalidMappingError(
            f"deviceCategory: {device_category_str} int({raw_dc}) doesn't map to a known DeviceCategory"
        )
    return DeviceCategory(raw_dc)


def pow10_to_decimal_value(value: Optional[int], pow10_multiplier: Optional[int]) -> Optional[Decimal]:
    """Converts a value and a power of ten multiplier into a raw Decimal value.

    If multiplier is not specified - it will be assumed to be 0

    Eg (Assuming the value represents Watts)
        to_decimal_value(1234, 3) would be equivalent to saying 1234 KiloWatts or 1,234,000 Watts
        to_decimal_value(1234, -3) would be equivalent to saying 1234 MilliWatts or 1.234 Watts"""
    if value is None:
        return None

    if pow10_multiplier is None:
        return Decimal(value)
    else:
        return Decimal(value) * (Decimal("10") ** pow10_multiplier)
