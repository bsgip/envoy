from typing import Protocol, TypeVar, Union

from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.archive.site import (
    ArchiveSite,
    ArchiveSiteDERAvailability,
    ArchiveSiteDERRating,
    ArchiveSiteDERSetting,
    ArchiveSiteDERStatus,
)
from envoy.server.model.archive.site_reading import ArchiveSiteReading
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from envoy.server.model.site_reading import SiteReading
from envoy.server.model.tariff import TariffGeneratedRate

TResourceModel = TypeVar(
    "TResourceModel",
    Site,
    DynamicOperatingEnvelope,
    TariffGeneratedRate,
    SiteReading,
    SiteDERAvailability,
    SiteDERRating,
    SiteDERSetting,
    SiteDERStatus,
)

TArchiveResourceModel = TypeVar(
    "TArchiveResourceModel",
    ArchiveSite,
    ArchiveDynamicOperatingEnvelope,
    ArchiveTariffGeneratedRate,
    ArchiveSiteReading,
    ArchiveSiteDERAvailability,
    ArchiveSiteDERRating,
    ArchiveSiteDERSetting,
    ArchiveSiteDERStatus,
)
