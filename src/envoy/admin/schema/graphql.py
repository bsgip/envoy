import logging
from asyncio import AbstractEventLoop, Future
from typing import Any, Callable, Coroutine, List, MutableMapping, Optional, Union

import graphene
from aiodataloader import CacheKeyT, DataLoader
from graphene_sqlalchemy import SQLAlchemyObjectType
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.aggregator import Aggregator
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.tariff import TariffGeneratedRate

# from sqlalchemy.orm import

logging.basicConfig()
logger = logging.getLogger("sqlalchemy.engine")
logger.setLevel(logging.DEBUG)
# TODO: Bacon - remove the above logging

# Data Loaders


class AggregatorLoader(DataLoader):
    session: AsyncSession

    def __init__(
        self,
        session: AsyncSession,
        batch_load_fn: Callable[[List], Coroutine[Any, Any, List]] | None = None,
        batch: bool | None = None,
        max_batch_size: int | None = None,
        cache: bool | None = None,
        get_cache_key: Callable[[Any], CacheKeyT | Any] | None = None,
        cache_map: MutableMapping[CacheKeyT | Any, Future] | None = None,
        loop: AbstractEventLoop | None = None,
    ):
        super().__init__(batch_load_fn, batch, max_batch_size, cache, get_cache_key, cache_map, loop)
        self.session = session

    async def batch_load_fn(self, keys: list[int]):
        # TODO: This will need to ensure the resulting list has a 1-1 correspondence with keys (inserting None if req'd)
        #       We can do this with a general purpose utility fn
        query = select(Aggregator).where(Aggregator.aggregator_id.in_(keys))
        result = await self.session.execute(query)
        foo = result.scalars().all()
        return foo


# Schema Types


class AggregatorSchemaType(SQLAlchemyObjectType):
    class Meta:
        model = Aggregator


class DynamicOperatingEnvelopeSchemaType(SQLAlchemyObjectType):
    class Meta:
        model = DynamicOperatingEnvelope


class SiteSchemaType(SQLAlchemyObjectType):
    class Meta:
        model = Site

    async def resolve_aggregator(self: Site, info: graphene.ResolveInfo):
        aggregator_loader: AggregatorLoader = info.context["aggregator_loader"]
        return await aggregator_loader.load(self.aggregator_id)
        # query = AggregatorSchemaType.get_query(info).where(Aggregator.aggregator_id == self.aggregator_id)
        # session: AsyncSession = info.context["session"]
        # result = await session.execute(query)
        # foo = result.scalars().one_or_none()
        # return foo


class TariffGeneratedRateSchemaType(SQLAlchemyObjectType):
    class Meta:
        model = TariffGeneratedRate


class SiteReadingTypeSchemaType(SQLAlchemyObjectType):
    class Meta:
        model = SiteReadingType


class SiteReadingSchemaType(SQLAlchemyObjectType):
    class Meta:
        model = SiteReading


# Queries


class Query(graphene.ObjectType):
    aggregators = graphene.List(AggregatorSchemaType)
    sites = graphene.PageInfo
    does = graphene.List(DynamicOperatingEnvelopeSchemaType)
    reading_types = graphene.List(SiteReadingTypeSchemaType)
    readings = graphene.List(SiteReadingSchemaType)

    sites_by_id = graphene.Field(graphene.List(SiteSchemaType), site_id=graphene.Int(required=True))

    async def resolve_sites_by_id(self, info: graphene.ResolveInfo, site_id: int):
        query = SiteSchemaType.get_query(info).where(Site.site_id == site_id)
        session: AsyncSession = info.context["session"]
        result = await session.execute(query)
        foo = result.scalars().all()
        return foo

    async def resolve_sites(self, info: graphene.ResolveInfo):
        query = SiteSchemaType.get_query(info).options()
        session: AsyncSession = info.context["session"]
        result = await session.execute(query)
        foo = result.scalars().all()
        return foo

    async def resolve_aggregators(self, info: graphene.ResolveInfo):
        query = AggregatorSchemaType.get_query(info)
        session: AsyncSession = info.context["session"]
        result = await session.execute(query)
        return result.scalars().all()


schema = graphene.Schema(query=Query)
