from typing import Sequence, Union, cast

from sqlalchemy import Column, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.notification.crud.common import TArchiveResourceModel, TResourceModel
from envoy.server.model.archive.base import ArchiveBase
from envoy.server.model.base import Base


async def fetch_relationship_with_archive(
    session: AsyncSession, source_type: type[Base], archive_type: type[ArchiveBase], primary_key_values: set[int]
) -> tuple[Sequence[TResourceModel], Sequence[TArchiveResourceModel]]:
    """Attempts to fetch all resources from the table backing source_type  with the specified primary keys. If any
    are NOT found in the source table, the table backing archive_type will instead be consulted.

    The return types will be a tuple of the form:
        (source_entities, archive_entities)"""

    if not hasattr(source_type.__table__.primary_key, "columns"):
        raise ValueError(f"Table {source_type} primary key has no configured columns")

    archive_pk_cols = source_type.__table__.primary_key.columns
    if len(archive_pk_cols) != 1:
        raise Exception(f"source_type: {source_type} should only have a single primary key column defined,")
    source_pk_col: Column = archive_pk_cols[0]  # The archive type will have the same column - we can reuse this

    # Lookup the source table
    source_entities: Sequence[TResourceModel] = cast(
        Sequence[TResourceModel],
        (await session.execute(select(source_type).where(source_pk_col.in_(primary_key_values)))).scalars().all(),
    )
    source_entity_ids = {getattr(e, source_pk_col.name) for e in source_entities}

    # If we find everything we want in the source table - we can exit early
    ids_not_in_source_table = primary_key_values.difference(source_entity_ids)
    if len(ids_not_in_source_table) == 0:
        return (source_entities, [])

    # If we are here - there are some primary_key_values that were NOT found - likely they have been deleted
    # We now need to goto the archive for the primary key (which does have an index) and find the LATEST deletion
    archive_pk_col: Column = [
        c for c in cast(list[Column], archive_type.__table__.columns) if c.name == source_pk_col.name
    ][0]
    archive_entities: Sequence[TArchiveResourceModel] = cast(
        Sequence[TArchiveResourceModel],
        (
            # NOTE - This leverages the postgresql DISTINCT ON functionality. Attempting to use this outside of
            # postgresql environment will result in errors
            await session.execute(
                select(archive_type)
                .distinct(archive_pk_col)
                .order_by(archive_pk_col, archive_type.deleted_time.desc(), archive_type.archive_time.desc())
                .where(archive_type.deleted_time != None)
                .where(archive_pk_col.in_(ids_not_in_source_table))
            )
        )
        .scalars()
        .all(),
    )

    return (source_entities, archive_entities)
