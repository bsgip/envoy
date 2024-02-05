from datetime import datetime, timezone
from typing import Annotated, Literal, Union

from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import TaskiqDepends, async_shared_broker

from envoy.notification.crud.batch import fetch_sites_by_changed_at
from envoy.notification.main import session_dependency
from envoy.server.model.subscription import SubscriptionResource


@async_shared_broker.task()
async def handle_db_upsert(
    session: Annotated[AsyncSession, TaskiqDepends(session_dependency)],
    resource: SubscriptionResource,
    timestamp_epoch: float,
) -> None:
    """Call this to notify that a particular timestamp within a particular named resource
    has had a batch of inserts/updates such that requesting all records with that changed_at timestamp
    will yield all resources to be inspected for potentially notifying subscribers

    resource_name: The name of the resource that is being checked for changes
    timestamp: The datetime.timestamp() that will be used for finding resources (must be exact match)"""

    timestamp = datetime.fromtimestamp(timestamp_epoch, tz=timezone.utc)

    if resource == SubscriptionResource.SITE:
        batched_entities = await fetch_sites_by_changed_at(session, timestamp)
    else:
        raise Exception(f"Unsupported resource type: {resource}")
    
    for (agg_id, entities) in batched_entities.models_by_aggregator_id.items():
        # Generate notifications
