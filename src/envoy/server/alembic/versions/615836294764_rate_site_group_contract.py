"""rate_site_group_contract

Revision ID: 615836294764
Revises: 1d33f879a065
Create Date: 2026-07-28 00:00:01.000000

Part 2 of 2 (contract) of migrating TariffGeneratedRate from a per-Site FK to a per-SiteGroup FK.
Requires the backfill migration (1d33f879a065) to have already run and populated site_group_id on
every row of tariff_generated_rate/archive_tariff_generated_rate.

This migration:
  1. Makes site_group_id NOT NULL on both tables (via a NOT VALID CHECK + VALIDATE CONSTRAINT
     first, so the full-table scan doesn't require an ACCESS EXCLUSIVE lock).
  2. Adds the site_group_id FK on the live table only (matching today - the archive table has
     never had a FK on its site_id column, it's a historical snapshot table).
  3. Replaces the (tariff_id, site_id, start_time) unique constraint with an equivalent
     (tariff_id, site_group_id, start_time) constraint, backed by a CONCURRENTLY-built unique
     index so the build doesn't take an ACCESS EXCLUSIVE lock.
  4. Drops the old site_id column on both tables.

NOTE: unlike the DOE contract migration (ab6361a582b3), no new SiteGroupAssignment index is
created here - ix_site_group_assignment_site_group_id_site_id already exists (added by that
migration) and covers this table's membership lookups too.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "615836294764"
down_revision = "1d33f879a065"
branch_labels = None
depends_on = None

_RATE_TABLE = "tariff_generated_rate"
_ARCHIVE_RATE_TABLE = "archive_tariff_generated_rate"

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
    _set_not_null_without_full_scan(_RATE_TABLE, "site_group_id")
    _set_not_null_without_full_scan(_ARCHIVE_RATE_TABLE, "site_group_id")

    op.execute(
        f"ALTER TABLE {_RATE_TABLE} ADD CONSTRAINT {_NEW_RATE_FK} "
        "FOREIGN KEY (site_group_id) REFERENCES site_group (site_group_id) NOT VALID"
    )
    op.execute(f"ALTER TABLE {_RATE_TABLE} VALIDATE CONSTRAINT {_NEW_RATE_FK}")

    with op.get_context().autocommit_block():
        op.create_index(
            _NEW_RATE_UC_INDEX,
            _RATE_TABLE,
            ["tariff_id", "site_group_id", "start_time"],
            unique=True,
            postgresql_concurrently=True,
        )

    op.execute(f"ALTER TABLE {_RATE_TABLE} ADD CONSTRAINT {_NEW_RATE_UC} UNIQUE USING INDEX {_NEW_RATE_UC_INDEX}")
    op.drop_constraint(_OLD_RATE_UC, _RATE_TABLE, type_="unique")

    op.drop_constraint(_OLD_RATE_FK, _RATE_TABLE, type_="foreignkey")
    op.drop_column(_RATE_TABLE, "site_id")
    op.drop_column(_ARCHIVE_RATE_TABLE, "site_id")


def downgrade() -> None:
    # Best-effort only: site_id is re-derived from site_group_assignment, which only round-trips
    # cleanly for groups with exactly one member (true for every group the backfill created, but
    # NOT for any real multi-site SiteGroup created/used after cutover - those rows will be left
    # with a NULL site_id, since there is no longer a single well-defined site to attribute them to).
    op.add_column(_RATE_TABLE, sa.Column("site_id", sa.Integer(), nullable=True))
    op.add_column(_ARCHIVE_RATE_TABLE, sa.Column("site_id", sa.Integer(), nullable=True))

    for table in (_RATE_TABLE, _ARCHIVE_RATE_TABLE):
        # table is one of two hardcoded module-level constants, not external input - table/column
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

    op.create_foreign_key(_OLD_RATE_FK, _RATE_TABLE, "site", ["site_id"], ["site_id"])

    op.drop_constraint(_NEW_RATE_UC, _RATE_TABLE, type_="unique")
    op.create_unique_constraint(_OLD_RATE_UC, _RATE_TABLE, ["tariff_id", "site_id", "start_time"])

    op.drop_constraint(_NEW_RATE_FK, _RATE_TABLE, type_="foreignkey")

    op.execute(f"ALTER TABLE {_ARCHIVE_RATE_TABLE} ALTER COLUMN site_group_id DROP NOT NULL")
    op.execute(f"ALTER TABLE {_RATE_TABLE} ALTER COLUMN site_group_id DROP NOT NULL")

    op.alter_column(_RATE_TABLE, "site_id", nullable=False)
