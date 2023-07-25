from datetime import date, datetime

from envoy_schema.server.schema.sep2.der import DERControlListResponse, DERProgramListResponse, DERProgramResponse
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.crud.doe import count_does, count_does_for_day, select_does, select_does_for_day
from envoy.server.crud.end_device import select_single_site_with_site_id
from envoy.server.exception import NotFoundError
from envoy.server.mapper.csip_aus.doe import DERControlMapper, DERProgramMapper


class DERProgramManager:
    @staticmethod
    async def fetch_list_for_site(session: AsyncSession, aggregator_id: int, site_id: int) -> DERProgramListResponse:
        """Program lists are static - this will just return a single fixed Dynamic Operating Envelope Program

        if site_id DNE is inaccessible to aggregator_id a NotFoundError will be raised"""

        site = await select_single_site_with_site_id(session, site_id, aggregator_id)
        if not site:
            raise NotFoundError(f"site_id {site_id} is not accessible / does not exist")

        total_does = await count_does(session, aggregator_id, site_id, datetime.min)
        return DERProgramMapper.doe_program_list_response(site_id, total_does)

    @staticmethod
    async def fetch_doe_program_for_site(session: AsyncSession, aggregator_id: int, site_id: int) -> DERProgramResponse:
        """DOE Programs are static - this will just return a fixed Dynamic Operating Envelope Program

        if site_id DNE is inaccessible to aggregator_id a NotFoundError will be raised"""
        site = await select_single_site_with_site_id(session, site_id, aggregator_id)
        if not site:
            raise NotFoundError(f"site_id {site_id} is not accessible / does not exist")

        total_does = await count_does(session, aggregator_id, site_id, datetime.min)
        return DERProgramMapper.doe_program_response(site_id, total_does)


class DERControlManager:
    @staticmethod
    async def fetch_doe_controls_for_site(
        session: AsyncSession, aggregator_id: int, site_id: int, start: int, changed_after: datetime, limit: int
    ) -> DERControlListResponse:
        """DER Controls are how Dynamic Operating Envelopes are communicated. This will provide a pagination API
        for iterating DOE's stored against a particular site"""

        does = await select_does(session, aggregator_id, site_id, start, changed_after, limit)
        total_count = await count_does(session, aggregator_id, site_id, changed_after)
        return DERControlMapper.map_to_list_response(does, total_count, site_id)

    @staticmethod
    async def fetch_doe_controls_for_site_day(
        session: AsyncSession,
        aggregator_id: int,
        site_id: int,
        day: date,
        start: int,
        changed_after: datetime,
        limit: int,
    ) -> DERControlListResponse:
        """Similar to fetch_doe_controls_for_site but filtered to a specific day (in site local time)"""

        does = await select_does_for_day(session, aggregator_id, site_id, day, start, changed_after, limit)
        total_count = await count_does_for_day(session, aggregator_id, site_id, day, changed_after)
        return DERControlMapper.map_to_list_response(does, total_count, site_id)
