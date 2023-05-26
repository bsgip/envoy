from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from envoy.server.model.tariff import Tariff


async def insert_single_tariff(session: AsyncSession, tariff: Tariff) -> None:
    session.add(tariff)


async def update_single_tariff(session: AsyncSession, updated_tariff: Tariff) -> None:
    resp = await session.execute(select(Tariff).filter_by(tariff_id=updated_tariff.tariff_id))
    tariff = resp.scalar_one()

    tariff.changed_time = updated_tariff.changed_time
    tariff.dnsp_code = updated_tariff.dnsp_code
    tariff.name = updated_tariff.name
    tariff.currency_code = updated_tariff.currency_code
