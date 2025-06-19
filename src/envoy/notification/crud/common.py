from dataclasses import dataclass
from typing import TypeVar

from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope
from envoy.server.model.archive.site import (
    ArchiveDefaultSiteControl,
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
from envoy.server.model.server import RuntimeServerConfig
from envoy.server.model.site import (
    DefaultSiteControl,
    Site,
    SiteDER,
    SiteDERAvailability,
    SiteDERRating,
    SiteDERSetting,
    SiteDERStatus,
)
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.subscription import Subscription
from envoy.server.model.tariff import TariffGeneratedRate


@dataclass
class SiteScopedRuntimeServerConfig:
    """RuntimeServerConfig isn't scoped to a specific Site - for csip-aus it will need to be"""

    aggregator_id: int
    site_id: int
    original: RuntimeServerConfig


@dataclass
class ArchiveSiteScopedRuntimeServerConfig:
    """There is no model for this in the DB - we don't archive top level config changes"""

    aggregator_id: int
    site_id: int


@dataclass
class ControlGroupScopedDefaultSiteControl:
    """DefaultSiteControl isn't scoped to a specific SiteControlGroup - for csip-aus it will need to be"""

    site_control_group_id: int
    original: DefaultSiteControl


@dataclass
class ArchiveControlGroupScopedDefaultSiteControl:
    """DefaultSiteControl isn't scoped to a specific SiteControlGroup - for csip-aus it will need to be"""

    site_control_group_id: int
    original: ArchiveDefaultSiteControl


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
    DefaultSiteControl,
    RuntimeServerConfig,
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
    ArchiveDefaultSiteControl,
)
