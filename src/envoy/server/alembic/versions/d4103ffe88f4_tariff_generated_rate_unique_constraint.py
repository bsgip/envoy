"""tariff_generated_rate_unique_constraint

Revision ID: d4103ffe88f4
Revises: 70c1e8a374b1
Create Date: 2026-08-07 14:42:13.882593

Adds a UniqueConstraint to tariff_generated_rate on (tariff_component_id, start_time, site_group_id) - this
supports the new "on_collide" behaviour on the admin bulk create endpoint that needs a well defined notion of
what constitutes a colliding/duplicate TariffGeneratedRate.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "d4103ffe88f4"
down_revision = "70c1e8a374b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uc_tariff_generated_rate_component_id_start_time_site_group_id",
        "tariff_generated_rate",
        ["tariff_component_id", "start_time", "site_group_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uc_tariff_generated_rate_component_id_start_time_site_group_id", "tariff_generated_rate", type_="unique"
    )
