"""add_new_doe_fields

Revision ID: 5d27d3c8d002
Revises: 3cd2245c7c00
Create Date: 2025-05-11 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5d27d3c8d002'
down_revision: Union[str, None] = '33a17317e7ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make existing power columns nullable in both tables
    op.alter_column('dynamic_operating_envelope', 'import_limit_active_watts', nullable=True)
    op.alter_column('dynamic_operating_envelope', 'export_limit_watts', nullable=True)
    op.alter_column('archive_dynamic_operating_envelope', 'import_limit_active_watts', nullable=True)
    op.alter_column('archive_dynamic_operating_envelope', 'export_limit_watts', nullable=True)

    # Add new columns to dynamic_operating_envelope table
    op.add_column('dynamic_operating_envelope', sa.Column('generation_limit_watts', sa.DECIMAL(precision=16, scale=2), nullable=True))
    op.add_column('dynamic_operating_envelope', sa.Column('load_limit_watts', sa.DECIMAL(precision=16, scale=2), nullable=True))
    op.add_column('dynamic_operating_envelope', sa.Column('max_limit_percent', sa.DECIMAL(precision=5, scale=2), nullable=True))
    op.add_column('dynamic_operating_envelope', sa.Column('energize', sa.Boolean(), nullable=True))

    # Add new columns to archive_dynamic_operating_envelope table
    op.add_column('archive_dynamic_operating_envelope', sa.Column('generation_limit_watts', sa.DECIMAL(precision=16, scale=2), nullable=True))
    op.add_column('archive_dynamic_operating_envelope', sa.Column('load_limit_watts', sa.DECIMAL(precision=16, scale=2), nullable=True))
    op.add_column('archive_dynamic_operating_envelope', sa.Column('max_limit_percent', sa.DECIMAL(precision=5, scale=2), nullable=True))
    op.add_column('archive_dynamic_operating_envelope', sa.Column('energize', sa.Boolean(), nullable=True))


def downgrade() -> None:
    # Remove the new columns from archive table
    op.drop_column('archive_dynamic_operating_envelope', 'energize')
    op.drop_column('archive_dynamic_operating_envelope', 'max_limit_percent')
    op.drop_column('archive_dynamic_operating_envelope', 'load_limit_watts')
    op.drop_column('archive_dynamic_operating_envelope', 'generation_limit_watts')

    # Remove the new columns from main table
    op.drop_column('dynamic_operating_envelope', 'energize')
    op.drop_column('dynamic_operating_envelope', 'max_limit_percent')
    op.drop_column('dynamic_operating_envelope', 'load_limit_watts')
    op.drop_column('dynamic_operating_envelope', 'generation_limit_watts')

    # Make existing power columns non-nullable again in both tables
    op.alter_column('dynamic_operating_envelope', 'import_limit_active_watts', nullable=False)
    op.alter_column('dynamic_operating_envelope', 'export_limit_watts', nullable=False)
    op.alter_column('archive_dynamic_operating_envelope', 'import_limit_active_watts', nullable=False)
    op.alter_column('archive_dynamic_operating_envelope', 'export_limit_watts', nullable=False)
