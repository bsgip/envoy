"""site_group_contract

Revision ID: ab6361a582b3
Revises: ed47bdab477f
Create Date: 2026-07-27 00:00:01.000000

Part 2 of 2 (contract) of migrating DynamicOperatingEnvelope and TariffGeneratedRate from a
per-Site FK to a per-SiteGroup FK. Requires the backfill migration (ed47bdab477f) to have already
run and populated site_group_id on every row of dynamic_operating_envelope,
archive_dynamic_operating_envelope, tariff_generated_rate and archive_tariff_generated_rate.

This migration:
  1. Makes site_group_id NOT NULL on all four tables (via a NOT VALID CHECK + VALIDATE CONSTRAINT
     first, so the full-table scan doesn't require an ACCESS EXCLUSIVE lock).
  2. Adds the site_group_id FK on the two live tables only (matching today - the archive tables
     have never had a FK on their site_id column, they're historical snapshot tables).
  3. Builds the renamed/new indexes with CREATE INDEX CONCURRENTLY (outside a transaction block) so
     multi-million-row index builds don't take an ACCESS EXCLUSIVE lock for their duration -
     including replacing TariffGeneratedRate's (tariff_id, site_id, start_time) unique constraint
     with an equivalent (tariff_id, site_group_id, start_time) constraint backed by a
     CONCURRENTLY-built unique index.
  4. Drops the old site_id columns, their indexes/constraints, and the old FKs.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ab6361a582b3"
down_revision = "ed47bdab477f"
branch_labels = None
depends_on = None

_DOE_TABLE = "dynamic_operating_envelope"
_ARCHIVE_DOE_TABLE = "archive_dynamic_operating_envelope"
_RATE_TABLE = "tariff_generated_rate"
_ARCHIVE_RATE_TABLE = "archive_tariff_generated_rate"

_OLD_DOE_INDEXES = [
    "ix_site_control_site_control_group_id_start_time_site_id",
    "ix_site_control_group_dynamic_operating_envelope_end_time_site",
    "ix_site_control_display_id_site_id",
]
_OLD_ARCHIVE_DOE_INDEXES = [
    "archive_doe_site_control_group_id_end_time_deleted_time_site_id",
    "archive_doe_display_id_site_id",
]

_OLD_DOE_FK = "dynamic_operating_envelope_site_id_fkey"
_NEW_DOE_FK = "dynamic_operating_envelope_site_group_id_fkey"

_OLD_RATE_UC = "tariff_id_site_id_start_time_uc"
_NEW_RATE_UC = "tariff_id_site_group_id_start_time_uc"
_NEW_RATE_UC_INDEX = "tariff_id_site_group_id_start_time_uc_idx"

_OLD_RATE_FK = "tariff_generated_rate_site_id_fkey"
_NEW_RATE_FK = "tariff_generated_rate_site_group_id_fkey"


def _set_not_null_without_full_scan(table_name: str, column_name: str) -> None:
    check_name = f"ck_{table_name}_{column_name}_not_null"
    op.execute(f"ALTER TABLE {table_name} ADD CONSTRAINT {check_name} CHECK ({column_name} IS NOT NULL) NOT VALID")
    op.execute(f"ALTER TABLE {table_name} VALIDATE CONSTRAINT {check_name}")
    op.execute(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} SET NOT NULL")
    op.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT {check_name}")


def upgrade() -> None:
    _set_not_null_without_full_scan(_DOE_TABLE, "site_group_id")
    _set_not_null_without_full_scan(_ARCHIVE_DOE_TABLE, "site_group_id")
    _set_not_null_without_full_scan(_RATE_TABLE, "site_group_id")
    _set_not_null_without_full_scan(_ARCHIVE_RATE_TABLE, "site_group_id")

    op.execute(
        f"ALTER TABLE {_DOE_TABLE} ADD CONSTRAINT {_NEW_DOE_FK} "
        "FOREIGN KEY (site_group_id) REFERENCES site_group (site_group_id) NOT VALID"
    )
    op.execute(f"ALTER TABLE {_DOE_TABLE} VALIDATE CONSTRAINT {_NEW_DOE_FK}")

    op.execute(
        f"ALTER TABLE {_RATE_TABLE} ADD CONSTRAINT {_NEW_RATE_FK} "
        "FOREIGN KEY (site_group_id) REFERENCES site_group (site_group_id) NOT VALID"
    )
    op.execute(f"ALTER TABLE {_RATE_TABLE} VALIDATE CONSTRAINT {_NEW_RATE_FK}")

    with op.get_context().autocommit_block():
        op.create_index(
            "ix_site_group_assignment_site_group_id_site_id",
            "site_group_assignment",
            ["site_group_id", "site_id"],
            unique=False,
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_site_control_site_control_group_id_start_time_site_group_id",
            _DOE_TABLE,
            ["site_control_group_id", "start_time", "site_group_id"],
            unique=False,
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_site_control_group_doe_end_time_site_group_id",
            _DOE_TABLE,
            ["site_control_group_id", "end_time", "site_group_id"],
            unique=False,
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_site_control_display_id_site_group_id",
            _DOE_TABLE,
            ["display_id", "site_group_id"],
            unique=False,
            postgresql_concurrently=True,
        )
        op.create_index(
            "archive_doe_scg_id_end_time_deleted_time_site_group_id",
            _ARCHIVE_DOE_TABLE,
            ["site_control_group_id", "end_time", "deleted_time", "site_group_id"],
            unique=False,
            postgresql_concurrently=True,
        )
        op.create_index(
            "archive_doe_display_id_site_group_id",
            _ARCHIVE_DOE_TABLE,
            ["display_id", "site_group_id"],
            unique=False,
            postgresql_concurrently=True,
        )
        op.create_index(
            _NEW_RATE_UC_INDEX,
            _RATE_TABLE,
            ["tariff_id", "site_group_id", "start_time"],
            unique=True,
            postgresql_concurrently=True,
        )

    op.execute(f"ALTER TABLE {_RATE_TABLE} ADD CONSTRAINT {_NEW_RATE_UC} UNIQUE USING INDEX {_NEW_RATE_UC_INDEX}")
    op.drop_constraint(_OLD_RATE_UC, _RATE_TABLE, type_="unique")

    for idx in _OLD_DOE_INDEXES:
        op.drop_index(idx, table_name=_DOE_TABLE)
    for idx in _OLD_ARCHIVE_DOE_INDEXES:
        op.drop_index(idx, table_name=_ARCHIVE_DOE_TABLE)

    op.drop_constraint(_OLD_DOE_FK, _DOE_TABLE, type_="foreignkey")
    op.drop_column(_DOE_TABLE, "site_id")
    op.drop_column(_ARCHIVE_DOE_TABLE, "site_id")

    op.drop_constraint(_OLD_RATE_FK, _RATE_TABLE, type_="foreignkey")
    op.drop_column(_RATE_TABLE, "site_id")
    op.drop_column(_ARCHIVE_RATE_TABLE, "site_id")


def downgrade() -> None:
    # Best-effort only: site_id is re-derived from site_group_assignment, which only round-trips
    # cleanly for groups with exactly one member (true for every group the backfill created, but
    # NOT for any real multi-site SiteGroup created/used after cutover - those rows will be left
    # with a NULL site_id, since there is no longer a single well-defined site to attribute them to).
    op.add_column(_DOE_TABLE, sa.Column("site_id", sa.Integer(), nullable=True))
    op.add_column(_ARCHIVE_DOE_TABLE, sa.Column("site_id", sa.Integer(), nullable=True))
    op.add_column(_RATE_TABLE, sa.Column("site_id", sa.Integer(), nullable=True))
    op.add_column(_ARCHIVE_RATE_TABLE, sa.Column("site_id", sa.Integer(), nullable=True))

    for table in (_DOE_TABLE, _ARCHIVE_DOE_TABLE, _RATE_TABLE, _ARCHIVE_RATE_TABLE):
        # table is one of four hardcoded module-level constants, not external input - table/column
        # identifiers can't be passed as bind params, so this can't be rewritten to avoid the f-string.
        op.execute(
            f"""
            UPDATE {table} t
            SET site_id = sga.site_id
            FROM site_group_assignment sga
            WHERE sga.site_group_id = t.site_group_id
              AND (SELECT count(*) FROM site_group_assignment WHERE site_group_id = t.site_group_id) = 1
            """  # noqa: S608
        )

    op.create_foreign_key(_OLD_DOE_FK, _DOE_TABLE, "site", ["site_id"], ["site_id"])
    op.create_foreign_key(_OLD_RATE_FK, _RATE_TABLE, "site", ["site_id"], ["site_id"])

    op.drop_constraint(_NEW_RATE_UC, _RATE_TABLE, type_="unique")
    op.create_unique_constraint(_OLD_RATE_UC, _RATE_TABLE, ["tariff_id", "site_id", "start_time"])

    op.create_index(_OLD_DOE_INDEXES[0], _DOE_TABLE, ["site_control_group_id", "start_time", "site_id"], unique=False)
    op.create_index(_OLD_DOE_INDEXES[1], _DOE_TABLE, ["site_control_group_id", "end_time", "site_id"], unique=False)
    op.create_index(_OLD_DOE_INDEXES[2], _DOE_TABLE, ["display_id", "site_id"], unique=False)

    op.create_index(
        _OLD_ARCHIVE_DOE_INDEXES[0],
        _ARCHIVE_DOE_TABLE,
        ["site_control_group_id", "end_time", "deleted_time", "site_id"],
        unique=False,
    )
    op.create_index(_OLD_ARCHIVE_DOE_INDEXES[1], _ARCHIVE_DOE_TABLE, ["display_id", "site_id"], unique=False)

    op.drop_index("archive_doe_display_id_site_group_id", table_name=_ARCHIVE_DOE_TABLE)
    op.drop_index("archive_doe_scg_id_end_time_deleted_time_site_group_id", table_name=_ARCHIVE_DOE_TABLE)
    op.drop_index("ix_site_control_display_id_site_group_id", table_name=_DOE_TABLE)
    op.drop_index("ix_site_control_group_doe_end_time_site_group_id", table_name=_DOE_TABLE)
    op.drop_index("ix_site_control_site_control_group_id_start_time_site_group_id", table_name=_DOE_TABLE)
    op.drop_index("ix_site_group_assignment_site_group_id_site_id", table_name="site_group_assignment")

    op.drop_constraint(_NEW_DOE_FK, _DOE_TABLE, type_="foreignkey")
    op.drop_constraint(_NEW_RATE_FK, _RATE_TABLE, type_="foreignkey")

    op.execute(f"ALTER TABLE {_ARCHIVE_RATE_TABLE} ALTER COLUMN site_group_id DROP NOT NULL")
    op.execute(f"ALTER TABLE {_RATE_TABLE} ALTER COLUMN site_group_id DROP NOT NULL")
    op.execute(f"ALTER TABLE {_ARCHIVE_DOE_TABLE} ALTER COLUMN site_group_id DROP NOT NULL")
    op.execute(f"ALTER TABLE {_DOE_TABLE} ALTER COLUMN site_group_id DROP NOT NULL")

    op.alter_column(_RATE_TABLE, "site_id", nullable=False)
    op.alter_column(_DOE_TABLE, "site_id", nullable=False)
