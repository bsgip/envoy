"""drop_site_der

Flattens the DER sub resources (rating/setting/availability/status) so they reference the owning site directly
instead of a (data-less) parent site_der row, then drops the site_der and archive_site_der tables.

Revision ID: b2f4a6c8d1e3
Revises: c230a2aa2615
Create Date: 2026-06-10 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b2f4a6c8d1e3"
down_revision = "c230a2aa2615"
branch_labels = None
depends_on = None


# (live table, primary key column)
CHILD_TABLES = [
    ("site_der_rating", "site_der_rating_id"),
    ("site_der_setting", "site_der_setting_id"),
    ("site_der_availability", "site_der_availability_id"),
    ("site_der_status", "site_der_status_id"),
]

ARCHIVE_CHILD_TABLES = [
    "archive_site_der_rating",
    "archive_site_der_setting",
    "archive_site_der_availability",
    "archive_site_der_status",
]


def upgrade() -> None:
    # --- Flatten live DER sub resources onto site_id ---
    for table, pk in CHILD_TABLES:
        op.add_column(table, sa.Column("site_id", sa.Integer(), nullable=True))

        # Backfill site_id from the parent site_der
        op.execute(
            f"UPDATE {table} AS c SET site_id = sd.site_id FROM site_der sd WHERE sd.site_der_id = c.site_der_id"  # noqa: S608
        )

        # De-duplicate: the old schema permitted (via a concurrency bug) multiple site_der rows per site, which could
        # leave more than one row of the same sub resource type per site. Only one is allowed per site now - keep the
        # most recently changed (tie broken by pk) and drop the rest.
        op.execute(
            f"DELETE FROM {table} a USING {table} b WHERE a.site_id = b.site_id "  # noqa: S608
            f"AND (a.changed_time < b.changed_time OR (a.changed_time = b.changed_time AND a.{pk} < b.{pk}))"
        )

        op.alter_column(table, "site_id", existing_type=sa.Integer(), nullable=False)
        op.create_foreign_key(f"{table}_site_id_fkey", table, "site", ["site_id"], ["site_id"], ondelete="CASCADE")
        op.create_unique_constraint(f"{table}_site_id_key", table, ["site_id"])

        op.drop_constraint(f"{table}_site_der_id_fkey", table, type_="foreignkey")
        op.drop_constraint(f"{table}_site_der_id_key", table, type_="unique")
        op.drop_column(table, "site_der_id")

    # --- Flatten archived DER sub resources onto site_id ---
    # For deleted entities the live site_der is gone, so resolve site_id from archive_site_der as well.
    for table in ARCHIVE_CHILD_TABLES:
        op.add_column(table, sa.Column("site_id", sa.Integer(), nullable=True))
        op.execute(
            f"UPDATE {table} AS c SET site_id = COALESCE("  # noqa: S608
            f"(SELECT sd.site_id FROM site_der sd WHERE sd.site_der_id = c.site_der_id), "
            f"(SELECT asd.site_id FROM archive_site_der asd WHERE asd.site_der_id = c.site_der_id "
            f"ORDER BY asd.archive_id DESC LIMIT 1))"
        )
        op.drop_column(table, "site_der_id")

    # --- Drop the now-unused parent tables ---
    op.drop_index(op.f("ix_archive_site_der_site_der_id"), table_name="archive_site_der")
    op.drop_index(op.f("ix_archive_site_der_deleted_time"), table_name="archive_site_der")
    op.drop_table("archive_site_der")

    op.drop_index(op.f("ix_site_der_changed_time"), table_name="site_der")
    op.drop_table("site_der")


def downgrade() -> None:
    # Recreate the parent tables. NOTE: this is a best effort reconstruction - duplicate sub resource rows removed
    # during upgrade are not restored, and original site_der ids / archive linkages cannot be recovered.
    op.create_table(
        "site_der",
        sa.Column("site_der_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("changed_time", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["site.site_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("site_der_id"),
    )
    op.create_index(op.f("ix_site_der_changed_time"), "site_der", ["changed_time"], unique=False)

    op.create_table(
        "archive_site_der",
        sa.Column("archive_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("archive_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("site_der_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_time", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("archive_id"),
    )
    op.create_index(op.f("ix_archive_site_der_deleted_time"), "archive_site_der", ["deleted_time"], unique=False)
    op.create_index(op.f("ix_archive_site_der_site_der_id"), "archive_site_der", ["site_der_id"], unique=False)

    # Reconstitute a single site_der per site that has any DER sub resource
    op.execute(
        "INSERT INTO site_der (site_id, created_time, changed_time) "
        "SELECT site_id, now(), now() FROM ("
        "SELECT site_id FROM site_der_rating "
        "UNION SELECT site_id FROM site_der_setting "
        "UNION SELECT site_id FROM site_der_availability "
        "UNION SELECT site_id FROM site_der_status"
        ") s"
    )

    for table, _pk in CHILD_TABLES:
        op.add_column(table, sa.Column("site_der_id", sa.Integer(), nullable=True))
        op.execute(
            f"UPDATE {table} AS c SET site_der_id = sd.site_der_id FROM site_der sd WHERE sd.site_id = c.site_id"  # noqa: S608
        )
        op.alter_column(table, "site_der_id", existing_type=sa.Integer(), nullable=False)
        op.create_foreign_key(
            f"{table}_site_der_id_fkey", table, "site_der", ["site_der_id"], ["site_der_id"], ondelete="CASCADE"
        )
        op.create_unique_constraint(f"{table}_site_der_id_key", table, ["site_der_id"])

        op.drop_constraint(f"{table}_site_id_fkey", table, type_="foreignkey")
        op.drop_constraint(f"{table}_site_id_key", table, type_="unique")
        op.drop_column(table, "site_id")

    for table in ARCHIVE_CHILD_TABLES:
        op.add_column(table, sa.Column("site_der_id", sa.Integer(), nullable=False, server_default="0"))
        op.alter_column(table, "site_der_id", server_default=None)
        op.drop_column(table, "site_id")
