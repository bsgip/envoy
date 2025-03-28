"""added_subscriptions

Revision ID: a0b35d4fff6c
Revises: 3cd2245c7c00
Create Date: 2024-02-21 16:47:33.879964

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a0b35d4fff6c"
down_revision = "3cd2245c7c00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "aggregator_domain",
        sa.Column("aggregator_domain_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("aggregator_id", sa.Integer(), nullable=False),
        sa.Column("changed_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("domain", sa.VARCHAR(length=512), nullable=False),
        sa.ForeignKeyConstraint(["aggregator_id"], ["aggregator.aggregator_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("aggregator_domain_id"),
    )
    op.create_table(
        "subscription",
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("aggregator_id", sa.Integer(), nullable=False),
        sa.Column("changed_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resource_type", sa.INTEGER(), nullable=False),
        sa.Column("resource_id", sa.INTEGER(), nullable=True),
        sa.Column("scoped_site_id", sa.Integer(), nullable=True),
        sa.Column("notification_uri", sa.VARCHAR(length=2048), nullable=False),
        sa.Column("entity_limit", sa.INTEGER(), nullable=False),
        sa.ForeignKeyConstraint(
            ["aggregator_id"],
            ["aggregator.aggregator_id"],
        ),
        sa.ForeignKeyConstraint(
            ["scoped_site_id"],
            ["site.site_id"],
        ),
        sa.PrimaryKeyConstraint("subscription_id"),
    )
    op.create_index("aggregator_id", "subscription", ["resource_type"], unique=False)
    op.create_table(
        "subscription_condition",
        sa.Column("subscription_condition_id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("attribute", sa.INTEGER(), nullable=False),
        sa.Column("lower_threshold", sa.INTEGER(), nullable=True),
        sa.Column("upper_threshold", sa.INTEGER(), nullable=True),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscription.subscription_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("subscription_condition_id"),
    )
    op.create_index(
        op.f("ix_dynamic_operating_envelope_changed_time"), "dynamic_operating_envelope", ["changed_time"], unique=False
    )
    op.create_index(op.f("ix_site_changed_time"), "site", ["changed_time"], unique=False)
    op.create_index(op.f("ix_site_reading_changed_time"), "site_reading", ["changed_time"], unique=False)
    op.create_index(
        op.f("ix_tariff_generated_rate_changed_time"), "tariff_generated_rate", ["changed_time"], unique=False
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_tariff_generated_rate_changed_time"), table_name="tariff_generated_rate")
    op.drop_index(op.f("ix_site_reading_changed_time"), table_name="site_reading")
    op.drop_index(op.f("ix_site_changed_time"), table_name="site")
    op.drop_index(op.f("ix_dynamic_operating_envelope_changed_time"), table_name="dynamic_operating_envelope")
    op.drop_table("subscription_condition")
    op.drop_index("aggregator_id", table_name="subscription")
    op.drop_table("subscription")
    op.drop_table("aggregator_domain")
    # ### end Alembic commands ###
