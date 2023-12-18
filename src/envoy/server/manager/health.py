from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.health import (
    DynamicOperatingEnvelopeCheck,
    DynamicPriceCheck,
    HealthCheck,
    check_database,
    check_dynamic_operating_envelopes,
    check_dynamic_prices,
)


class HealthManager:
    @staticmethod
    async def run_health_check(session: AsyncSession) -> HealthCheck:
        """Runs all health checks for the server"""

        # create a failing check
        check = HealthCheck()

        # run through every check setting it incrementally to non failing
        await check_database(session, check)
        return check

    @staticmethod
    async def run_dynamic_price_check(session: AsyncSession) -> DynamicPriceCheck:
        """Runs all dynamic price checks for the server"""

        # create a failing check
        check = DynamicPriceCheck()

        # run through every check setting it incrementally to non failing
        await check_dynamic_prices(session, check)
        return check

    @staticmethod
    async def run_dynamic_operating_envelope_check(session: AsyncSession) -> DynamicOperatingEnvelopeCheck:
        """Runs all dynamic operating envelope checks for the server"""

        # create a failing check
        check = DynamicOperatingEnvelopeCheck()

        # run through every check setting it incrementally to non failing
        await check_dynamic_operating_envelopes(session, check)
        return check
