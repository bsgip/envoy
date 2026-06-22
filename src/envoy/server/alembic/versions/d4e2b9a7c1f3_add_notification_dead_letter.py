"""add_notification_dead_letter

Revision ID: d4e2b9a7c1f3
Revises: a1c4f7e9d2b8
Create Date: 2026-06-22 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d4e2b9a7c1f3"
down_revision = "a1c4f7e9d2b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_dead_letter",
        sa.Column("notification_dead_letter_id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("subscription_href", sa.VARCHAR(length=2048), nullable=False),
        sa.Column("notification_id", sa.VARCHAR(length=36), nullable=False),
        sa.Column("remote_uri", sa.VARCHAR(length=2048), nullable=False),
        sa.Column("content", sa.TEXT(), nullable=False),
        sa.Column("attempt", sa.INTEGER(), nullable=False),
        sa.Column("http_status_code", sa.INTEGER(), nullable=True),
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("notification_dead_letter_id"),
    )


def downgrade() -> None:
    op.drop_table("notification_dead_letter")
