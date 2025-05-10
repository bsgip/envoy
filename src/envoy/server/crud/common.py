from typing import Optional, TypeVar, Union
from zoneinfo import ZoneInfo

from sqlalchemy import Row

from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.tariff import TariffGeneratedRate

EntityWithStartTime = TypeVar(
    "EntityWithStartTime", bound=Union[TariffGeneratedRate, DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope]
)


def localize_start_time_for_entity(entity: EntityWithStartTime, tz_name: str) -> EntityWithStartTime:
    """Localizes a entity.start_time to be in the local timezone passed in as the second
    element in the tuple. Returns the Entity (it will be modified in place)"""
    tz = ZoneInfo(tz_name)
    entity.start_time = entity.start_time.astimezone(tz)
    return entity


def localize_start_time(entity_and_tz: Optional[Row[tuple[EntityWithStartTime, str]]]) -> EntityWithStartTime:
    """Localizes a Entity.start_time to be in the local timezone passed in as the second
    element in the tuple. Returns the Entity (it will be modified in place)"""
    if entity_and_tz is None:
        raise ValueError("row is None")

    entity: EntityWithStartTime
    tz_name: str
    (entity, tz_name) = entity_and_tz
    return localize_start_time_for_entity(entity, tz_name)


def sum_digits(n: int) -> int:
    """Sums all base10 digits in n and returns the results.
    Eg:
    11 -> 2
    456 -> 15"""
    n = abs(n)
    s = 0
    while n:
        s += n % 10
        n //= 10
    return s


def convert_lfdi_to_sfdi(lfdi: str) -> int:
    """This function generates the 2030.5-2018 sFDI (Short-form device identifier) from a
    2030.5-2018 lFDI (Long-form device identifier). More details on the sFDI can be found in
    section 6.3.3 of the IEEE Std 2030.5-2018.

    To generate the sFDI from the lFDI the following steps are performed:
        1- Left truncate the lFDI to 36 bits.
        2- From the result of Step (1), calculate a sum-of-digits checksum digit.
        3- Right concatenate the checksum digit to the result of Step (1).

    Args:
        lfdi: The 2030.5-2018 lFDI as string of 40 hex characters (eg '18aff1802d ... 12d')

    Return:
        The sFDI as integer.
    """
    if len(lfdi) != 40:
        raise ValueError(f"lfdi should be 40 hex characters. Received {len(lfdi)} chars")

    raw_sfdi = int(("0x" + lfdi[:9]), 16)
    sfdi_checksum = (10 - (sum_digits(raw_sfdi) % 10)) % 10
    return raw_sfdi * 10 + sfdi_checksum
