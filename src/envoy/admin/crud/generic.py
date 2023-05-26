from typing import Type

from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert as psql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.base import Base


async def upsert_single_return_status(
    session: AsyncSession, orm_class: Type[Base], obj: BaseModel, return_key: str
) -> bool:
    """TODO - how to identify if update or creation?"""
    """Relying on postgresql dialect for upsert capability. Unfortunately this breaks the typical ORM insert pattern."""
    table = orm_class.__table__
    index_cols = list(table.primary_key.columns)  # type: ignore [attr-defined]
    update_cols = [c.name for c in table.c if c not in index_cols]  # type: ignore [attr-defined]

    stmt = psql_insert(orm_class).values(**{k: getattr(obj, k) for k in update_cols})
    stmt = stmt.on_conflict_do_update(
        index_elements=index_cols,
        set_={k: getattr(stmt.excluded, k) for k in update_cols},
    ).returning(getattr(orm_class, return_key))

    resp = await session.execute(stmt)
    return resp.raw.rowcount != 1
