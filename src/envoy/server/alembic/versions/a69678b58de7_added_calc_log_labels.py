"""added_calc_log_labels

Revision ID: a69678b58de7
Revises: e42aa138c308
Create Date: 2024-12-23 15:45:47.288183

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a69678b58de7"
down_revision = "e42aa138c308"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "calculation_log_label_metadata",
        sa.Column("calculation_log_id", sa.Integer(), nullable=False),
        sa.Column("label_id", sa.INTEGER(), nullable=False),
        sa.Column("name", sa.VARCHAR(length=64), nullable=False),
        sa.Column("description", sa.VARCHAR(length=512), nullable=False),
        sa.ForeignKeyConstraint(["calculation_log_id"], ["calculation_log.calculation_log_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("calculation_log_id", "label_id"),
    )
    op.create_table(
        "calculation_log_label_value",
        sa.Column("calculation_log_id", sa.Integer(), nullable=False),
        sa.Column("label_id", sa.INTEGER(), nullable=False),
        sa.Column("site_id_snapshot", sa.INTEGER(), nullable=False),
        sa.Column("label", sa.VARCHAR(length=64), nullable=False),
        sa.ForeignKeyConstraint(["calculation_log_id"], ["calculation_log.calculation_log_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("calculation_log_id", "label_id", "site_id_snapshot"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("calculation_log_label_value")
    op.drop_table("calculation_log_label_metadata")
    # ### end Alembic commands ###
