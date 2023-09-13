from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.health import HealthCheck, check_database


class HealthManager:
    @staticmethod
    async def run_health_check(session: AsyncSession) -> HealthCheck:
        """Runs all health checks for the server"""

        # create a failing check
        check = HealthCheck()

        # run through every check setting it incrementally to non failing
        await check_database(session, check)

        return check
