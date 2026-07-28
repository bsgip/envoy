"""site_group_backfill

Revision ID: ed47bdab477f
Revises: 2593d6e055bb
Create Date: 2026-07-27 00:00:00.000000

Part 1 of 2 (expand) of migrating DynamicOperatingEnvelope and TariffGeneratedRate from a per-Site
FK to a per-SiteGroup FK. This migration is purely additive - it adds a nullable site_group_id
column to dynamic_operating_envelope, archive_dynamic_operating_envelope, tariff_generated_rate and
archive_tariff_generated_rate, and backfills it by creating a singleton SiteGroup (+
SiteGroupAssignment) for every distinct legacy site_id referenced by any of those four tables. The
old site_id columns/indexes/FKs/unique-constraint are left completely untouched here so existing
application code keeps working unmodified until the code deploy lands. The NOT NULL/FK/index
changes and the site_id column drops are deferred to the follow-up "contract" migration
(ab6361a582b3) so this step stays cheap and reversible.

NOTE for operators: the backfill UPDATE statements below touch every row of all four tables. On a
deployment with millions of rows, run this against a realistic data copy first to gauge wall-clock
time / lock duration, and consider running it during a maintenance window. A manual
`VACUUM (ANALYZE)` on all four tables is recommended after this migration completes.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ed47bdab477f"
down_revision = "2593d6e055bb"
branch_labels = None
depends_on = None

# Deterministic prefix used to name the singleton SiteGroups created for legacy site_id values so
# that this migration is idempotent/re-joinable without needing to correlate INSERT ... RETURNING
# order back to source rows. site_group.name has a UNIQUE constraint - if an admin has already
# created a real group whose name collides with this convention, the INSERT below will fail loudly
# rather than silently reusing/corrupting that group.
MIGRATED_SITE_GROUP_NAME_PREFIX = "__migrated_site_"

_DOE_TABLE = "dynamic_operating_envelope"
_ARCHIVE_DOE_TABLE = "archive_dynamic_operating_envelope"
_RATE_TABLE = "tariff_generated_rate"
_ARCHIVE_RATE_TABLE = "archive_tariff_generated_rate"


def upgrade() -> None:
    op.add_column(_DOE_TABLE, sa.Column("site_group_id", sa.Integer(), nullable=True))
    op.add_column(_ARCHIVE_DOE_TABLE, sa.Column("site_group_id", sa.Integer(), nullable=True))
    op.add_column(_RATE_TABLE, sa.Column("site_group_id", sa.Integer(), nullable=True))
    op.add_column(_ARCHIVE_RATE_TABLE, sa.Column("site_group_id", sa.Integer(), nullable=True))

    # 1. Create one singleton SiteGroup per distinct legacy site_id referenced by any of the four tables
    op.execute(
        sa.text(
            """
            INSERT INTO site_group (name, created_time, changed_time)
            SELECT DISTINCT :prefix || legacy.site_id::text, now(), now()
            FROM (
                SELECT site_id FROM dynamic_operating_envelope
                UNION
                SELECT site_id FROM archive_dynamic_operating_envelope
                UNION
                SELECT site_id FROM tariff_generated_rate
                UNION
                SELECT site_id FROM archive_tariff_generated_rate
            ) legacy
            """
        ).bindparams(prefix=MIGRATED_SITE_GROUP_NAME_PREFIX)
    )

    # 2. Assign the (singleton) member site to its new group, so admin group listings / member
    #    counts are correct from the moment this migration completes
    op.execute(
        sa.text(
            """
            INSERT INTO site_group_assignment (site_id, site_group_id, created_time, changed_time)
            SELECT legacy.site_id, sg.site_group_id, now(), now()
            FROM (
                SELECT DISTINCT site_id FROM dynamic_operating_envelope
                UNION
                SELECT DISTINCT site_id FROM archive_dynamic_operating_envelope
                UNION
                SELECT DISTINCT site_id FROM tariff_generated_rate
                UNION
                SELECT DISTINCT site_id FROM archive_tariff_generated_rate
            ) legacy
            JOIN site_group sg ON sg.name = :prefix || legacy.site_id::text
            """
        ).bindparams(prefix=MIGRATED_SITE_GROUP_NAME_PREFIX)
    )

    # 3. Backfill site_group_id on all four tables by joining straight to site_group on the
    #    deterministic name (site_group.name is UNIQUE so this join is unambiguous)
    for table in (_DOE_TABLE, _ARCHIVE_DOE_TABLE, _RATE_TABLE, _ARCHIVE_RATE_TABLE):
        # table is one of four hardcoded module-level constants, not external input - table
        # identifiers can't be passed as bind params, so this can't be rewritten to avoid the f-string.
        op.execute(
            sa.text(
                f"""
                UPDATE {table} t
                SET site_group_id = sg.site_group_id
                FROM site_group sg
                WHERE sg.name = :prefix || t.site_id::text
                """  # noqa: S608 # nosec: B608
            ).bindparams(prefix=MIGRATED_SITE_GROUP_NAME_PREFIX)
        )


def downgrade() -> None:
    op.drop_column(_ARCHIVE_RATE_TABLE, "site_group_id")
    op.drop_column(_RATE_TABLE, "site_group_id")
    op.drop_column(_ARCHIVE_DOE_TABLE, "site_group_id")
    op.drop_column(_DOE_TABLE, "site_group_id")

    op.execute(
        sa.text(
            """
            DELETE FROM site_group_assignment
            WHERE site_group_id IN (
                SELECT site_group_id FROM site_group WHERE name LIKE :prefix
            )
            """
        ).bindparams(prefix=MIGRATED_SITE_GROUP_NAME_PREFIX + "%")
    )
    op.execute(
        sa.text("DELETE FROM site_group WHERE name LIKE :prefix").bindparams(
            prefix=MIGRATED_SITE_GROUP_NAME_PREFIX + "%"
        )
    )
