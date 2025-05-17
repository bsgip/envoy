from datetime import datetime
from itertools import chain
from typing import Any, Generic, Iterable, Sequence, Union, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.notification.crud.archive import (
    fetch_entities_with_archive_by_datetime,
    fetch_entities_with_archive_by_id,
    orm_relationship_map_parent_entities,
)
from envoy.notification.crud.common import TArchiveResourceModel, TResourceModel
from envoy.notification.exception import NotificationError
from envoy.server.crud.common import localize_start_time_for_entity
from envoy.server.manager.der_constants import PUBLIC_SITE_DER_ID
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
from envoy.server.model.archive.tariff import ArchiveTariffGeneratedRate
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site, SiteDER, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.subscription import Subscription, SubscriptionResource
from envoy.server.model.tariff import TariffGeneratedRate


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


def get_batch_key(resource: SubscriptionResource, entity: TResourceModel) -> tuple:
    """
    Gets a multipart key in the form of a tuple that describes entity as a single sep2 resource. This is because
    sep2 Notifications are only sent out underneath a single resource (eg /edev/3/derp/doe/derc/1) which means all
    notifications we generate MUST be grouped by this batch key

    NOTE - the first element of every tuple will be aggregator_id

    Given the SubscriptionResource - it's safe to rely on the ordering of the batch key tuple entries:

    SubscriptionResource.SITE: (aggregator_id: int, site_id: int)
    SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE: (aggregator_id: int, site_id: int, site_control_group_id: int)
    SubscriptionResource.READING: (aggregator_id: int, site_id: int, site_reading_type_id: int)
    SubscriptionResource.TARIFF_GENERATED_RATE: (aggregator_id: int, tariff_id: int, site_id: int, day: date)
    SubscriptionResource.SITE_DER_AVAILABILITY: (aggregator_id: int, site_id: int, site_der_id: int)
    SubscriptionResource.SITE_DER_RATING: (aggregator_id: int, site_id: int, site_der_id: int)
    SubscriptionResource.SITE_DER_SETTING: (aggregator_id: int, site_id: int, site_der_id: int)
    SubscriptionResource.SITE_DER_STATUS: (aggregator_id: int, site_id: int, site_der_id: int)
    SubscriptionResource.SUBSCRIPTION: (aggregator_id: int, subscription_id: int)
    """
    if resource == SubscriptionResource.SITE:
        site: Site = cast(Site, entity)  # type: ignore # Pretty sure this is a mypy quirk
        return (site.aggregator_id, site.site_id)
    elif resource == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
        doe = cast(DynamicOperatingEnvelope, entity)  # type: ignore # Pretty sure this is a mypy quirk
        return (doe.site.aggregator_id, doe.site_id, doe.site_control_group_id)
    elif resource == SubscriptionResource.READING:
        reading = cast(SiteReading, entity)  # type: ignore # Pretty sure this is a mypy quirk
        return (
            reading.site_reading_type.aggregator_id,
            reading.site_reading_type.site_id,
            reading.site_reading_type.site_reading_type_id,
        )
    elif resource == SubscriptionResource.TARIFF_GENERATED_RATE:
        rate = cast(TariffGeneratedRate, entity)  # type: ignore # Pretty sure this is a mypy quirk
        return (rate.site.aggregator_id, rate.tariff_id, rate.site_id, rate.start_time.date())
    elif resource == SubscriptionResource.SITE_DER_AVAILABILITY:
        availability = cast(SiteDERAvailability, entity)  # type: ignore # Pretty sure this is a mypy quirk
        return (availability.site_der.site.aggregator_id, availability.site_der.site_id, PUBLIC_SITE_DER_ID)
    elif resource == SubscriptionResource.SITE_DER_RATING:
        rating = cast(SiteDERRating, entity)  # type: ignore # Pretty sure this is a mypy quirk
        return (rating.site_der.site.aggregator_id, rating.site_der.site_id, PUBLIC_SITE_DER_ID)
    elif resource == SubscriptionResource.SITE_DER_SETTING:
        setting = cast(SiteDERSetting, entity)  # type: ignore # Pretty sure this is a mypy quirk
        return (setting.site_der.site.aggregator_id, setting.site_der.site_id, PUBLIC_SITE_DER_ID)
    elif resource == SubscriptionResource.SITE_DER_STATUS:
        status = cast(SiteDERStatus, entity)  # type: ignore # Pretty sure this is a mypy quirk
        return (status.site_der.site.aggregator_id, status.site_der.site_id, PUBLIC_SITE_DER_ID)
    else:
        raise NotificationError(f"{resource} is unsupported - unable to identify appropriate batch key")


def get_subscription_filter_id(resource: SubscriptionResource, entity: TResourceModel) -> int:
    """Means of disambiguating the "subscription filter" id for TResourceModel. This is the field
    that Subscription.resource_id will filter on (if specified). This practically allows subscriptions
    to apply to only a subset of entities"""
    if resource == SubscriptionResource.SITE:
        # Site lists subscriptions can be scoped to a single site
        return cast(Site, entity).site_id  # type: ignore # Pretty sure this is a mypy quirk
    elif resource == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
        # DOE subscriptions can be scoped to a single DERP
        return cast(DynamicOperatingEnvelope, entity).site_control_group_id  # type: ignore # mypy quirk
    elif resource == SubscriptionResource.READING:
        # Reading subscriptions can be scoped to the overarching type
        return cast(SiteReading, entity).site_reading_type_id  # type: ignore # Pretty sure this is a mypy quirk
    elif resource == SubscriptionResource.TARIFF_GENERATED_RATE:
        # rate subscriptions can be scoped to a single tariff
        return cast(TariffGeneratedRate, entity).tariff_id  # type: ignore # Pretty sure this is a mypy quirk
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
    else:
        raise NotificationError(f"{resource} is unsupported - unable to identify appropriate primary key")


def get_site_id(resource: SubscriptionResource, entity: TResourceModel) -> int:
    """Means of disambiguating the site id for TResourceModel"""
    if resource == SubscriptionResource.SITE:
        return cast(Site, entity).site_id  # type: ignore # Pretty sure this is a mypy quirk
    elif resource == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
        return cast(DynamicOperatingEnvelope, entity).site_id  # type: ignore # Pretty sure this is a mypy quirk
    elif resource == SubscriptionResource.READING:
        return cast(SiteReading, entity).site_reading_type.site_id  # type: ignore # Pretty sure this is a mypy quirk
    elif resource == SubscriptionResource.TARIFF_GENERATED_RATE:
        return cast(TariffGeneratedRate, entity).site_id  # type: ignore # Pretty sure this is a mypy quirk
    elif resource == SubscriptionResource.SITE_DER_AVAILABILITY:
        return cast(SiteDERAvailability, entity).site_der.site_id  # type: ignore # Pretty sure this is a mypy quirk
    elif resource == SubscriptionResource.SITE_DER_RATING:
        return cast(SiteDERRating, entity).site_der.site_id  # type: ignore # Pretty sure this is a mypy quirk
    elif resource == SubscriptionResource.SITE_DER_SETTING:
        return cast(SiteDERSetting, entity).site_der.site_id  # type: ignore # Pretty sure this is a mypy quirk
    elif resource == SubscriptionResource.SITE_DER_STATUS:
        return cast(SiteDERStatus, entity).site_der.site_id  # type: ignore # Pretty sure this is a mypy quirk
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

    Also fetches any site from the archive that was deleted at the specified timestamp"""

    active_sites, deleted_sites = await fetch_entities_with_archive_by_datetime(session, Site, ArchiveSite, timestamp)

    return AggregatorBatchedEntities(timestamp, SubscriptionResource.SITE, active_sites, deleted_sites)


async def fetch_rates_by_changed_at(
    session: AsyncSession, timestamp: datetime
) -> AggregatorBatchedEntities[TariffGeneratedRate, ArchiveTariffGeneratedRate]:
    """Fetches all rates matching the specified changed_at and returns them keyed by their aggregator/site id

    Will include the TariffGeneratedRate.site relationship

    Also fetches any site from the archive that was deleted at the specified timestamp"""

    active_rates, deleted_rates = await fetch_entities_with_archive_by_datetime(
        session, TariffGeneratedRate, ArchiveTariffGeneratedRate, timestamp
    )

    referenced_site_ids = {
        e.site_id
        for e in cast(
            Iterable[Union[TariffGeneratedRate, ArchiveTariffGeneratedRate]], chain(active_rates, deleted_rates)
        )
    }

    active_sites, deleted_sites = await fetch_entities_with_archive_by_id(
        session, Site, ArchiveSite, referenced_site_ids
    )

    # Map the "site" relationship
    orm_relationship_map_parent_entities(
        cast(Iterable[Union[TariffGeneratedRate, ArchiveTariffGeneratedRate]], chain(active_rates, deleted_rates)),
        lambda e: e.site_id,
        {e.site_id: e for e in cast(Iterable[Union[Site, ArchiveSite]], chain(active_sites, deleted_sites))},
        "site",
    )

    # localize start times using the new "site" relationship
    for e in cast(Iterable[TariffGeneratedRate], chain(active_rates, deleted_rates)):
        localize_start_time_for_entity(e, e.site.timezone_id)

    return AggregatorBatchedEntities(timestamp, SubscriptionResource.TARIFF_GENERATED_RATE, active_rates, deleted_rates)


async def fetch_does_by_changed_at(
    session: AsyncSession, timestamp: datetime
) -> AggregatorBatchedEntities[DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope]:
    """Fetches all DOEs matching the specified changed_at and returns them keyed by their aggregator/site id

    Will include the DynamicOperatingEnvelope.site relationship

    Also fetches any site from the archive that was deleted at the specified timestamp"""

    active_does, deleted_does = await fetch_entities_with_archive_by_datetime(
        session, DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope, timestamp
    )

    referenced_site_ids = {
        e.site_id
        for e in cast(
            Iterable[Union[DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope]], chain(active_does, deleted_does)
        )
    }

    active_sites, deleted_sites = await fetch_entities_with_archive_by_id(
        session, Site, ArchiveSite, referenced_site_ids
    )

    # Map the "site" relationship
    orm_relationship_map_parent_entities(
        cast(
            Iterable[Union[DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope]], chain(active_does, deleted_does)
        ),
        lambda e: e.site_id,
        {e.site_id: e for e in cast(Iterable[Union[Site, ArchiveSite]], chain(active_sites, deleted_sites))},
        "site",
    )

    # localize start times using the new "site" relationship
    for e in cast(Iterable[DynamicOperatingEnvelope], chain(active_does, deleted_does)):
        localize_start_time_for_entity(e, e.site.timezone_id)

    return AggregatorBatchedEntities(
        timestamp, SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE, active_does, deleted_does
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
            Iterable[Union[SiteReading, ArchiveSiteReading]],
            chain(active_readings, deleted_readings),
        )
    }

    active_site_reading_types, deleted_site_reading_types = await fetch_entities_with_archive_by_id(
        session, SiteReadingType, ArchiveSiteReadingType, referenced_site_reading_type_ids
    )

    # Map the "site_reading_type" relationship
    orm_relationship_map_parent_entities(
        cast(
            Iterable[Union[SiteReading, ArchiveSiteReading]],
            chain(active_readings, deleted_readings),
        ),
        lambda e: e.site_reading_type_id,
        {
            e.site_reading_type_id: e
            for e in cast(
                Iterable[Union[SiteReadingType, ArchiveSiteReadingType]],
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

    Will include the SiteDERAvailability.site_der relationship and SiteDER.site relationship"""

    active_der_avails, deleted_der_avails = await fetch_entities_with_archive_by_datetime(
        session, SiteDERAvailability, ArchiveSiteDERAvailability, timestamp
    )

    referenced_site_der_ids = {
        e.site_der_id
        for e in cast(
            Iterable[Union[SiteDERAvailability, ArchiveSiteDERAvailability]],
            chain(active_der_avails, deleted_der_avails),
        )
    }

    active_site_ders, deleted_site_ders = await fetch_entities_with_archive_by_id(
        session, SiteDER, ArchiveSiteDER, referenced_site_der_ids
    )

    # Map the "site_der" relationship
    orm_relationship_map_parent_entities(
        cast(
            Iterable[Union[SiteDERAvailability, ArchiveSiteDERAvailability]],
            chain(active_der_avails, deleted_der_avails),
        ),
        lambda e: e.site_der_id,
        {
            e.site_der_id: e
            for e in cast(Iterable[Union[SiteDER, ArchiveSiteDER]], chain(active_site_ders, deleted_site_ders))
        },
        "site_der",
    )

    # Now repeat again but for the site relationships on the site_der
    referenced_site_ids = {
        e.site_id
        for e in cast(
            Iterable[Union[SiteDER, ArchiveSiteDER]],
            chain(active_site_ders, deleted_site_ders),
        )
    }

    active_sites, deleted_sites = await fetch_entities_with_archive_by_id(
        session, Site, ArchiveSite, referenced_site_ids
    )

    # Map the "site" relationship for every site_der
    all_site_ders = (cast(SiteDERAvailability, e).site_der for e in chain(active_der_avails, deleted_der_avails))
    orm_relationship_map_parent_entities(
        all_site_ders,
        lambda e: e.site_id,
        {e.site_id: e for e in cast(Iterable[Union[Site, ArchiveSite]], chain(active_sites, deleted_sites))},
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

    Will include the SiteDERRating.site_der relationship and SiteDER.site relationship"""

    active_der_ratings, deleted_der_ratings = await fetch_entities_with_archive_by_datetime(
        session, SiteDERRating, ArchiveSiteDERRating, timestamp
    )

    referenced_site_der_ids = {
        e.site_der_id
        for e in cast(
            Iterable[Union[SiteDERRating, ArchiveSiteDERRating]],
            chain(active_der_ratings, deleted_der_ratings),
        )
    }

    active_site_ders, deleted_site_ders = await fetch_entities_with_archive_by_id(
        session, SiteDER, ArchiveSiteDER, referenced_site_der_ids
    )

    # Map the "site_der" relationship
    orm_relationship_map_parent_entities(
        cast(
            Iterable[Union[SiteDERRating, ArchiveSiteDERRating]],
            chain(active_der_ratings, deleted_der_ratings),
        ),
        lambda e: e.site_der_id,
        {
            e.site_der_id: e
            for e in cast(Iterable[Union[SiteDER, ArchiveSiteDER]], chain(active_site_ders, deleted_site_ders))
        },
        "site_der",
    )

    # Now repeat again but for the site relationships on the site_der
    referenced_site_ids = {
        e.site_id
        for e in cast(
            Iterable[Union[SiteDER, ArchiveSiteDER]],
            chain(active_site_ders, deleted_site_ders),
        )
    }

    active_sites, deleted_sites = await fetch_entities_with_archive_by_id(
        session, Site, ArchiveSite, referenced_site_ids
    )

    # Map the "site" relationship for every site_der
    all_site_ders = (cast(SiteDERRating, e).site_der for e in chain(active_der_ratings, deleted_der_ratings))
    orm_relationship_map_parent_entities(
        all_site_ders,
        lambda e: e.site_id,
        {e.site_id: e for e in cast(Iterable[Union[Site, ArchiveSite]], chain(active_sites, deleted_sites))},
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

    Will include the SiteDERSetting.site_der relationship and SiteDER.site relationship"""

    active_der_settings, deleted_der_settings = await fetch_entities_with_archive_by_datetime(
        session, SiteDERSetting, ArchiveSiteDERSetting, timestamp
    )

    referenced_site_der_ids = {
        e.site_der_id
        for e in cast(
            Iterable[Union[SiteDERSetting, ArchiveSiteDERSetting]],
            chain(active_der_settings, deleted_der_settings),
        )
    }

    active_site_ders, deleted_site_ders = await fetch_entities_with_archive_by_id(
        session, SiteDER, ArchiveSiteDER, referenced_site_der_ids
    )

    # Map the "site_der" relationship
    orm_relationship_map_parent_entities(
        cast(
            Iterable[Union[SiteDERSetting, ArchiveSiteDERSetting]],
            chain(active_der_settings, deleted_der_settings),
        ),
        lambda e: e.site_der_id,
        {
            e.site_der_id: e
            for e in cast(Iterable[Union[SiteDER, ArchiveSiteDER]], chain(active_site_ders, deleted_site_ders))
        },
        "site_der",
    )

    # Now repeat again but for the site relationships on the site_der
    referenced_site_ids = {
        e.site_id
        for e in cast(
            Iterable[Union[SiteDER, ArchiveSiteDER]],
            chain(active_site_ders, deleted_site_ders),
        )
    }

    active_sites, deleted_sites = await fetch_entities_with_archive_by_id(
        session, Site, ArchiveSite, referenced_site_ids
    )

    # Map the "site" relationship for every site_der
    all_site_ders = (cast(SiteDERSetting, e).site_der for e in chain(active_der_settings, deleted_der_settings))
    orm_relationship_map_parent_entities(
        all_site_ders,
        lambda e: e.site_id,
        {e.site_id: e for e in cast(Iterable[Union[Site, ArchiveSite]], chain(active_sites, deleted_sites))},
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

    Will include the SiteDERStatus.site_der relationship and SiteDER.site relationship"""

    active_der_statuses, deleted_der_statuses = await fetch_entities_with_archive_by_datetime(
        session, SiteDERStatus, ArchiveSiteDERStatus, timestamp
    )

    referenced_site_der_ids = {
        e.site_der_id
        for e in cast(
            Iterable[Union[SiteDERStatus, ArchiveSiteDERStatus]],
            chain(active_der_statuses, deleted_der_statuses),
        )
    }

    active_site_ders, deleted_site_ders = await fetch_entities_with_archive_by_id(
        session, SiteDER, ArchiveSiteDER, referenced_site_der_ids
    )

    # Map the "site_der" relationship
    orm_relationship_map_parent_entities(
        cast(
            Iterable[Union[SiteDERStatus, ArchiveSiteDERStatus]],
            chain(active_der_statuses, deleted_der_statuses),
        ),
        lambda e: e.site_der_id,
        {
            e.site_der_id: e
            for e in cast(Iterable[Union[SiteDER, ArchiveSiteDER]], chain(active_site_ders, deleted_site_ders))
        },
        "site_der",
    )

    # Now repeat again but for the site relationships on the site_der
    referenced_site_ids = {
        e.site_id
        for e in cast(
            Iterable[Union[SiteDER, ArchiveSiteDER]],
            chain(active_site_ders, deleted_site_ders),
        )
    }

    active_sites, deleted_sites = await fetch_entities_with_archive_by_id(
        session, Site, ArchiveSite, referenced_site_ids
    )

    # Map the "site" relationship for every site_der
    all_site_ders = (cast(SiteDERStatus, e).site_der for e in chain(active_der_statuses, deleted_der_statuses))
    orm_relationship_map_parent_entities(
        all_site_ders,
        lambda e: e.site_id,
        {e.site_id: e for e in cast(Iterable[Union[Site, ArchiveSite]], chain(active_sites, deleted_sites))},
        "site",
    )

    return AggregatorBatchedEntities(
        timestamp, SubscriptionResource.SITE_DER_STATUS, active_der_statuses, deleted_der_statuses
    )
