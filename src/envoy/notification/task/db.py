from datetime import datetime, timezone
from typing import Annotated, Literal, Union

from taskiq import async_shared_broker

# Taskiq serializes messages to JSON so these substitute for a string enum
ResourceType = Union[Literal["SITE"], Literal["DOE"], Literal["TARIFF"], Literal["READING"]]


async def dependency() -> AsyncGenerator[str, None]:
    print("Startup")
    await asyncio.sleep(0.1)

    yield "value"

    await asyncio.sleep(0.1)
    print("Shutdown")


@async_shared_broker.task()
async def handle_db_upsert(
    context: Annotated[Context, TaskiqDepends()], resource_name: ResourceType, timestamp_epoch: float
) -> None:
    """Call this to notify that a particular timestamp within a particular named resource
    has had a batch of inserts/updates such that requesting all records with that changed_at timestamp
    will yield all resources to be inspected for potentially notifying subscribers

    resource_name: The name of the resource that is being checked for changes
    timestamp: The datetime.timestamp() that will be used for finding resources (must be exact match)"""

    timestamp = datetime.fromtimestamp(timestamp_epoch, tz=timezone.utc)

    session: AsyncSession
