from datetime import datetime
from typing import Optional, Sequence, Union, cast

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload, selectinload

from envoy.server.model.log import CalculationLog


async def select_calculation_log_by_id(
    session: AsyncSession, calculation_log_id: int, include_variables: bool, include_labels: bool
) -> Optional[CalculationLog]:
    """Admin fetching of a calculation log by ID - returns the log with (optionally) child entities included

    include_variables - If set, variable_metadata and variable_values will be populated. Otherwise will be set to []
    include_labels - If set, label_metadata and label_values will be populated. Otherwise will be set to []
    """
    stmt = select(CalculationLog).where((CalculationLog.calculation_log_id == calculation_log_id))

    if include_variables and include_labels:
        stmt = stmt.options(
            selectinload(CalculationLog.variable_metadata),
            selectinload(CalculationLog.variable_values),
            selectinload(CalculationLog.label_metadata),
            selectinload(CalculationLog.label_values),
        )
    elif include_variables:
        stmt = stmt.options(
            selectinload(CalculationLog.variable_metadata),
            selectinload(CalculationLog.variable_values),
            noload(CalculationLog.label_metadata),
            noload(CalculationLog.label_values),
        )
    elif include_labels:
        stmt = stmt.options(
            noload(CalculationLog.variable_metadata),
            noload(CalculationLog.variable_values),
            selectinload(CalculationLog.label_metadata),
            selectinload(CalculationLog.label_values),
        )
    else:
        stmt = stmt.options(
            noload(CalculationLog.variable_metadata),
            noload(CalculationLog.variable_values),
            noload(CalculationLog.label_metadata),
            noload(CalculationLog.label_values),
        )

    resp = await session.execute(stmt)
    return resp.scalars().one_or_none()


async def _calculation_logs_for_period(
    is_counting: bool,
    session: AsyncSession,
    period_start: datetime,
    period_end: datetime,
    start: int,
    limit: Optional[int],
) -> Union[Sequence[CalculationLog], int]:

    select_clause: Union[Select[tuple[int]], Select[tuple[CalculationLog]]]
    if is_counting:
        select_clause = select(func.count()).select_from(CalculationLog)
    else:
        select_clause = select(CalculationLog)

    stmt = (
        select_clause.where(
            ~(
                (CalculationLog.calculation_range_start >= period_end)
                | (
                    (
                        CalculationLog.calculation_range_start
                        + func.make_interval(0, 0, 0, 0, 0, 0, CalculationLog.calculation_range_duration_seconds)
                    )
                    <= period_start
                )
            )
        )
        .offset(start)
        .limit(limit)
    )

    if not is_counting:
        stmt = stmt.order_by(CalculationLog.calculation_log_id).options(
            noload(CalculationLog.variable_metadata),
            noload(CalculationLog.variable_values),
            noload(CalculationLog.label_metadata),
            noload(CalculationLog.label_values),
        )

    resp = await session.execute(stmt)
    if is_counting:
        return resp.scalar_one()
    else:
        return resp.scalars().all()


async def count_calculation_logs_for_period(session: AsyncSession, period_start: datetime, period_end: datetime) -> int:
    """Similar to select_calculation_logs_for_period but instead returns the full count of all matching entities"""
    return cast(int, await _calculation_logs_for_period(True, session, period_start, period_end, 0, None))


async def select_calculation_logs_for_period(
    session: AsyncSession, period_start: datetime, period_end: datetime, start: int, limit: int
) -> Sequence[CalculationLog]:
    """Admin fetching of a calculation logs by comparing a calculation log against a period of time. Returns ANY
    calculation log whose start/end times intersect the specified period (start time inclusive, end time exclusive)

    Does NOT include any child logs"""
    return cast(
        Sequence[CalculationLog],
        await _calculation_logs_for_period(False, session, period_start, period_end, start, limit),
    )
