from datetime import datetime
from typing import Any, Callable, Iterable, Sequence, Union, cast

from sqlalchemy import Column, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.notification.crud.common import TArchiveResourceModel, TResourceModel
from envoy.server.model.archive.base import ArchiveBase
from envoy.server.model.base import Base


def extract_source_archive_pk_columns(
    source_type: type[Base], archive_type: type[ArchiveBase]
) -> tuple[Column, Column]:
    """Internal utility for extracting the "primary key" column name from source_type. Also fetches the "equivalent"
    column on the archive_type

    returns (source_pk_col, archive_pk_col)"""
    if not hasattr(source_type.__table__.primary_key, "columns"):
        raise ValueError(f"Table {source_type} primary key has no configured columns")

    archive_pk_cols = source_type.__table__.primary_key.columns
    if len(archive_pk_cols) != 1:
        raise Exception(f"source_type: {source_type} should only have a single primary key column defined,")
    source_pk_col: Column = archive_pk_cols[0]  # The archive type will have the same column - we can reuse this
    archive_pk_col: Column = cast(Column, archive_type.__table__.columns[source_pk_col.name])

    return (source_pk_col, archive_pk_col)


def extract_source_archive_changed_deleted_columns(
    source_type: type[Base], archive_type: type[ArchiveBase]
) -> tuple[Column, Column]:
    """Internal utility for extracting the "changed_time" or "deleted_time" columns from source_type/archive_type.

    returns (source_changed_col, archive_deleted_col)"""

    if not hasattr(source_type, "changed_time"):
        raise ValueError(f"Type {source_type} has no changed_time column to filter for modified entities")

    return (source_type.changed_time, cast(Column, archive_type.deleted_time))


async def fetch_entities_with_archive_by_id(
    session: AsyncSession,
    source_type: type[TResourceModel],
    archive_type: type[TArchiveResourceModel],
    primary_key_values: set[int],
) -> tuple[Sequence[TResourceModel], Sequence[TArchiveResourceModel]]:
    """Attempts to fetch all resources from the table backing source_type  with the specified primary keys. If any
    are NOT found in the source table, the table backing archive_type will instead be consulted.

    The return types will be a tuple of the form:
        (source_entities, archive_entities)"""

    source_pk_col, archive_pk_col = extract_source_archive_pk_columns(source_type, archive_type)

    # Lookup the source table
    source_entities = (
        (await session.execute(select(source_type).where(source_pk_col.in_(primary_key_values)))).scalars().all()
    )

    source_entity_ids = {getattr(e, source_pk_col.name) for e in source_entities}

    # If we find everything we want in the source table - we can exit early
    ids_not_in_source_table = primary_key_values.difference(source_entity_ids)
    if len(ids_not_in_source_table) == 0:
        return (source_entities, [])

    # If we are here - there are some primary_key_values that were NOT found - likely they have been deleted
    # We now need to goto the archive for the primary key (which does have an index) and find the LATEST deletion

    # NOTE - This leverages the postgresql DISTINCT ON functionality. Attempting to use this outside of
    # postgresql environment will result in errors
    archive_entities = (
        (
            await session.execute(
                select(archive_type)
                .distinct(archive_pk_col)
                .order_by(archive_pk_col, archive_type.deleted_time.desc(), archive_type.archive_time.desc())
                .where(archive_type.deleted_time != None)  # noqa: E711 # The is not None doesn't parse with SQLAlchemy
                .where(archive_pk_col.in_(ids_not_in_source_table))
            )
        )
        .scalars()
        .all()
    )

    return (source_entities, cast(Sequence[TArchiveResourceModel], archive_entities))  # type: ignore # mypy quirk


async def fetch_entities_with_archive_by_datetime(
    session: AsyncSession,
    source_type: type[TResourceModel],
    archive_type: type[TArchiveResourceModel],
    cd_time: datetime,
) -> tuple[Sequence[TResourceModel], Sequence[TArchiveResourceModel]]:
    """Attempts to fetch all resources from the table backing source_type and archive_type that have the specified
    changed/deleted time (cd_time)

    The return types will be a tuple of the form:
        (source_entities, archive_entities)"""

    if not hasattr(source_type, "changed_time"):
        raise ValueError(f"Type {source_type} has no changed_time column to filter for modified entities")

    source_changed_time, archive_deleted_time = extract_source_archive_changed_deleted_columns(
        source_type, archive_type
    )

    _, archive_pk_col = extract_source_archive_pk_columns(source_type, archive_type)

    # Lookup the source table (using changed_time)
    source_entities = (await session.execute(select(source_type).where(source_changed_time == cd_time))).scalars().all()

    # Lookup the archive tables (using deleted_time)
    # NOTE - This leverages the postgresql DISTINCT ON functionality. Attempting to use this outside of
    # postgresql environment will result in errors
    archive_entities = (
        (
            await session.execute(
                select(archive_type)
                .distinct(archive_pk_col)
                .order_by(archive_pk_col, archive_deleted_time.desc(), archive_type.archive_time.desc())
                .where(archive_deleted_time == cd_time)
            )
        )
        .scalars()
        .all()
    )

    return (source_entities, archive_entities)


def orm_relationship_map_parent_entities(
    source_entities: Iterable[Union[TResourceModel, TArchiveResourceModel]],
    get_parent_pk_id: Callable[[Union[TResourceModel, TArchiveResourceModel]], int],
    parent_entities_by_pk: dict[int, Any],
    source_relationship_prop_name: str,
) -> None:
    """Mutates source_entities to add "parent" relationships as if they had been fetched by SQLAlchemy ORM.

    Eg - Given a source array of TariffGeneratedRate or ArchivedTariffGeneratedRate, set the "site" relationship
    property to values from parent_entities_by_pk according to

    source_entities: The entities to be decorated with values from parent_entities_by_pk under a specific property
    get_parent_pk_id: A lambda that returns the FK reference to parent_entities_by_pk from a source entity
    parent_entities_by_pk: All of the parent entities indexed by their primary key
    source_relationship_prop_name: The name of the ORM relationship property on source_entity (eg: 'site')

    Returns nothing but source_entities will be updated. If a parent relationship lookup cannot be made, a ValueError
    will be raised"""

    for src in source_entities:
        parent_pk = get_parent_pk_id(src)
        parent = parent_entities_by_pk.get(parent_pk, None)
        if parent is None:
            raise ValueError(f"Entity {src} has parent with ID {parent_pk} that couldn't be matched")

        # We can't use setattr - some models struggle with our lazy=raise definition and pushing in a value
        # It feels like a SQL alchemy oddity with relationships that are "single_parent=True" but I'm not 100% sure
        # This method will be fine for the purposes we need for it - it might become problematic if this function
        # starts getting wider use
        src.__dict__[source_relationship_prop_name] = parent
        # setattr(src, source_relationship_prop_name, parent)
