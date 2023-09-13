import logging
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.aggregator import Aggregator

logger = logging.getLogger(__name__)


@dataclass
class HealthCheck:
    """A snapshot of the envoy system health."""

    database_connectivity: bool = False  # true if the database can be queried
    database_has_data: bool = False  # true if the database has a basic configuration


async def check_database(session: AsyncSession, check: HealthCheck) -> None:
    """Checks the database connection and populates the results to check.

    Any raised exceptions will be caught and logged."""
    try:
        stmt = select(func.count()).select_from(Aggregator)
        resp = await session.execute(stmt)

        check.database_connectivity = True
        check.database_has_data = resp.scalar_one() > 0
    except Exception as ex:
        check.database_connectivity = False
        logger.error(f"check_database: Exception checking database connectivity {ex}")
