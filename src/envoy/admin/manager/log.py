from datetime import datetime
from typing import Optional

from envoy_schema.admin.schema.log import CalculationLogRequest, CalculationLogResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.log import select_calculation_log_by_id, select_most_recent_calculation_log_for_interval_start
from envoy.admin.mapper.log import CalculationLogMapper
from envoy.server.manager.time import utc_now


class CalculationLogManager:
    @staticmethod
    async def get_calculation_log_by_id(
        session: AsyncSession, calculation_log_id: int
    ) -> Optional[CalculationLogResponse]:
        """Fetches a specific calculation log with a specific ID"""
        log = await select_calculation_log_by_id(session, calculation_log_id)
        if log is None:
            return log
        return CalculationLogMapper.map_to_response(log)

    @staticmethod
    async def get_calculation_log_by_interval_start(
        session: AsyncSession, interval_start: datetime
    ) -> Optional[CalculationLogResponse]:
        """Fetches a the most recent calculation log for the specified interval start"""
        log = await select_most_recent_calculation_log_for_interval_start(session, interval_start)
        if log is None:
            return log
        return CalculationLogMapper.map_to_response(log)

    @staticmethod
    async def save_calculation_log(session: AsyncSession, calculation_log: CalculationLogRequest) -> int:
        """Saves the specified calculation_log into the database"""
        changed_time = utc_now()
        new_log = CalculationLogMapper.map_from_request(changed_time, calculation_log)

        session.add(new_log)
        await session.commit()

        return new_log.calculation_log_id
