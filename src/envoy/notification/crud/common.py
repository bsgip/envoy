from dataclasses import dataclass
from typing import Optional, TypeVar

from envoy.server.model.archive.doe import (
    ArchiveDynamicOperatingEnvelope,
    ArchiveSiteControlGroup,
    ArchiveSiteControlGroupDefault,
)
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
from envoy.server.model.doe import DynamicOperatingEnvelope, SiteControlGroup, SiteControlGroupDefault
from envoy.server.model.server import RuntimeServerConfig
from envoy.server.model.site import Site, SiteDER, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.subscription import Subscription
from envoy.server.model.tariff import TariffGeneratedRate


@dataclass
class SiteScopedFunctionSetAssignment:
    """This is a mapping from RuntimeServerConfig (not site scoped) to a FunctionSetAssignment (site scoped)
    - for csip-aus we need the site scoping"""

    aggregator_id: int
    site_id: int
    function_set_assignment_ids: list[int]  # The list of "changed" function set assignments
    function_set_assignment_poll_rate: Optional[
        int
    ]  # The changed poll rate for FunctionSetAssignmentsList (if changed)


@dataclass
class ArchiveSiteScopedFunctionSetAssignment:
    """There is no model for this in the DB - we don't archive top level config changes"""

    aggregator_id: int
    site_id: int


@dataclass
class SiteScopedSiteControlGroup:
    """SiteControlGroup isn't scoped to a specific Site - for csip-aus it will need to be"""

    aggregator_id: int
    site_id: int
    original: SiteControlGroup


@dataclass
class ArchiveSiteScopedSiteControlGroup:
    """ArchiveSiteControlGroup isn't scoped to a specific Site - for csip-aus it will need to be"""

    aggregator_id: int
    site_id: int
    original: ArchiveSiteControlGroup


@dataclass
class SiteScopedSiteControlGroupDefault:
    """SiteControlGroupDefault isn't scoped to a specific site - for csip-aus it will need to be"""

    aggregator_id: int
    site_id: int
    site_control_group_id: int
    original: SiteControlGroupDefault


@dataclass
class ArchiveSiteScopedSiteControlGroupDefault:
    """SiteControlGroupDefault isn't scoped to a specific site - for csip-aus it will need to be"""

    aggregator_id: int
    site_id: int
    site_control_group_id: int
    original: ArchiveSiteControlGroupDefault


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
    SiteControlGroupDefault,
    SiteControlGroup,
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
    ArchiveSiteControlGroupDefault,
    ArchiveSiteControlGroup,
)
