"""required_site_group

Revision ID: 221e711a4555
Revises: ab6361a582b3
Create Date: 2026-07-29 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "221e711a4555"
down_revision = "ab6361a582b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("site_control_group", sa.Column("required_site_group_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_site_control_group_required_site_group_id"),
        "site_control_group",
        ["required_site_group_id"],
        unique=False,
    )
    op.create_foreign_key(
        "site_control_group_required_site_group_id_fkey",
        "site_control_group",
        "site_group",
        ["required_site_group_id"],
        ["site_group_id"],
    )
    op.add_column("archive_site_control_group", sa.Column("required_site_group_id", sa.Integer(), nullable=True))

    op.add_column("tariff", sa.Column("required_site_group_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_tariff_required_site_group_id"), "tariff", ["required_site_group_id"], unique=False)
    op.create_foreign_key(
        "tariff_required_site_group_id_fkey",
        "tariff",
        "site_group",
        ["required_site_group_id"],
        ["site_group_id"],
    )
    op.add_column("archive_tariff", sa.Column("required_site_group_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("archive_tariff", "required_site_group_id")
    op.drop_constraint("tariff_required_site_group_id_fkey", "tariff", type_="foreignkey")
    op.drop_index(op.f("ix_tariff_required_site_group_id"), table_name="tariff")
    op.drop_column("tariff", "required_site_group_id")

    op.drop_column("archive_site_control_group", "required_site_group_id")
    op.drop_constraint("site_control_group_required_site_group_id_fkey", "site_control_group", type_="foreignkey")
    op.drop_index(op.f("ix_site_control_group_required_site_group_id"), table_name="site_control_group")
    op.drop_column("site_control_group", "required_site_group_id")
