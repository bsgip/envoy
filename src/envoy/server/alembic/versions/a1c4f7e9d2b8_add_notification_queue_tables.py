"""add_notification_queue_tables

Revision ID: a1c4f7e9d2b8
Revises: c230a2aa2615
Create Date: 2026-06-19 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1c4f7e9d2b8"
down_revision = "c230a2aa2615"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_check",
        sa.Column("notification_check_id", sa.Integer(), nullable=False),
        sa.Column("resource_type", sa.INTEGER(), nullable=False),
        sa.Column("changed_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("notification_check_id"),
    )
    op.create_table(
        "notification_transmit",
        sa.Column("notification_transmit_id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("subscription_href", sa.VARCHAR(length=2048), nullable=False),
        sa.Column("notification_id", sa.VARCHAR(length=36), nullable=False),
        sa.Column("remote_uri", sa.VARCHAR(length=2048), nullable=False),
        sa.Column("content", sa.TEXT(), nullable=False),
        sa.Column("attempt", sa.INTEGER(), nullable=False),
        sa.Column("execute_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("notification_transmit_id"),
    )
    op.create_index(
        "ix_notification_transmit_execute_after", "notification_transmit", ["execute_after"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_notification_transmit_execute_after", table_name="notification_transmit")
    op.drop_table("notification_transmit")
    op.drop_table("notification_check")
