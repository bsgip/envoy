from datetime import datetime
from typing import Optional

from envoy_schema.admin.schema.log import CalculationLogListResponse, CalculationLogRequest, CalculationLogResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.log import (
    count_calculation_logs_for_period,
    select_calculation_log_by_id,
    select_calculation_logs_for_period,
)
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
    async def get_calculation_logs_by_period(
        session: AsyncSession, period_start: datetime, period_end: datetime, start: int, limit: int
    ) -> CalculationLogListResponse:
        """Fetches a the most recent calculation log for the specified interval start"""
        count = await count_calculation_logs_for_period(session, period_start, period_end)
        logs = await select_calculation_logs_for_period(session, period_start, period_end, start, limit)

        return CalculationLogMapper.map_to_list_response(logs, count, start, limit)

    @staticmethod
    async def save_calculation_log(session: AsyncSession, calculation_log: CalculationLogRequest) -> int:
        """Saves the specified calculation_log into the database"""
        changed_time = utc_now()
        new_log = CalculationLogMapper.map_from_request(changed_time, calculation_log)

        session.add(new_log)
        await session.commit()

        return new_log.calculation_log_id
