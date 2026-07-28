"""rate_site_group_backfill

Revision ID: 1d33f879a065
Revises: 2593d6e055bb
Create Date: 2026-07-28 00:00:00.000000

Part 1 of 2 (expand) of migrating TariffGeneratedRate from a per-Site FK to a per-SiteGroup FK -
the same pattern already applied to DynamicOperatingEnvelope in ed47bdab477f/ab6361a582b3. This
migration is purely additive - it adds a nullable site_group_id column to both
tariff_generated_rate and archive_tariff_generated_rate and backfills it by creating a singleton
SiteGroup (+ SiteGroupAssignment) for every distinct legacy site_id referenced by those tables.
The old site_id column/index/FK/unique-constraint are left completely untouched here so existing
application code keeps working unmodified until the code deploy lands. The NOT NULL/FK/index
changes and the site_id column drop are deferred to the follow-up "contract" migration
(615836294764) so this step stays cheap and reversible.

The singleton SiteGroups created here reuse the exact same deterministic naming convention as the
DOE backfill (ed47bdab477f) - '__migrated_site_' || site_id - and every INSERT is guarded with
ON CONFLICT DO NOTHING, since a site referenced by both a DOE and a TariffGeneratedRate will
already have its singleton group/assignment created by the DOE migration (which may run before or
after this one - both are safe to run in either order or independently).

NOTE for operators: the backfill UPDATE statements below touch every row of
tariff_generated_rate/archive_tariff_generated_rate. On a deployment with millions of rows, run
this against a realistic data copy first to gauge wall-clock time / lock duration, and consider
running it during a maintenance window. A manual `VACUUM (ANALYZE)` on both tables is recommended
after this migration completes.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1d33f879a065"
down_revision = "2593d6e055bb"
branch_labels = None
depends_on = None

# Deterministic prefix used to name the singleton SiteGroups created for legacy site_id values -
# must match the constant of the same name in ed47bdab477f_doe_site_group_backfill.py so that a
# site referenced by both DOEs and rates ends up in a single shared singleton group.
MIGRATED_SITE_GROUP_NAME_PREFIX = "__migrated_site_"


def upgrade() -> None:
    op.add_column("tariff_generated_rate", sa.Column("site_group_id", sa.Integer(), nullable=True))
    op.add_column("archive_tariff_generated_rate", sa.Column("site_group_id", sa.Integer(), nullable=True))

    # 1. Create one singleton SiteGroup per distinct legacy site_id referenced by either table - skipping
    #    any site_id that already has a migrated singleton group (eg created by the DOE backfill)
    op.execute(
        sa.text(
            """
            INSERT INTO site_group (name, created_time, changed_time)
            SELECT DISTINCT :prefix || legacy.site_id::text, now(), now()
            FROM (
                SELECT site_id FROM tariff_generated_rate
                UNION
                SELECT site_id FROM archive_tariff_generated_rate
            ) legacy
            ON CONFLICT ON CONSTRAINT name_uc DO NOTHING
            """
        ).bindparams(prefix=MIGRATED_SITE_GROUP_NAME_PREFIX)
    )

    # 2. Assign the (singleton) member site to its new group, so admin group listings / member
    #    counts are correct from the moment this migration completes. Skips any (site_id, site_group_id)
    #    pair that already exists (eg created by the DOE backfill).
    op.execute(
        sa.text(
            """
            INSERT INTO site_group_assignment (site_id, site_group_id, created_time, changed_time)
            SELECT legacy.site_id, sg.site_group_id, now(), now()
            FROM (
                SELECT DISTINCT site_id FROM tariff_generated_rate
                UNION
                SELECT DISTINCT site_id FROM archive_tariff_generated_rate
            ) legacy
            JOIN site_group sg ON sg.name = :prefix || legacy.site_id::text
            ON CONFLICT ON CONSTRAINT site_id_site_group_id_uc DO NOTHING
            """
        ).bindparams(prefix=MIGRATED_SITE_GROUP_NAME_PREFIX)
    )

    # 3. Backfill site_group_id on both rate tables by joining straight to site_group on the
    #    deterministic name (site_group.name is UNIQUE so this join is unambiguous)
    op.execute(
        sa.text(
            """
            UPDATE tariff_generated_rate r
            SET site_group_id = sg.site_group_id
            FROM site_group sg
            WHERE sg.name = :prefix || r.site_id::text
            """
        ).bindparams(prefix=MIGRATED_SITE_GROUP_NAME_PREFIX)
    )
    op.execute(
        sa.text(
            """
            UPDATE archive_tariff_generated_rate ar
            SET site_group_id = sg.site_group_id
            FROM site_group sg
            WHERE sg.name = :prefix || ar.site_id::text
            """
        ).bindparams(prefix=MIGRATED_SITE_GROUP_NAME_PREFIX)
    )


def downgrade() -> None:
    op.drop_column("archive_tariff_generated_rate", "site_group_id")
    op.drop_column("tariff_generated_rate", "site_group_id")

    # NOTE: we deliberately do NOT delete the "__migrated_site_*" SiteGroup/SiteGroupAssignment rows here -
    # they may still be in use by DynamicOperatingEnvelope rows (created independently by the DOE backfill,
    # or reused by this migration via the ON CONFLICT DO NOTHING guards above). Cleaning those up is the
    # responsibility of whichever migration created them last in the downgrade order.
