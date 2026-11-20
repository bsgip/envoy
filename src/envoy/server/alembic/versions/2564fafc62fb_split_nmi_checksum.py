"""split nmi checksum

Splits the 11 character site.nmi column into a 10 character nmi and a separate (nullable) single character
nmi_checksum. Existing 11 character NMIs will be migrated so that the 11th character becomes the nmi_checksum. NMIs
with <= 10 characters will have a NULL nmi_checksum.

Revision ID: 2564fafc62fb
Revises: beb692fa34d5
Create Date: 2026-11-20 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2564fafc62fb"
down_revision = "beb692fa34d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("site", sa.Column("nmi_checksum", sa.VARCHAR(length=1), nullable=True))
    op.add_column("archive_site", sa.Column("nmi_checksum", sa.VARCHAR(length=1), nullable=True))

    # Migrate any 11 char NMIs so that the trailing char becomes the checksum. NMIs of length <= 10 are left as is
    op.execute(
        "UPDATE site SET nmi_checksum = SUBSTRING(nmi FROM 11 FOR 1), nmi = SUBSTRING(nmi FROM 1 FOR 10) "
        "WHERE LENGTH(nmi) = 11"
    )
    op.execute(
        "UPDATE archive_site SET nmi_checksum = SUBSTRING(nmi FROM 11 FOR 1), nmi = SUBSTRING(nmi FROM 1 FOR 10) "
        "WHERE LENGTH(nmi) = 11"
    )

    op.alter_column(
        "site", "nmi", existing_type=sa.VARCHAR(length=11), type_=sa.VARCHAR(length=10), existing_nullable=True
    )
    op.alter_column(
        "archive_site", "nmi", existing_type=sa.VARCHAR(length=11), type_=sa.VARCHAR(length=10), existing_nullable=True
    )


def downgrade() -> None:
    op.alter_column(
        "site", "nmi", existing_type=sa.VARCHAR(length=10), type_=sa.VARCHAR(length=11), existing_nullable=True
    )
    op.alter_column(
        "archive_site", "nmi", existing_type=sa.VARCHAR(length=10), type_=sa.VARCHAR(length=11), existing_nullable=True
    )

    # Recombine the checksum back into the NMI
    op.execute("UPDATE site SET nmi = nmi || nmi_checksum WHERE nmi IS NOT NULL AND nmi_checksum IS NOT NULL")
    op.execute("UPDATE archive_site SET nmi = nmi || nmi_checksum WHERE nmi IS NOT NULL AND nmi_checksum IS NOT NULL")

    op.drop_column("archive_site", "nmi_checksum")
    op.drop_column("site", "nmi_checksum")
