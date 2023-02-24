from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.model import Certificate


async def select_certificate_id_using_lfdi(lfdi: str, session: AsyncSession):
    stmt = select(Certificate).where(Certificate.lfdi == lfdi)

    resp = await session.execute(stmt)

    return resp.scalar_one_or_none()
