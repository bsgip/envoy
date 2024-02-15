import logging
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.manager.time import utc_now
from envoy.server.model.aggregator import Aggregator
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.tariff import TariffGeneratedRate

logger = logging.getLogger(__name__)


@dataclass
class HealthCheck:
    """A snapshot of the envoy system health."""

    database_connectivity: bool = False  # true if the database can be queried
    database_has_data: bool = False  # true if the database has a basic configuration


@dataclass
class DynamicPriceCheck:
    """A snapshot of the envoy system health."""

    has_dynamic_prices: bool = False  # true if the database has at least 1 dynamic price
    has_future_prices: bool = False  # true if the database has at least 1 dynamic price for upcoming time periods


@dataclass
class DynamicOperatingEnvelopeCheck:
    """A snapshot of the envoy system health."""

    has_does: bool = False  # true if the database has at least 1 dynamic operating envelope
    has_future_does: bool = False  # true if the database has at least 1 dynamic operating envelope for a future time


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


async def check_dynamic_prices(session: AsyncSession, check: DynamicPriceCheck) -> None:
    """Checks the stored dynamic prices and populates the results to check.

    Any raised exceptions will be caught and logged."""
    try:
        # Look for the first entity whose start time exceeds now - look through more recent entries to hopefully get
        # match more quickly
        now = utc_now()
        future_rate_stmt = (
            select(TariffGeneratedRate)
            .where(TariffGeneratedRate.start_time >= now)
            .order_by(TariffGeneratedRate.tariff_generated_rate_id.desc())
            .limit(1)
        )
        future_rate_resp = await session.execute(future_rate_stmt)

        future_rate = future_rate_resp.one_or_none()
        if future_rate is not None:
            check.has_dynamic_prices = True
            check.has_future_prices = True
            return

        # At this point there's nothing in the future - but maybe we have historical data
        check.has_future_prices = False
        count_rate_stmt = select(func.count()).select_from(TariffGeneratedRate)
        count_rate_resp = await session.execute(count_rate_stmt)
        check.has_dynamic_prices = count_rate_resp.scalar_one() > 0
    except Exception as ex:
        check.has_dynamic_prices = False
        check.has_future_prices = False
        logger.error(f"check_dynamic_prices: Exception checking database for rates {ex}")


async def check_dynamic_operating_envelopes(session: AsyncSession, check: DynamicOperatingEnvelopeCheck) -> None:
    """Checks the stored dynamic operating envelopes and populates the results to check.

    Any raised exceptions will be caught and logged."""
    try:
        # Look for the first entity whose start time exceeds now - look through more recent entries to hopefully get
        # match more quickly
        now = utc_now()
        future_doe_stmt = (
            select(DynamicOperatingEnvelope)
            .where(DynamicOperatingEnvelope.start_time >= now)
            .order_by(DynamicOperatingEnvelope.dynamic_operating_envelope_id.desc())
            .limit(1)
        )
        future_rate_resp = await session.execute(future_doe_stmt)

        future_rate = future_rate_resp.one_or_none()
        if future_rate is not None:
            check.has_does = True
            check.has_future_does = True
            return

        # At this point there's nothing in the future - but maybe we have historical data
        check.has_future_does = False
        count_doe_stmt = select(func.count()).select_from(DynamicOperatingEnvelope)
        count_rate_resp = await session.execute(count_doe_stmt)
        check.has_does = count_rate_resp.scalar_one() > 0
    except Exception as ex:
        check.has_does = False
        check.has_future_does = False
        logger.error(f"check_dynamic_prices: Exception checking database for rates {ex}")
