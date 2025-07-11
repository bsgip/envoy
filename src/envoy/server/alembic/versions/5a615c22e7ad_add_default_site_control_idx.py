"""add_default_site_control_idx

Revision ID: 5a615c22e7ad
Revises: 039bcb7dab76
Create Date: 2025-06-19 16:18:13.875896

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "5a615c22e7ad"
down_revision = "039bcb7dab76"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(
        op.f("ix_default_site_control_changed_time"), "default_site_control", ["changed_time"], unique=False
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_default_site_control_changed_time"), table_name="default_site_control")
    # ### end Alembic commands ###
