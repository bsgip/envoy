from typing import Optional, TypeVar, Union
from zoneinfo import ZoneInfo

from sqlalchemy import Row

from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.tariff import TariffGeneratedRate

EntityWithStartTime = TypeVar("EntityWithStartTime", bound=Union[TariffGeneratedRate, DynamicOperatingEnvelope])


def localize_start_time(rate_and_tz: Optional[Row[tuple[EntityWithStartTime, str]]]) -> EntityWithStartTime:
    """Localizes a Entity.start_time to be in the local timezone passed in as the second
    element in the tuple. Returns the Entity (it will be modified in place)"""
    if rate_and_tz is None:
        raise ValueError("row is None")

    entity: EntityWithStartTime
    tz_name: str
    (entity, tz_name) = rate_and_tz
    tz = ZoneInfo(tz_name)
    entity.start_time = entity.start_time.astimezone(tz)
    return entity
