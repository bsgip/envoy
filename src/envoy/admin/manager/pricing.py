"""Managers for pricing/tariff endpoints"""

from envoy_schema.admin.schema.pricing import (
    TariffGeneratedRateRequest,
    TariffPageResponse,
    TariffRequest,
    TariffResponse,
)
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.pricing import (
    count_all_tariffs,
    insert_single_tariff,
    select_all_tariffs_for_group,
    update_single_tariff,
    upsert_many_tariff_genrate,
)
from envoy.admin.mapper.pricing import TariffGeneratedRateListMapper, TariffMapper
from envoy.notification.manager.notification import NotificationManager
from envoy.server.crud.pricing import select_single_tariff
from envoy.server.manager.time import utc_now
from envoy.server.model.subscription import SubscriptionResource


class TariffManager:
    @staticmethod
    async def add_new_tariff(session: AsyncSession, tariff: TariffRequest) -> int:
        """Map a TariffRequest object to a Tariff model and insert into DB. Return the tariff_id only."""

        changed_time = utc_now()
        tariff_model = TariffMapper.map_from_request(changed_time, tariff)
        await insert_single_tariff(session, tariff_model)
        await session.commit()
        return tariff_model.tariff_id

    @staticmethod
    async def update_existing_tariff(
        session: AsyncSession,
        tariff_id: int,
        tariff: TariffRequest,
    ) -> None:
        """Map a TariffRequest object to a Tariff model and update DB entry."""

        changed_time = utc_now()
        tariff_model = TariffMapper.map_from_request(changed_time, tariff)
        tariff_model.tariff_id = tariff_id
        await update_single_tariff(session, tariff_model)
        await session.commit()

    @staticmethod
    async def fetch_tariff(session: AsyncSession, tariff_id: int) -> TariffResponse:
        """Select a singular tariff entry from the DB and map to a TariffResponse object."""
        tariff = await select_single_tariff(session, tariff_id)
        if tariff is None:
            raise NoResultFound
        return TariffMapper.map_to_response(tariff)


class TariffListManager:
    @staticmethod
    async def fetch_many_tariffs(
        session: AsyncSession, start: int, limit: int, group_filter: str | None
    ) -> TariffPageResponse:
        """Select many tariff entries from the DB and map to a TariffPageResponse.

        group_filter: If specified - only include tariffs that are globally visible or whose required_site_group
            references a SiteGroup with this name"""
        tariff_count = await count_all_tariffs(session, group_filter)
        tariff_list = await select_all_tariffs_for_group(session, group_filter, start, limit)
        return TariffMapper.map_to_page_response(
            total_count=tariff_count, limit=limit, start=start, group=group_filter, tariffs=tariff_list
        )


class TariffGeneratedRateListManager:
    @staticmethod
    async def add_many_tariff_genrate(session: AsyncSession, tariff_genrates: list[TariffGeneratedRateRequest]) -> None:
        """Map a TariffGeneratedRateRequest object to a TariffGeneratedRate model and insert into DB.
        Return the tariff_generated_rate_id only."""

        changed_time = utc_now()
        tariff_genrate_models = TariffGeneratedRateListMapper.map_from_request(changed_time, tariff_genrates)
        await upsert_many_tariff_genrate(session, tariff_genrate_models, changed_time)
        await NotificationManager.notify_changed_deleted_entities(
            session, SubscriptionResource.TARIFF_GENERATED_RATE, changed_time
        )
        await session.commit()
