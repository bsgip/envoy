"""add_created_time

Revision ID: 22491fcef4fd
Revises: f18fbf983ca9
Create Date: 2024-10-24 16:25:18.047027

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "22491fcef4fd"
down_revision = "f18fbf983ca9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "aggregator",
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "aggregator",
        sa.Column("changed_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "aggregator_domain",
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "dynamic_operating_envelope",
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "site", sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
    )
    op.add_column(
        "site_der",
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "site_der_availability",
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "site_der_rating",
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "site_der_setting",
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "site_der_status",
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "site_group",
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "site_group_assignment",
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "site_reading",
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "site_reading_type",
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "subscription",
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "tariff", sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
    )
    op.add_column(
        "tariff_generated_rate",
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    # ### end Alembic commands ###

    op.alter_column("aggregator", "changed_time", server_default=None)

    # Seed the created_time by Copying from changed_time
    op.execute("UPDATE aggregator_domain SET created_time = changed_time")
    op.execute("UPDATE dynamic_operating_envelope SET created_time = changed_time")
    op.execute("UPDATE site SET created_time = changed_time")
    op.execute("UPDATE site_der SET created_time = changed_time")
    op.execute("UPDATE site_der_availability SET created_time = changed_time")
    op.execute("UPDATE site_der_rating SET created_time = changed_time")
    op.execute("UPDATE site_der_setting SET created_time = changed_time")
    op.execute("UPDATE site_der_status SET created_time = changed_time")
    op.execute("UPDATE site_group SET created_time = changed_time")
    op.execute("UPDATE site_group_assignment SET created_time = changed_time")
    op.execute("UPDATE site_reading SET created_time = changed_time")
    op.execute("UPDATE site_reading_type SET created_time = changed_time")
    op.execute("UPDATE subscription SET created_time = changed_time")
    op.execute("UPDATE tariff SET created_time = changed_time")
    op.execute("UPDATE tariff_generated_rate SET created_time = changed_time")


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("tariff_generated_rate", "created_time")
    op.drop_column("tariff", "created_time")
    op.drop_column("subscription", "created_time")
    op.drop_column("site_reading_type", "created_time")
    op.drop_column("site_reading", "created_time")
    op.drop_column("site_group_assignment", "created_time")
    op.drop_column("site_group", "created_time")
    op.drop_column("site_der_status", "created_time")
    op.drop_column("site_der_setting", "created_time")
    op.drop_column("site_der_rating", "created_time")
    op.drop_column("site_der_availability", "created_time")
    op.drop_column("site_der", "created_time")
    op.drop_column("site", "created_time")
    op.drop_column("dynamic_operating_envelope", "created_time")
    op.drop_column("aggregator_domain", "created_time")
    op.drop_column("aggregator", "changed_time")
    op.drop_column("aggregator", "created_time")
    # ### end Alembic commands ###
