from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.model.log import CalculationLog


async def select_calculation_log_by_id(session: AsyncSession, calculation_log_id: int) -> Optional[CalculationLog]:
    """Admin fetching of a calculation log by ID - returns the log with all child entities included"""
    stmt = (
        select(CalculationLog)
        .where((CalculationLog.calculation_log_id == calculation_log_id))
        .options(
            selectinload(CalculationLog.weather_forecast_logs),
            selectinload(CalculationLog.power_flow_logs),
            selectinload(CalculationLog.power_target_logs),
            selectinload(CalculationLog.power_forecast_logs),
        )
    )

    resp = await session.execute(stmt)
    return resp.scalars().one_or_none()


async def select_most_recent_calculation_log_for_interval_start(
    session: AsyncSession, calculation_interval_start: datetime
) -> Optional[CalculationLog]:
    """Admin fetching of a calculation log by calculation interval date. Fetches the most recent calculation log
    for the interval date

    returns the log with all child entities included"""
    stmt = (
        select(CalculationLog)
        .where((CalculationLog.calculation_interval_start == calculation_interval_start))
        .order_by(CalculationLog.created_time.desc())
        .limit(1)
        .options(
            selectinload(CalculationLog.weather_forecast_logs),
            selectinload(CalculationLog.power_flow_logs),
            selectinload(CalculationLog.power_target_logs),
            selectinload(CalculationLog.power_forecast_logs),
        )
    )

    resp = await session.execute(stmt)
    return resp.scalars().one_or_none()
