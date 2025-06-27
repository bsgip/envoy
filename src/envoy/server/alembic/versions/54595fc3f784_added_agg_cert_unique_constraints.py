"""added agg cert unique constraints

Revision ID: 54595fc3f784
Revises: 8feebfbbfe69
Create Date: 2025-06-18 08:47:59.042643

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "54595fc3f784"
down_revision = "8feebfbbfe69"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        op.f("uq_certificate_lfdi"), "certificate", ["lfdi"], postgresql_nulls_not_distinct=False
    )
    op.create_unique_constraint(
        op.f("uq_aggregator_certificate_assignment_cert_id_agg_id"),
        "aggregator_certificate_assignment",
        ["certificate_id", "aggregator_id"],
    )
    op.alter_column("certificate", "created", server_default=sa.text("now()"))


def downgrade() -> None:
    op.drop_constraint(op.f("uq_certificate_lfdi"), "certificate", type_="unique")
    op.drop_constraint(
        op.f("uq_aggregator_certificate_assignment_cert_id_agg_id"),
        "aggregator_certificate_assignment",
        type_="unique",
    )
    op.alter_column("certificate", "created", server_default=None)
