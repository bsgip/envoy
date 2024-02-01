from sqlalchemy.dialects.postgresql import insert as psql_insert
from sqlalchemy.ext.asyncio import AsyncSession


from envoy.server.model.doe import DynamicOperatingEnvelope


async def upsert_many_doe(session: AsyncSession, doe_list: list[DynamicOperatingEnvelope]) -> None:
    """Adds a multiple DynamicOperatingEnvelope into the db. Returns None."""
    table = DynamicOperatingEnvelope.__table__
    update_cols = [c.name for c in table.c if c not in list(table.primary_key.columns)]  # type: ignore [attr-defined]
    stmt = psql_insert(DynamicOperatingEnvelope).values([{k: getattr(doe, k) for k in update_cols} for doe in doe_list])
    stmt = stmt.on_conflict_do_update(
        index_elements=[DynamicOperatingEnvelope.site_id, DynamicOperatingEnvelope.start_time],
        set_={k: getattr(stmt.excluded, k) for k in update_cols},
    )
    await session.execute(stmt)
