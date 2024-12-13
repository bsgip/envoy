from typing import TypeVar

from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.archive.site import (
    ArchiveSite,
    ArchiveSiteDER,
    ArchiveSiteDERAvailability,
    ArchiveSiteDERRating,
    ArchiveSiteDERSetting,
    ArchiveSiteDERStatus,
)
from envoy.server.model.archive.site_reading import ArchiveSiteReading, ArchiveSiteReadingType
from envoy.server.model.archive.subscription import ArchiveSubscription
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site, SiteDER, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.subscription import Subscription
from envoy.server.model.tariff import TariffGeneratedRate

TResourceModel = TypeVar(
    "TResourceModel",
    Site,
    DynamicOperatingEnvelope,
    TariffGeneratedRate,
    SiteReading,
    SiteReadingType,
    SiteDER,
    SiteDERAvailability,
    SiteDERRating,
    SiteDERSetting,
    SiteDERStatus,
    Subscription,
)

TArchiveResourceModel = TypeVar(
    "TArchiveResourceModel",
    ArchiveSite,
    ArchiveDynamicOperatingEnvelope,
    ArchiveTariffGeneratedRate,
    ArchiveSiteReading,
    ArchiveSiteReadingType,
    ArchiveSiteDER,
    ArchiveSiteDERAvailability,
    ArchiveSiteDERRating,
    ArchiveSiteDERSetting,
    ArchiveSiteDERStatus,
    ArchiveSubscription,
)
