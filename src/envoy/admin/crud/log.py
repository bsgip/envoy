from collections.abc import Sequence
from datetime import datetime
from typing import cast

from sqlalchemy import Select, func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value

from envoy.server.model.log import CalculationLog

VARIABLE_RELATIONSHIPS = ("variable_metadata", "variable_values")
LABEL_RELATIONSHIPS = ("label_metadata", "label_values")


def _set_unloaded_relationships_empty(calculation_log: CalculationLog, relationships: Sequence[str]) -> None:
    """Populates the specified relationships with an empty list (without emitting any SQL) if they haven't already
    been loaded. This is a replacement for the (deprecated) noload() loader option."""
    loaded_state = inspect(calculation_log).dict
    for relationship in relationships:
        if relationship not in loaded_state:
            set_committed_value(calculation_log, relationship, [])


async def select_calculation_log_by_id(
    session: AsyncSession, calculation_log_id: int, include_variables: bool, include_labels: bool
) -> CalculationLog | None:
    """Admin fetching of a calculation log by ID - returns the log with (optionally) child entities included

    include_variables - If set, variable_metadata and variable_values will be populated. Otherwise will be set to []
    include_labels - If set, label_metadata and label_values will be populated. Otherwise will be set to []
    """
    stmt = select(CalculationLog).where(CalculationLog.calculation_log_id == calculation_log_id)

    if include_variables:
        stmt = stmt.options(
            selectinload(CalculationLog.variable_metadata),
            selectinload(CalculationLog.variable_values),
        )
    if include_labels:
        stmt = stmt.options(
            selectinload(CalculationLog.label_metadata),
            selectinload(CalculationLog.label_values),
        )

    resp = await session.execute(stmt)
    calculation_log = resp.scalars().one_or_none()
    if calculation_log is not None:
        if not include_variables:
            _set_unloaded_relationships_empty(calculation_log, VARIABLE_RELATIONSHIPS)
        if not include_labels:
            _set_unloaded_relationships_empty(calculation_log, LABEL_RELATIONSHIPS)
    return calculation_log


async def _calculation_logs_for_period(
    is_counting: bool,
    session: AsyncSession,
    period_start: datetime,
    period_end: datetime,
    start: int,
    limit: int | None,
) -> Sequence[CalculationLog] | int:

    select_clause: Select[int] | Select[CalculationLog]
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
        stmt = stmt.order_by(CalculationLog.calculation_log_id)

    resp = await session.execute(stmt)
    if is_counting:
        return resp.scalar_one()
    else:
        calculation_logs = resp.scalars().all()
        for calculation_log in calculation_logs:
            _set_unloaded_relationships_empty(calculation_log, VARIABLE_RELATIONSHIPS + LABEL_RELATIONSHIPS)
        return calculation_logs


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
