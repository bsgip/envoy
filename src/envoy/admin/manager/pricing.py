"""Managers for pricing/tariff endpoints"""

from datetime import datetime
from typing import List, cast

from envoy_schema.admin.schema.base import BatchCreateResponse
from envoy_schema.admin.schema.pricing import (
    TariffComponentRequest,
    TariffComponentResponse,
    TariffGeneratedRateRequest,
    TariffGeneratedRateResponse,
    TariffRequest,
    TariffResponse,
)
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.admin.crud.pricing import (
    insert_many_tariff_genrate,
    insert_single_tariff,
    select_tariff_ids_for_component_ids,
    update_single_tariff,
)
from envoy.admin.mapper.pricing import TariffComponentMapper, TariffGeneratedRateListMapper, TariffMapper
from envoy.notification.manager.notification import NotificationManager
from envoy.server.crud.pricing import select_all_tariffs, select_single_tariff, select_tariff_component_by_id
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

        await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.TARIFF, changed_time)

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

        await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.TARIFF, changed_time)

    @staticmethod
    async def fetch_tariff(session: AsyncSession, tariff_id: int) -> TariffResponse:
        """Select a singular tariff entry from the DB and map to a TariffResponse object."""
        tariff = await select_single_tariff(session, tariff_id)
        if tariff is None:
            raise NoResultFound
        return TariffMapper.map_to_response(tariff)

    @staticmethod
    async def fetch_many_tariffs(session: AsyncSession, start: int, limit: int) -> list[TariffResponse]:
        """Select many tariff entries from the DB and map to a list of TariffResponse objects"""
        tariff_list = await select_all_tariffs(session, start, datetime.min, limit, None)
        return [TariffMapper.map_to_response(t) for t in tariff_list]


class TariffComponentManager:
    @staticmethod
    async def add_new_tariff_component(session: AsyncSession, tariff_component: TariffComponentRequest) -> int:
        """Map a TariffComponentRequest object to a TariffComponent model and insert into DB.

        Returns the inserted tariff_component_id."""

        changed_time = utc_now()
        tc_model = TariffComponentMapper.map_from_request(changed_time, tariff_component)
        session.add(tc_model)
        await session.commit()

        await NotificationManager.notify_changed_deleted_entities(SubscriptionResource.TARIFF_COMPONENT, changed_time)

        return tc_model.tariff_component_id

    @staticmethod
    async def fetch_tariff_component(session: AsyncSession, tariff_component_id: int) -> TariffComponentResponse:
        """Select a singular tariff entry from the DB and map to a TariffResponse object."""
        tc = await select_tariff_component_by_id(session, tariff_component_id)
        if tc is None:
            raise NoResultFound
        return TariffComponentMapper.map_to_response(tc)


class TariffGeneratedRateManager:
    @staticmethod
    async def add_many_tariff_genrate(
        session: AsyncSession, tariff_genrates: List[TariffGeneratedRateRequest]
    ) -> BatchCreateResponse:
        """Map a TariffGeneratedRateRequest object to a TariffGeneratedRate model and insert into DB.

        Return the IDs of the inserted rates."""

        changed_time = utc_now()

        # We only have the tariff_component_id but to write to the DB - we also need the associated tariff_id
        # so we do these lookups in a batch
        tariff_ids_by_component = await select_tariff_ids_for_component_ids(
            session, (r.tariff_component_id for r in tariff_genrates)
        )

        tariff_genrate_models = TariffGeneratedRateListMapper.map_from_request(
            changed_time, tariff_genrates, tariff_ids_by_component
        )
        insert_ids = await insert_many_tariff_genrate(session, tariff_genrate_models)
        await session.commit()

        await NotificationManager.notify_changed_deleted_entities(
            SubscriptionResource.TARIFF_GENERATED_RATE, changed_time
        )

        return BatchCreateResponse(ids=cast(list[int], insert_ids))
