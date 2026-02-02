"""add_ci_lfdis

Revision ID: 4cc01a143a95
Revises: f0f12c93d5aa
Create Date: 2025-09-01 12:59:35.599084

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4cc01a143a95"
down_revision = "f0f12c93d5aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
    CREATE COLLATION "case_insensitive" (
        provider = icu,
        locale = 'und-u-ks-level2',
        deterministic = false
    );
    """))

    op.alter_column("site", "lfdi", type_=sa.VARCHAR(length=42, collation="case_insensitive"))
    op.alter_column("site_reading_type", "mrid", type_=sa.VARCHAR(length=32, collation="case_insensitive"))
    op.alter_column("site_reading_type", "group_mrid", type_=sa.VARCHAR(length=32, collation="case_insensitive"))


def downgrade() -> None:
    op.alter_column("site", "lfdi", type_=sa.VARCHAR(length=42, collation="default"))
    op.alter_column("site_reading_type", "mrid", type_=sa.VARCHAR(length=32, collation="default"))
    op.alter_column("site_reading_type", "group_mrid", type_=sa.VARCHAR(length=32, collation="default"))

    op.execute(sa.text('DROP COLLATION IF EXISTS "case_insensitive";'))
