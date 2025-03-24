from datetime import datetime
from typing import Optional, Sequence, Union

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from envoy.server.model.response import DynamicOperatingEnvelopeResponse as DOEResponse
from envoy.server.model.response import TariffGeneratedRateResponse as RateResponse
from envoy.server.model.site import Site


async def select_doe_response_for_scope(
    session: AsyncSession,
    aggregator_id: int,
    site_id: Optional[int],
    doe_response_id: int,
) -> Optional[DOEResponse]:
    """Attempts to fetch a doe response using its' primary key, also scoping it to a particular aggregator/site

    Will populate the "site" relationship

    aggregator_id: The aggregator id to constrain the lookup to
    site_id: If None - no effect otherwise the query will apply a filter on site_id using this value"""

    stmt = (
        select(DOEResponse)
        .join(DOEResponse.site)
        .where(
            (DOEResponse.dynamic_operating_envelope_response_id == doe_response_id)
            & (Site.aggregator_id == aggregator_id)
        )
        .options(selectinload(DOEResponse.site))
    )
    if site_id is not None:
        stmt = stmt.where(DOEResponse.site_id == site_id)

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def select_rate_response_for_scope(
    session: AsyncSession,
    aggregator_id: int,
    site_id: Optional[int],
    tariff_generated_rate_response_id: int,
) -> Optional[RateResponse]:
    """Attempts to fetch a tariff generated rate response using its' primary key, also scoping it to a particular
    aggregator/site

    Will populate the "site" relationship

    aggregator_id: The aggregator id to constrain the lookup to
    site_id: If None - no effect otherwise the query will apply a filter on site_id using this value"""

    stmt = (
        select(RateResponse)
        .join(RateResponse.site)
        .where(
            (RateResponse.tariff_generated_rate_response_id == tariff_generated_rate_response_id)
            & (Site.aggregator_id == aggregator_id)
        )
        .options(selectinload(RateResponse.site))
    )
    if site_id is not None:
        stmt = stmt.where(RateResponse.site_id == site_id)

    resp = await session.execute(stmt)
    return resp.scalar_one_or_none()


async def _doe_responses(
    is_counting: bool,
    session: AsyncSession,
    aggregator_id: int,
    site_id: Optional[int],
    start: int,
    limit: Optional[int],
    created_after: datetime,
) -> Union[Sequence[DOEResponse], int]:
    """Internal utility for fetching doe responses

    site_id: If None - no site_id filter applied, otherwise filter on site_id = Value

    Orders by 2030.5 requirements on Response which is created DESC, site_id ASC

    Will populate the "site" relationship for all returned entities"""

    select_clause: Union[Select[tuple[int]], Select[tuple[DOEResponse]]]
    if is_counting:
        select_clause = select(func.count()).select_from(DOEResponse)
    else:
        select_clause = select(DOEResponse).options(selectinload(DOEResponse.site))

    # fmt: off
    stmt = (
        select_clause
        .join(DOEResponse.site)
        .where(
            (DOEResponse.created_time >= created_after) &
            (Site.aggregator_id == aggregator_id))
        .offset(start)
        .limit(limit)
    )
    # fmt: on

    if site_id is not None:
        stmt = stmt.where(DOEResponse.site_id == site_id)

    if not is_counting:
        stmt = stmt.order_by(DOEResponse.created_time.desc(), DOEResponse.site_id.asc())

    resp = await session.execute(stmt)
    if is_counting:
        return resp.scalar_one()
    else:
        return resp.scalars().all()


async def _rate_responses(
    is_counting: bool,
    session: AsyncSession,
    aggregator_id: int,
    site_id: Optional[int],
    start: int,
    limit: Optional[int],
    created_after: datetime,
) -> Union[Sequence[RateResponse], int]:
    """Internal utility for fetching rate responses's

    site_id: If None - no site_id filter applied, otherwise filter on site_id = Value

    Orders by 2030.5 requirements on Response which is created DESC, site_id ASC

    Will populate the "site" relationship for all returned entities"""

    select_clause: Union[Select[tuple[int]], Select[tuple[RateResponse]]]
    if is_counting:
        select_clause = select(func.count()).select_from(RateResponse)
    else:
        select_clause = select(RateResponse).options(selectinload(RateResponse.site))

    # fmt: off
    stmt = (
        select_clause
        .join(RateResponse.site)
        .where(
            (RateResponse.created_time >= created_after) &
            (Site.aggregator_id == aggregator_id))
        .offset(start)
        .limit(limit)
    )
    # fmt: on

    if site_id is not None:
        stmt = stmt.where(RateResponse.site_id == site_id)

    if not is_counting:
        stmt = stmt.order_by(RateResponse.created_time.desc(), RateResponse.site_id.asc())

    resp = await session.execute(stmt)
    if is_counting:
        return resp.scalar_one()
    else:
        return resp.scalars().all()


async def count_doe_responses(
    session: AsyncSession, aggregator_id: int, site_id: Optional[int], created_after: datetime
) -> int:
    """Fetches the number of DynamicOperatingEnvelopeResponse's stored.

    created_after: Only responses with a created_time greater than this value will be counted (0 will count everything)
    """

    return await _doe_responses(
        True, session, aggregator_id, site_id, 0, None, created_after
    )  # type: ignore [return-value]  # Test coverage will ensure that it's an int and not an entity


async def select_doe_responses(
    session: AsyncSession, aggregator_id: int, site_id: Optional[int], start: int, limit: int, created_after: datetime
) -> Sequence[DOEResponse]:
    """Selects DynamicOperatingEnvelopeResponse entities (with pagination). Will populate the "site" relationship for
    all returned entities.

    site_id: The specific site does responses are being requested for
    start: The number of matching entities to skip
    limit: The maximum number of entities to return
    created_after: removes any entities with a changed_date BEFORE this value (set to datetime.min to not filter)

    Orders by 2030.5 requirements on Response which is created DESC, site ASC"""

    return await _doe_responses(
        False, session, aggregator_id, site_id, start, limit, created_after
    )  # type: ignore [return-value]  # Test coverage will ensure that it's an entity list


async def count_tariff_generated_rate_responses(
    session: AsyncSession, aggregator_id: int, site_id: Optional[int], created_after: datetime
) -> int:
    """Fetches the number of TariffGeneratedRateResponse's stored.

    created_after: Only responses with a created_time greater than this value will be counted (0 will count everything)
    """

    return await _rate_responses(
        True, session, aggregator_id, site_id, 0, None, created_after
    )  # type: ignore [return-value]  # Test coverage will ensure that it's an int and not an entity


async def select_tariff_generated_rate_responses(
    session: AsyncSession, aggregator_id: int, site_id: Optional[int], start: int, limit: int, created_after: datetime
) -> Sequence[RateResponse]:
    """Selects TariffGeneratedRateResponse entities (with pagination). Will populate the "site" relationship for all
    returned entities

    site_id: The specific site rate responses are being requested for
    start: The number of matching entities to skip
    limit: The maximum number of entities to return
    created_after: removes any entities with a changed_date BEFORE this value (set to datetime.min to not filter)

    Orders by 2030.5 requirements on Response which is created DESC, site ASC"""

    return await _rate_responses(
        False, session, aggregator_id, site_id, start, limit, created_after
    )  # type: ignore [return-value]  # Test coverage will ensure that it's an entity list
