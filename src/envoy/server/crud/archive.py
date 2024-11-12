from datetime import datetime
from itertools import chain
from typing import Any, Callable

from sqlalchemy import Delete, Select, delete, insert, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.model.archive.base import ARCHIVE_BASE_COLUMNS, ArchiveBase
from envoy.server.model.base import Base


async def copy_rows_into_archive(
    session: AsyncSession,
    source_table: type[Base],
    archive_table: type[ArchiveBase],
    where_clause_decorator: Callable[[Select[Any]], Select[Any]],
) -> None:
    """Archives a set of rows from source_table by copying them to archive_table. The rows will be copied in a way
    that marks them as being an update to the original table. That is, the deleted_time column will be left NULL


    source_table will NOT be altered
    archive_table will receive new rows that are matched by where_clause_decorator

    where_clause_decorator should be used to scope the archive operation to specific rows. Do this by:
        where_clause_decorator=lambda q: q.where(MyTable.column_name == 123)

    NOTE - this will not populate/affect any models in the session, all operations occur on the DB directly
    """

    # We only want to save the columns NOT found in the archive table (i.e. they only exist in the source table)
    archive_cols = [
        column.name for column in archive_table.__table__.columns if column.name not in ARCHIVE_BASE_COLUMNS
    ]
    archive_stmt = insert(archive_table).from_select(
        archive_cols, where_clause_decorator(select(*[getattr(source_table, column) for column in archive_cols]))
    )
    await session.execute(archive_stmt)


async def delete_rows_into_archive(
    session: AsyncSession,
    source_table: type[Base],
    archive_table: type[ArchiveBase],
    deleted_time: datetime,
    where_clause_decorator: Callable[[Delete], Delete],
) -> None:
    """Deletes a set of rows from source_table (while also copying them to archive_table). The rows in the source_table
    will be deleted and copies of the deleted contents will be added to the archive (with the specified deleted_time).

    source_table will have rows deleted (according to where_clause_decorator)
    archive_table will receive the deleted rows that are matched by where_clause_decorator

    where_clause_decorator should be used to scope the delete operation to specific rows. Do this by:
        where_clause_decorator=lambda q: q.where(MyTable.column_name == 123)

    NOTE - this will not populate/affect any models in the session, all operations occur on the DB directly
    """

    # We will be writing a query like:
    # INSERT INTO archive_table(col1, col2..)
    #     (DELETE FROM original_table
    #      WHERE ...
    #      RETURNING (col1, col2...)
    #     )

    # The deleted_time is going to be a constant that we specify
    delete_cte = (
        where_clause_decorator(delete(source_table))
        .returning(*source_table.__table__.columns, literal(deleted_time).label(ArchiveBase.deleted_time.name))
        .cte("deleted_rows")
    )
    returned_cols = [c.name for c in chain(source_table.__table__.columns, archive_table.deleted_time.property.columns)]

    # Define the insert statement, selecting from the CTE
    insert_from_delete_stmt = insert(archive_table).from_select(returned_cols, delete_cte)

    await session.execute(insert_from_delete_stmt)
