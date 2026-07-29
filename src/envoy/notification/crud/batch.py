import copy
from collections.abc import Iterable, Sequence
from datetime import datetime
from itertools import chain
from typing import Any, Generic, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.admin.crud.aggregator import select_all_aggregators
from envoy.notification.crud.archive import (
    fetch_entities_with_archive_by_datetime,
    fetch_entities_with_archive_by_id,
    orm_relationship_map_parent_entities,
)
from envoy.notification.crud.common import (
    ArchiveSiteScopedDynamicOperatingEnvelope,
    ArchiveSiteScopedFunctionSetAssignment,
    ArchiveSiteScopedSiteControlGroup,
    ArchiveSiteScopedSiteControlGroupDefault,
    ArchiveSiteScopedTariffGeneratedRate,
    SiteScopedDynamicOperatingEnvelope,
    SiteScopedFunctionSetAssignment,
    SiteScopedSiteControlGroup,
    SiteScopedSiteControlGroupDefault,
    SiteScopedTariffGeneratedRate,
    TArchiveResourceModel,
    TResourceModel,
)
from envoy.notification.exception import NotificationError
from envoy.server.crud.common import localize_start_time_for_entity
from envoy.server.crud.server import select_server_config
from envoy.server.manager.der_constants import PUBLIC_SITE_DER_ID
from envoy.server.model.aggregator import Aggregator
from envoy.server.model.archive.doe import (
    ArchiveDynamicOperatingEnvelope,
    ArchiveSiteControlGroup,
    ArchiveSiteControlGroupDefault,
)
from envoy.server.model.archive.site import (
    ArchiveSite,
    ArchiveSiteDERAvailability,
    ArchiveSiteDERRating,
    ArchiveSiteDERSetting,
    ArchiveSiteDERStatus,
)
from envoy.server.model.archive.site_reading import ArchiveSiteReading, ArchiveSiteReadingType
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
from envoy.server.model.doe import DynamicOperatingEnvelope, SiteControlGroup, SiteControlGroupDefault
from envoy.server.model.site import (
    Site,
    SiteDERAvailability,
    SiteDERRating,
    SiteDERSetting,
    SiteDERStatus,
    SiteGroupAssignment,
)
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.subscription import Subscription, SubscriptionResource
from envoy.server.model.tariff import Tariff, TariffGeneratedRate


class AggregatorBatchedEntities(Generic[TResourceModel, TArchiveResourceModel]):
    """A set of TResourceModel and TArchiveResourceModel entities keyed by their aggregator ID and then site id. They
    represent all of the entities that have changed/deleted in a single batch (identified by timestamp)."""

    timestamp: datetime

    # All of the models that were changed at timestamp. First element of batch key will be aggregator_id
    models_by_batch_key: dict[tuple, list[TResourceModel]]

    # The archive records that were deleted at timestamp. First element of batch key will be aggregator id
    deleted_by_batch_key: dict[tuple, list[TArchiveResourceModel]]

    @staticmethod
    def _generate_batch_dict(resource: SubscriptionResource, models: Iterable[Any]) -> dict[tuple, list[Any]]:
        batch_dict: dict[tuple, list[Any]] = {}
        for m in models:
            batch_key = get_batch_key(resource, m)

            model_list = batch_dict.get(batch_key, None)
            if model_list is None:
                batch_dict[batch_key] = [m]
            else:
                model_list.append(m)
        return batch_dict

    def __init__(
        self,
        timestamp: datetime,
        resource: SubscriptionResource,
        models: Sequence[TResourceModel],
        deleted_models: Sequence[TArchiveResourceModel],
    ) -> None:
        super().__init__()

        self.timestamp = timestamp
        self.models_by_batch_key = AggregatorBatchedEntities._generate_batch_dict(resource, models)
        self.deleted_by_batch_key = AggregatorBatchedEntities._generate_batch_dict(resource, deleted_models)

    @staticmethod
    def aggregator_id_instance(
        timestamp: datetime, resource: SubscriptionResource, aggregators: Sequence[Aggregator]
    ) -> "AggregatorBatchedEntities":
        """This will generate an instance with the models_by_batch_key loaded with a key for each aggregator instance
        (key being a single tuple[aggregator_id: int]). Each of the entries will be an empty list.

        This will be a mechanism for prepping an "empty list" notification for representing things like a pollRate
        change"""

        batch = AggregatorBatchedEntities(timestamp, resource, [], [])
        for agg in aggregators:
            batch.models_by_batch_key[(agg.aggregator_id,)] = []
        return batch


def get_batch_key(resource: SubscriptionResource, entity: TResourceModel) -> tuple:
    """
    Gets a multipart key in the form of a tuple that describes entity as a single sep2 resource. This is because
    sep2 Notifications are only sent out underneath a single resource (eg /edev/3/derp/doe/derc/1) which means all
    notifications we generate MUST be grouped by this batch key

    NOTE - the first element of every tuple will be aggregator_id

    Given the SubscriptionResource - it's safe to rely on the ordering of the batch key tuple entries:

    SubscriptionResource.SITE: (aggregator_id: int, site_id: int) OR (aggregator_id: int)
    SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE: (aggregator_id: int, site_id: int, site_control_group_id: int)
    SubscriptionResource.READING: (aggregator_id: int, site_id: int, group_id: int)
    SubscriptionResource.TARIFF_GENERATED_RATE: (aggregator_id: int, tariff_id: int, site_id: int, day: date)
    SubscriptionResource.SITE_DER_AVAILABILITY: (aggregator_id: int, site_id: int, site_der_id: int)
    SubscriptionResource.SITE_DER_RATING: (aggregator_id: int, site_id: int, site_der_id: int)
    SubscriptionResource.SITE_DER_SETTING: (aggregator_id: int, site_id: int, site_der_id: int)
    SubscriptionResource.SITE_DER_STATUS: (aggregator_id: int, site_id: int, site_der_id: int)
    SubscriptionResource.FUNCTION_SET_ASSIGNMENTS: (aggregator_id: int, site_id: int)
    SubscriptionResource.SITE_CONTROL_GROUP: (aggregator_id: int, site_id: int)
    SubscriptionResource.DEFAULT_SITE_CONTROL: (aggregator_id: int, site_id: int, site_control_group_id: int)
    SubscriptionResource.SUBSCRIPTION: (aggregator_id: int, subscription_id: int)
    """
    if resource == SubscriptionResource.SITE:
        site: Site = cast(Site, entity)
        return (site.aggregator_id, site.site_id)
    elif resource == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
        scoped_doe = cast(SiteScopedDynamicOperatingEnvelope, entity)
        return (scoped_doe.aggregator_id, scoped_doe.site_id, scoped_doe.original.site_control_group_id)
    elif resource == SubscriptionResource.READING:
        reading = cast(SiteReading, entity)
        return (
            reading.site_reading_type.aggregator_id,
            reading.site_reading_type.site_id,
            reading.site_reading_type.group_id,
        )
    elif resource == SubscriptionResource.TARIFF_GENERATED_RATE:
        scoped_rate = cast(SiteScopedTariffGeneratedRate, entity)
        return (
            scoped_rate.aggregator_id,
            scoped_rate.original.tariff_id,
            scoped_rate.site_id,
            scoped_rate.original.start_time.date(),
        )
    elif resource == SubscriptionResource.SITE_DER_AVAILABILITY:
        availability = cast(SiteDERAvailability, entity)
        return (availability.site.aggregator_id, availability.site_id, PUBLIC_SITE_DER_ID)
    elif resource == SubscriptionResource.SITE_DER_RATING:
        rating = cast(SiteDERRating, entity)
        return (rating.site.aggregator_id, rating.site_id, PUBLIC_SITE_DER_ID)
    elif resource == SubscriptionResource.SITE_DER_SETTING:
        setting = cast(SiteDERSetting, entity)
        return (setting.site.aggregator_id, setting.site_id, PUBLIC_SITE_DER_ID)
    elif resource == SubscriptionResource.SITE_DER_STATUS:
        status = cast(SiteDERStatus, entity)
        return (status.site.aggregator_id, status.site_id, PUBLIC_SITE_DER_ID)
    elif resource == SubscriptionResource.DEFAULT_SITE_CONTROL:
        default_control = cast(SiteScopedSiteControlGroupDefault, entity)
        return (
            default_control.aggregator_id,
            default_control.site_id,
            default_control.site_control_group_id,
        )
    elif resource == SubscriptionResource.FUNCTION_SET_ASSIGNMENTS:
        server_config = cast(SiteScopedFunctionSetAssignment, entity)
        return (server_config.aggregator_id, server_config.site_id)
    elif resource == SubscriptionResource.SITE_CONTROL_GROUP:
        scgroup = cast(SiteScopedSiteControlGroup, entity)
        return (scgroup.aggregator_id, scgroup.site_id)
    else:
        raise NotificationError(f"{resource} is unsupported - unable to identify appropriate batch key")


def get_subscription_filter_id(resource: SubscriptionResource, entity: TResourceModel) -> int:
    """Means of disambiguating the "subscription filter" id for TResourceModel. This is the field
    that Subscription.resource_id will filter on (if specified). This practically allows subscriptions
    to apply to only a subset of entities"""
    if resource == SubscriptionResource.SITE:
        # Site lists subscriptions can be scoped to a single site
        return cast(Site, entity).site_id
    elif resource == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
        # DOE subscriptions can be scoped to a single DERP
        return cast(SiteScopedDynamicOperatingEnvelope, entity).original.site_control_group_id
    elif resource == SubscriptionResource.READING:
        # Reading subscriptions can be scoped to the overarching type
        return cast(SiteReading, entity).site_reading_type.group_id
    elif resource == SubscriptionResource.TARIFF_GENERATED_RATE:
        # rate subscriptions can be scoped to a single tariff
        return cast(SiteScopedTariffGeneratedRate, entity).original.tariff_id
    elif resource == SubscriptionResource.SITE_DER_AVAILABILITY:
        # der entities get scoped to the parent der
        return PUBLIC_SITE_DER_ID  # There is only a single site DER per EndDevice - it has a static id
    elif resource == SubscriptionResource.SITE_DER_RATING:
        # der entities get scoped to the parent der
        return PUBLIC_SITE_DER_ID  # There is only a single site DER per EndDevice - it has a static id
    elif resource == SubscriptionResource.SITE_DER_SETTING:
        # der entities get scoped to the parent der
        return PUBLIC_SITE_DER_ID  # There is only a single site DER per EndDevice - it has a static id
    elif resource == SubscriptionResource.SITE_DER_STATUS:
        # der entities get scoped to the parent der
        return PUBLIC_SITE_DER_ID  # There is only a single site DER per EndDevice - it has a static id
    elif resource == SubscriptionResource.FUNCTION_SET_ASSIGNMENTS:
        return -1  # There are no subscriptions to a single FSA
    elif resource == SubscriptionResource.DEFAULT_SITE_CONTROL:
        return cast(SiteScopedSiteControlGroupDefault, entity).site_control_group_id
    elif resource == SubscriptionResource.SITE_CONTROL_GROUP:
        return cast(SiteScopedSiteControlGroup, entity).original.fsa_id or -1
    else:
        raise NotificationError(f"{resource} is unsupported - unable to identify appropriate primary key")


def get_site_id(resource: SubscriptionResource, entity: TResourceModel) -> int:
    """Means of disambiguating the site id for TResourceModel"""
    if resource == SubscriptionResource.SITE:
        return cast(Site, entity).site_id
    elif resource == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
        return cast(SiteScopedDynamicOperatingEnvelope, entity).site_id
    elif resource == SubscriptionResource.READING:
        return cast(SiteReading, entity).site_reading_type.site_id
    elif resource == SubscriptionResource.TARIFF_GENERATED_RATE:
        return cast(SiteScopedTariffGeneratedRate, entity).site_id
    elif resource == SubscriptionResource.SITE_DER_AVAILABILITY:
        return cast(SiteDERAvailability, entity).site_id
    elif resource == SubscriptionResource.SITE_DER_RATING:
        return cast(SiteDERRating, entity).site_id
    elif resource == SubscriptionResource.SITE_DER_SETTING:
        return cast(SiteDERSetting, entity).site_id
    elif resource == SubscriptionResource.SITE_DER_STATUS:
        return cast(SiteDERStatus, entity).site_id
    elif resource == SubscriptionResource.DEFAULT_SITE_CONTROL:
        return cast(SiteScopedSiteControlGroupDefault, entity).site_id
    elif resource == SubscriptionResource.FUNCTION_SET_ASSIGNMENTS:
        return cast(SiteScopedFunctionSetAssignment, entity).site_id
    elif resource == SubscriptionResource.SITE_CONTROL_GROUP:
        return cast(SiteScopedSiteControlGroup, entity).site_id
    else:
        raise NotificationError(f"{resource} is unsupported - unable to identify appropriate site id")


async def select_subscriptions_for_resource(
    session: AsyncSession, aggregator_id: int, resource: SubscriptionResource
) -> Sequence[Subscription]:
    """Fetches all subscriptions that 'might' match a change in a particular resource. Actual checks will not be made.

    Will populate the Subscription.conditions relationship"""

    stmt = (
        select(Subscription)
        .where((Subscription.aggregator_id == aggregator_id) & (Subscription.resource_type == resource))
        .options(selectinload(Subscription.conditions))
    )

    resp = await session.execute(stmt)
    return resp.scalars().all()


async def fetch_sites_by_changed_at(
    session: AsyncSession, timestamp: datetime
) -> AggregatorBatchedEntities[Site, ArchiveSite]:
    """Fetches all sites matching the specified changed_at and returns them keyed by their aggregator/site id

    Also fetches any site from the archive that was deleted at the specified timestamp.

    This will also consider runtime config for the EndDeviceList.pollRate - If this is altered, it will instead
    generate a notification for EVERY EndDevice"""

    # If run time config has been marked as a "Site" update - it's because it has had a change in poll rate
    # In this circumstance - we generate a special kind of update that will result in an "Empty List" Notification
    # that will just show the pollRate change.
    runtime_cfg = await select_server_config(session)
    if runtime_cfg is not None and runtime_cfg.changed_time == timestamp:
        aggregators = await select_all_aggregators(session, None, None)
        return AggregatorBatchedEntities.aggregator_id_instance(timestamp, SubscriptionResource.SITE, aggregators)

    # Otherwise - we proceed as if sites are the table that is changing
    active_sites, deleted_sites = await fetch_entities_with_archive_by_datetime(session, Site, ArchiveSite, timestamp)
    return AggregatorBatchedEntities(timestamp, SubscriptionResource.SITE, active_sites, deleted_sites)


async def fetch_rates_by_changed_at(
    session: AsyncSession, timestamp: datetime
) -> AggregatorBatchedEntities[SiteScopedTariffGeneratedRate, ArchiveSiteScopedTariffGeneratedRate]:  # type: ignore # SiteScoped variables will work here - tests enforce it
    """Fetches all rates matching the specified changed_at and returns them keyed by their aggregator/site id

    A rate targets a SiteGroup (rather than a single site) - each changed/deleted rate is expanded into one
    SiteScopedTariffGeneratedRate per member site of its SiteGroup (NOT every site in the system - only the
    group's actual members, unlike the SiteControlGroup/FSA fan-out patterns elsewhere in this file). A rate whose
    SiteGroup currently has no members contributes no entries.

    Also fetches any rate from the archive that was deleted at the specified timestamp"""

    active_rates, deleted_rates = await fetch_entities_with_archive_by_datetime(
        session, TariffGeneratedRate, ArchiveTariffGeneratedRate, timestamp
    )

    referenced_site_group_ids = {
        e.site_group_id
        for e in cast(Iterable[TariffGeneratedRate | ArchiveTariffGeneratedRate], chain(active_rates, deleted_rates))
    }

    member_sites_by_group_id: dict[int, list[tuple[int, int, str]]] = {}
    if referenced_site_group_ids:
        member_sites = (
            await session.execute(
                select(SiteGroupAssignment.site_group_id, Site.aggregator_id, Site.site_id, Site.timezone_id)
                .join(Site, Site.site_id == SiteGroupAssignment.site_id)
                .where(SiteGroupAssignment.site_group_id.in_(referenced_site_group_ids))
            )
        ).all()
        for site_group_id, aggregator_id, site_id, timezone_id in member_sites:
            member_sites_by_group_id.setdefault(site_group_id, []).append((aggregator_id, site_id, timezone_id))

    # A rate's parent Tariff can also restrict visibility via required_site_group_id - resolve each referenced
    # Tariff's requirement (if any) and the membership of whatever SiteGroup it requires
    referenced_tariff_ids = {
        e.tariff_id
        for e in cast(Iterable[TariffGeneratedRate | ArchiveTariffGeneratedRate], chain(active_rates, deleted_rates))
    }
    required_group_by_tariff_id: dict[int, int | None] = {}
    if referenced_tariff_ids:
        tariff_rows = (
            await session.execute(
                select(Tariff.tariff_id, Tariff.required_site_group_id).where(
                    Tariff.tariff_id.in_(referenced_tariff_ids)
                )
            )
        ).tuples()
        required_group_by_tariff_id = dict(tariff_rows.all())

    referenced_required_group_ids = {gid for gid in required_group_by_tariff_id.values() if gid is not None}
    member_site_ids_by_required_group: dict[int, set[int]] = {}
    if referenced_required_group_ids:
        required_members = (
            await session.execute(
                select(SiteGroupAssignment.site_group_id, SiteGroupAssignment.site_id).where(
                    SiteGroupAssignment.site_group_id.in_(referenced_required_group_ids)
                )
            )
        ).all()
        for site_group_id, site_id in required_members:
            member_site_ids_by_required_group.setdefault(site_group_id, set()).add(site_id)

    def expand_rate(rate: TariffGeneratedRate | ArchiveTariffGeneratedRate) -> list[tuple[int, int, Any]]:
        """Expands a single rate into one (aggregator_id, site_id, localized_rate) tuple per member site of its
        SiteGroup. Each site gets its own copy of rate since start_time localization mutates in place and
        different member sites can be in different timezones.

        A member site is excluded if the rate's parent Tariff has a required_site_group_id set and the site isn't
        a member of that SiteGroup (Tariff.required_site_group_id not found - eg the Tariff itself has been
        deleted - is treated as unrestricted, since there's no requirement left to enforce)."""
        required_group_id = required_group_by_tariff_id.get(rate.tariff_id)
        allowed_site_ids = (
            None if required_group_id is None else member_site_ids_by_required_group.get(required_group_id, set())
        )
        return [
            (aggregator_id, site_id, localize_start_time_for_entity(copy.copy(rate), timezone_id))
            for aggregator_id, site_id, timezone_id in member_sites_by_group_id.get(rate.site_group_id, [])
            if allowed_site_ids is None or site_id in allowed_site_ids
        ]

    site_scoped_active_rates = [
        SiteScopedTariffGeneratedRate(aggregator_id, site_id, localized_rate)
        for rate in cast(Iterable[TariffGeneratedRate], active_rates)
        for aggregator_id, site_id, localized_rate in expand_rate(rate)
    ]
    site_scoped_deleted_rates = [
        ArchiveSiteScopedTariffGeneratedRate(aggregator_id, site_id, localized_rate)
        for rate in cast(Iterable[ArchiveTariffGeneratedRate], deleted_rates)
        for aggregator_id, site_id, localized_rate in expand_rate(rate)
    ]

    return AggregatorBatchedEntities(
        timestamp,
        SubscriptionResource.TARIFF_GENERATED_RATE,
        site_scoped_active_rates,  # type: ignore # SiteScoped variables will work here - tests enforce it
        site_scoped_deleted_rates,  # type: ignore # SiteScoped variables will work here - tests enforce it
    )


async def fetch_does_by_changed_at(
    session: AsyncSession, timestamp: datetime
) -> AggregatorBatchedEntities[SiteScopedDynamicOperatingEnvelope, ArchiveSiteScopedDynamicOperatingEnvelope]:  # type: ignore # SiteScoped variables will work here - tests enforce it
    """Fetches all DOEs matching the specified changed_at and returns them keyed by their aggregator/site id

    A DOE targets a SiteGroup (rather than a single site) - each changed/deleted DOE is expanded into one
    SiteScopedDynamicOperatingEnvelope per member site of its SiteGroup (NOT every site in the system - only the
    group's actual members, unlike the SiteControlGroup/FSA fan-out patterns elsewhere in this file). A DOE whose
    SiteGroup currently has no members contributes no entries."""

    active_does, deleted_does = await fetch_entities_with_archive_by_datetime(
        session, DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope, timestamp
    )

    referenced_site_group_ids = {
        e.site_group_id
        for e in cast(
            Iterable[DynamicOperatingEnvelope | ArchiveDynamicOperatingEnvelope], chain(active_does, deleted_does)
        )
    }

    member_sites_by_group_id: dict[int, list[tuple[int, int, str]]] = {}
    if referenced_site_group_ids:
        member_sites = (
            await session.execute(
                select(SiteGroupAssignment.site_group_id, Site.aggregator_id, Site.site_id, Site.timezone_id)
                .join(Site, Site.site_id == SiteGroupAssignment.site_id)
                .where(SiteGroupAssignment.site_group_id.in_(referenced_site_group_ids))
            )
        ).all()
        for site_group_id, aggregator_id, site_id, timezone_id in member_sites:
            member_sites_by_group_id.setdefault(site_group_id, []).append((aggregator_id, site_id, timezone_id))

    def expand_doe(doe: DynamicOperatingEnvelope | ArchiveDynamicOperatingEnvelope) -> list[tuple[int, int, Any]]:
        """Expands a single doe into one (aggregator_id, site_id, localized_doe) tuple per member site of its
        SiteGroup. Each site gets its own copy of doe since start_time localization mutates in place and different
        member sites can be in different timezones."""
        return [
            (aggregator_id, site_id, localize_start_time_for_entity(copy.copy(doe), timezone_id))
            for aggregator_id, site_id, timezone_id in member_sites_by_group_id.get(doe.site_group_id, [])
        ]

    site_scoped_active_does = [
        SiteScopedDynamicOperatingEnvelope(aggregator_id, site_id, localized_doe)
        for doe in cast(Iterable[DynamicOperatingEnvelope], active_does)
        for aggregator_id, site_id, localized_doe in expand_doe(doe)
    ]
    site_scoped_deleted_does = [
        ArchiveSiteScopedDynamicOperatingEnvelope(aggregator_id, site_id, localized_doe)
        for doe in cast(Iterable[ArchiveDynamicOperatingEnvelope], deleted_does)
        for aggregator_id, site_id, localized_doe in expand_doe(doe)
    ]

    return AggregatorBatchedEntities(
        timestamp,
        SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE,
        site_scoped_active_does,  # type: ignore # SiteScoped variables will work here - tests enforce it
        site_scoped_deleted_does,  # type: ignore # SiteScoped variables will work here - tests enforce it
    )


async def fetch_readings_by_changed_at(
    session: AsyncSession, timestamp: datetime
) -> AggregatorBatchedEntities[SiteReading, ArchiveSiteReading]:
    """Fetches all site readings matching the specified changed_at and returns them keyed by their aggregator/site id

    Will include the SiteReading.site_reading_type relationship"""

    active_readings, deleted_readings = await fetch_entities_with_archive_by_datetime(
        session, SiteReading, ArchiveSiteReading, timestamp
    )

    referenced_site_reading_type_ids = {
        e.site_reading_type_id
        for e in cast(
            Iterable[SiteReading | ArchiveSiteReading],
            chain(active_readings, deleted_readings),
        )
    }

    active_site_reading_types, deleted_site_reading_types = await fetch_entities_with_archive_by_id(
        session, SiteReadingType, ArchiveSiteReadingType, referenced_site_reading_type_ids
    )

    # Map the "site_reading_type" relationship
    orm_relationship_map_parent_entities(
        cast(
            Iterable[SiteReading | ArchiveSiteReading],
            chain(active_readings, deleted_readings),
        ),
        lambda e: e.site_reading_type_id,
        {
            e.site_reading_type_id: e
            for e in cast(
                Iterable[SiteReadingType | ArchiveSiteReadingType],
                chain(active_site_reading_types, deleted_site_reading_types),
            )
        },
        "site_reading_type",
    )

    return AggregatorBatchedEntities(timestamp, SubscriptionResource.READING, active_readings, deleted_readings)


async def fetch_der_availability_by_changed_at(
    session: AsyncSession, timestamp: datetime
) -> AggregatorBatchedEntities[SiteDERAvailability, ArchiveSiteDERAvailability]:
    """Fetches all der availabilities matching the specified changed_at and returns them keyed by their
    aggregator/site id

    Will include the SiteDERAvailability.site relationship"""

    active_der_avails, deleted_der_avails = await fetch_entities_with_archive_by_datetime(
        session, SiteDERAvailability, ArchiveSiteDERAvailability, timestamp
    )

    referenced_site_ids = {
        e.site_id
        for e in cast(
            Iterable[SiteDERAvailability | ArchiveSiteDERAvailability],
            chain(active_der_avails, deleted_der_avails),
        )
    }

    active_sites, deleted_sites = await fetch_entities_with_archive_by_id(
        session, Site, ArchiveSite, referenced_site_ids
    )

    # Map the "site" relationship for every der availability
    orm_relationship_map_parent_entities(
        cast(
            Iterable[SiteDERAvailability | ArchiveSiteDERAvailability],
            chain(active_der_avails, deleted_der_avails),
        ),
        lambda e: e.site_id,
        {e.site_id: e for e in cast(Iterable[Site | ArchiveSite], chain(active_sites, deleted_sites))},
        "site",
    )

    return AggregatorBatchedEntities(
        timestamp, SubscriptionResource.SITE_DER_AVAILABILITY, active_der_avails, deleted_der_avails
    )


async def fetch_der_rating_by_changed_at(
    session: AsyncSession, timestamp: datetime
) -> AggregatorBatchedEntities[SiteDERRating, ArchiveSiteDERRating]:
    """Fetches all der ratings matching the specified changed_at and returns them keyed by their
    aggregator/site id

    Will include the SiteDERRating.site relationship"""

    active_der_ratings, deleted_der_ratings = await fetch_entities_with_archive_by_datetime(
        session, SiteDERRating, ArchiveSiteDERRating, timestamp
    )

    referenced_site_ids = {
        e.site_id
        for e in cast(
            Iterable[SiteDERRating | ArchiveSiteDERRating],
            chain(active_der_ratings, deleted_der_ratings),
        )
    }

    active_sites, deleted_sites = await fetch_entities_with_archive_by_id(
        session, Site, ArchiveSite, referenced_site_ids
    )

    # Map the "site" relationship for every der rating
    orm_relationship_map_parent_entities(
        cast(
            Iterable[SiteDERRating | ArchiveSiteDERRating],
            chain(active_der_ratings, deleted_der_ratings),
        ),
        lambda e: e.site_id,
        {e.site_id: e for e in cast(Iterable[Site | ArchiveSite], chain(active_sites, deleted_sites))},
        "site",
    )

    return AggregatorBatchedEntities(
        timestamp, SubscriptionResource.SITE_DER_RATING, active_der_ratings, deleted_der_ratings
    )


async def fetch_der_setting_by_changed_at(
    session: AsyncSession, timestamp: datetime
) -> AggregatorBatchedEntities[SiteDERSetting, ArchiveSiteDERSetting]:
    """Fetches all der settings matching the specified changed_at and returns them keyed by their
    aggregator/site id

    Will include the SiteDERSetting.site relationship"""

    active_der_settings, deleted_der_settings = await fetch_entities_with_archive_by_datetime(
        session, SiteDERSetting, ArchiveSiteDERSetting, timestamp
    )

    referenced_site_ids = {
        e.site_id
        for e in cast(
            Iterable[SiteDERSetting | ArchiveSiteDERSetting],
            chain(active_der_settings, deleted_der_settings),
        )
    }

    active_sites, deleted_sites = await fetch_entities_with_archive_by_id(
        session, Site, ArchiveSite, referenced_site_ids
    )

    # Map the "site" relationship for every der setting
    orm_relationship_map_parent_entities(
        cast(
            Iterable[SiteDERSetting | ArchiveSiteDERSetting],
            chain(active_der_settings, deleted_der_settings),
        ),
        lambda e: e.site_id,
        {e.site_id: e for e in cast(Iterable[Site | ArchiveSite], chain(active_sites, deleted_sites))},
        "site",
    )

    return AggregatorBatchedEntities(
        timestamp, SubscriptionResource.SITE_DER_SETTING, active_der_settings, deleted_der_settings
    )


async def fetch_der_status_by_changed_at(
    session: AsyncSession, timestamp: datetime
) -> AggregatorBatchedEntities[SiteDERStatus, ArchiveSiteDERStatus]:
    """Fetches all der status matching the specified changed_at and returns them keyed by their
    aggregator/site id

    Will include the SiteDERStatus.site relationship"""

    active_der_statuses, deleted_der_statuses = await fetch_entities_with_archive_by_datetime(
        session, SiteDERStatus, ArchiveSiteDERStatus, timestamp
    )

    referenced_site_ids = {
        e.site_id
        for e in cast(
            Iterable[SiteDERStatus | ArchiveSiteDERStatus],
            chain(active_der_statuses, deleted_der_statuses),
        )
    }

    active_sites, deleted_sites = await fetch_entities_with_archive_by_id(
        session, Site, ArchiveSite, referenced_site_ids
    )

    # Map the "site" relationship for every der status
    orm_relationship_map_parent_entities(
        cast(
            Iterable[SiteDERStatus | ArchiveSiteDERStatus],
            chain(active_der_statuses, deleted_der_statuses),
        ),
        lambda e: e.site_id,
        {e.site_id: e for e in cast(Iterable[Site | ArchiveSite], chain(active_sites, deleted_sites))},
        "site",
    )

    return AggregatorBatchedEntities(
        timestamp, SubscriptionResource.SITE_DER_STATUS, active_der_statuses, deleted_der_statuses
    )


async def fetch_default_site_controls_by_changed_at(
    session: AsyncSession, timestamp: datetime
) -> AggregatorBatchedEntities[SiteScopedSiteControlGroupDefault, ArchiveSiteScopedSiteControlGroupDefault]:  # type: ignore # SiteScoped variables will work here - tests enforce it
    """Fetches all DefaultSiteControl instances matching the specified changed_at and returns them keyed by their
    aggregator/site id

    Also fetches any site from the archive that was deleted at the specified timestamp"""

    active_defaults, deleted_defaults = await fetch_entities_with_archive_by_datetime(
        session, SiteControlGroupDefault, ArchiveSiteControlGroupDefault, timestamp
    )

    # We need to generate a notification per site ID - so fetch all of those
    aggregator_site_ids = (await session.execute(select(Site.aggregator_id, Site.site_id).order_by(Site.site_id))).all()

    scoped_actives = [
        SiteScopedSiteControlGroupDefault(agg_id, site_id, ad.site_control_group_id, ad)
        for ad in active_defaults
        for agg_id, site_id in aggregator_site_ids
    ]
    scoped_deleted = [
        ArchiveSiteScopedSiteControlGroupDefault(agg_id, site_id, dd.site_control_group_id, dd)
        for dd in deleted_defaults
        for agg_id, site_id in aggregator_site_ids
    ]

    return AggregatorBatchedEntities(
        timestamp,
        SubscriptionResource.DEFAULT_SITE_CONTROL,
        scoped_actives,  # type: ignore # SiteScoped variables will work here - tests enforce it
        scoped_deleted,  # type: ignore # SiteScoped variables will work here - tests enforce it
    )


async def fetch_fsa_by_changed_at(
    session: AsyncSession, timestamp: datetime
) -> AggregatorBatchedEntities[SiteScopedFunctionSetAssignment, ArchiveSiteScopedFunctionSetAssignment]:  # type: ignore # noqa: E501
    """Fetches all SiteScopedFunctionSetAssignment instances matching the specified changed_at and returns them keyed
    by their aggregator/site id"""

    # Two things can trigger a FSA Notification - a change in pollrate...
    runtime_cfg = await select_server_config(session)
    new_poll_rate: int | None = None
    if runtime_cfg is not None and runtime_cfg.changed_time == timestamp:
        new_poll_rate = runtime_cfg.fsal_pollrate_seconds

    # ... or a change in SiteControlGroup fsa_index (indicating a new FunctionSetAssignment ID)
    active_groups, _ = await fetch_entities_with_archive_by_datetime(
        session, SiteControlGroup, ArchiveSiteControlGroup, timestamp
    )
    new_fsa_ids = [scg.fsa_id for scg in active_groups if scg.fsa_id is not None]

    # If there isn't anything that's changed - don't encode any entities (there's nothing to Notify)
    if new_poll_rate is None and not new_fsa_ids:
        return AggregatorBatchedEntities(timestamp, SubscriptionResource.FUNCTION_SET_ASSIGNMENTS, [], [])

    # The fsa update will need to vary per Site so we generate an instance per site_id
    aggregator_site_ids = (await session.execute(select(Site.aggregator_id, Site.site_id).order_by(Site.site_id))).all()

    site_scoped_cfgs = [
        SiteScopedFunctionSetAssignment(agg_id, site_id, new_fsa_ids, new_poll_rate)
        for agg_id, site_id in aggregator_site_ids
    ]

    return AggregatorBatchedEntities(timestamp, SubscriptionResource.FUNCTION_SET_ASSIGNMENTS, site_scoped_cfgs, [])  # type: ignore


async def fetch_site_control_groups_by_changed_at(
    session: AsyncSession, timestamp: datetime
) -> AggregatorBatchedEntities[SiteScopedSiteControlGroup, ArchiveSiteScopedSiteControlGroup]:  # type: ignore # SiteScoped variables will work here - tests enforce it
    """Fetches all SiteControlGroup instances matching the specified changed_at and returns them keyed by all existing
    site IDs

    Also fetches any site control group from the archive that was deleted at the specified timestamp.

    If the runtime config changed at this timestamp (derpl_pollrate_seconds update), generates an empty-list
    notification per aggregator so subscribers receive the updated pollRate."""

    runtime_cfg = await select_server_config(session)
    if runtime_cfg is not None and runtime_cfg.changed_time == timestamp:
        aggregators = await select_all_aggregators(session, None, None)
        return AggregatorBatchedEntities.aggregator_id_instance(
            timestamp, SubscriptionResource.SITE_CONTROL_GROUP, aggregators
        )

    active_groups, deleted_groups = await fetch_entities_with_archive_by_datetime(
        session, SiteControlGroup, ArchiveSiteControlGroup, timestamp
    )
    if len(active_groups) == 0 and len(deleted_groups) == 0:
        return AggregatorBatchedEntities(timestamp, SubscriptionResource.SITE_CONTROL_GROUP, [], [])

    # The site control group update will need to vary per Site so we generate an instance per site_id
    aggregator_site_ids = (
        (await session.execute(select(Site.aggregator_id, Site.site_id).order_by(Site.site_id))).tuples().all()
    )

    # Groups with a required_site_group_id set are only visible to member sites of that group - resolve
    # membership for any such groups referenced in this batch
    referenced_required_group_ids = {
        g.required_site_group_id
        for g in cast(Iterable[SiteControlGroup | ArchiveSiteControlGroup], chain(active_groups, deleted_groups))
        if g.required_site_group_id is not None
    }
    member_site_ids_by_required_group: dict[int, set[int]] = {}
    if referenced_required_group_ids:
        members = (
            await session.execute(
                select(SiteGroupAssignment.site_group_id, SiteGroupAssignment.site_id).where(
                    SiteGroupAssignment.site_group_id.in_(referenced_required_group_ids)
                )
            )
        ).all()
        for site_group_id, site_id in members:
            member_site_ids_by_required_group.setdefault(site_group_id, set()).add(site_id)

    def visible_aggregator_site_ids(
        group: SiteControlGroup | ArchiveSiteControlGroup,
    ) -> Sequence[tuple[int, int]]:
        """Returns the (aggregator_id, site_id) pairs that should be notified about group - all sites, unless
        group.required_site_group_id restricts visibility to a specific SiteGroup's members."""
        if group.required_site_group_id is None:
            return aggregator_site_ids
        member_site_ids = member_site_ids_by_required_group.get(group.required_site_group_id, set())
        return [(agg_id, site_id) for agg_id, site_id in aggregator_site_ids if site_id in member_site_ids]

    site_scoped_active_groups: list[SiteScopedSiteControlGroup] = [
        SiteScopedSiteControlGroup(agg_id, site_id, active_group)
        for active_group in active_groups
        for agg_id, site_id in visible_aggregator_site_ids(active_group)
    ]

    site_scoped_deleted_groups = [
        ArchiveSiteScopedSiteControlGroup(agg_id, site_id, deleted_group)
        for deleted_group in deleted_groups
        for agg_id, site_id in visible_aggregator_site_ids(deleted_group)
    ]

    return AggregatorBatchedEntities(
        timestamp,
        SubscriptionResource.SITE_CONTROL_GROUP,
        site_scoped_active_groups,  # type: ignore # SiteScoped variables will work here - tests enforce it
        site_scoped_deleted_groups,  # type: ignore # SiteScoped variables will work here - tests enforce it
    )
