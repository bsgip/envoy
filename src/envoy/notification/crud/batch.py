from datetime import datetime
from typing import Generic, Optional, Sequence, TypeVar, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.subscription import Subscription, SubscriptionResource
from envoy.server.model.tariff import TariffGeneratedRate

TResourceModel = TypeVar(
    "TResourceModel", bound=Union[Site, DynamicOperatingEnvelope, TariffGeneratedRate, SiteReading]
)


class AggregatorBatchedEntities(Generic[TResourceModel]):
    """A set of TResourceModel entities keyed by their aggregator ID"""

    timestamp: datetime
    models_by_aggregator_id: dict[int, list[TResourceModel]]

    def __init__(self, timestamp: datetime, models: Sequence[TResourceModel]) -> None:
        super().__init__()

        self.timestamp = timestamp

        self.models_by_aggregator_id = {}
        for m in models:
            agg_id: Optional[int] = getattr(m, "aggregator_id", None)
            if agg_id is None:
                rt: Optional[SiteReadingType] = getattr(m, "site_reading_type", None)
                if rt is None:
                    raise Exception(f"Unable to discover aggregator_id for {m}")
                agg_id = rt.aggregator_id

            grouped_models: Optional[list[TResourceModel]] = self.models_by_aggregator_id.get(agg_id, None)
            if grouped_models is None:
                self.models_by_aggregator_id[agg_id] = [m]
            else:
                grouped_models.append(m)


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


async def fetch_sites_by_changed_at(session: AsyncSession, timestamp: datetime) -> AggregatorBatchedEntities[Site]:
    """Fetches all sites matching the specified changed_at and returns them keyed by their aggregator_id"""

    stmt = select(Site, Site.timezone_id).where(Site.changed_time == timestamp)
    resp = await session.execute(stmt)
    return AggregatorBatchedEntities(timestamp, resp.scalars().all())
