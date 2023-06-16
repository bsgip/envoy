from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from envoy.server.schema.sep2.types import DeviceCategory


class SiteResponse(BaseModel):
    """Response model for Site - includes the common details without exposing current aggregator assignments"""

    site_id: int
    nmi: Optional[str]
    timezone_id: str
    changed_time: datetime
    lfdi: str
    sfdi: int
    device_category: DeviceCategory


class SitePageResponse(BaseModel):
    """Represents a paginated response of Site"""

    total_count: int  # The total number of sites (independent of this page of results)
    limit: int  # The maximum number of sites that could've been returned (the limit set by the query)
    start: int  # The number of sites that have been skipped as part of this query (the start set by the query)
    sites: list[SiteResponse]  # The site models in this page
