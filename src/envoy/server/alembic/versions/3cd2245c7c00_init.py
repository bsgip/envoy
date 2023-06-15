"""init

Revision ID: 3cd2245c7c00
Revises: 
Create Date: 2023-06-09 10:33:34.002509

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3cd2245c7c00"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "aggregator",
        sa.Column("aggregator_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("aggregator_id"),
    )
    op.create_table(
        "certificate",
        sa.Column("certificate_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lfdi", sa.VARCHAR(length=42), nullable=False),
        sa.Column("expiry", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("certificate_id"),
    )
    op.create_table(
        "tariff",
        sa.Column("tariff_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("dnsp_code", sa.String(length=20), nullable=False),
        sa.Column("currency_code", sa.Integer(), nullable=False),
        sa.Column("changed_time", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("tariff_id"),
    )
    op.create_table(
        "aggregator_certificate_assignment",
        sa.Column("assignment_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("certificate_id", sa.Integer(), nullable=False),
        sa.Column("aggregator_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["aggregator_id"],
            ["aggregator.aggregator_id"],
        ),
        sa.ForeignKeyConstraint(
            ["certificate_id"],
            ["certificate.certificate_id"],
        ),
        sa.PrimaryKeyConstraint("assignment_id"),
    )
    op.create_table(
        "site",
        sa.Column("site_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nmi", sa.VARCHAR(length=11), nullable=True),
        sa.Column("aggregator_id", sa.Integer(), nullable=False),
        sa.Column("timezone_id", sa.VARCHAR(length=64), nullable=False),
        sa.Column("changed_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lfdi", sa.VARCHAR(length=42), nullable=False),
        sa.Column("sfdi", sa.BigInteger(), nullable=False),
        sa.Column("device_category", sa.INTEGER(), nullable=False),
        sa.ForeignKeyConstraint(
            ["aggregator_id"],
            ["aggregator.aggregator_id"],
        ),
        sa.PrimaryKeyConstraint("site_id"),
        sa.UniqueConstraint("lfdi"),
        sa.UniqueConstraint("lfdi", "aggregator_id", name="lfdi_aggregator_id_uc"),
        sa.UniqueConstraint("sfdi", "aggregator_id", name="sfdi_aggregator_id_uc"),
    )
    op.create_table(
        "dynamic_operating_envelope",
        sa.Column("dynamic_operating_envelope_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("changed_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("import_limit_active_watts", sa.DECIMAL(precision=16, scale=2), nullable=False),
        sa.Column("export_limit_watts", sa.DECIMAL(precision=16, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["site.site_id"],
        ),
        sa.PrimaryKeyConstraint("dynamic_operating_envelope_id"),
        sa.UniqueConstraint("site_id", "start_time", name="site_id_start_time_uc"),
    )
    op.create_table(
        "site_reading_type",
        sa.Column("site_reading_type_id", sa.Integer(), nullable=False),
        sa.Column("aggregator_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("uom", sa.INTEGER(), nullable=False),
        sa.Column("data_qualifier", sa.INTEGER(), nullable=False),
        sa.Column("flow_direction", sa.INTEGER(), nullable=False),
        sa.Column("accumulation_behaviour", sa.INTEGER(), nullable=False),
        sa.Column("kind", sa.INTEGER(), nullable=False),
        sa.Column("phase", sa.INTEGER(), nullable=False),
        sa.Column("power_of_ten_multiplier", sa.INTEGER(), nullable=False),
        sa.Column("default_interval_seconds", sa.INTEGER(), nullable=False),
        sa.Column("changed_time", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["aggregator_id"],
            ["aggregator.aggregator_id"],
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["site.site_id"],
        ),
        sa.PrimaryKeyConstraint("site_reading_type_id"),
        sa.UniqueConstraint(
            "aggregator_id",
            "site_id",
            "uom",
            "data_qualifier",
            "flow_direction",
            "accumulation_behaviour",
            "kind",
            "phase",
            "power_of_ten_multiplier",
            "default_interval_seconds",
            name="site_reading_type_all_values_uc",
        ),
    )
    op.create_table(
        "tariff_generated_rate",
        sa.Column("tariff_generated_rate_id", sa.Integer(), nullable=False),
        sa.Column("tariff_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("changed_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("import_active_price", sa.DECIMAL(precision=10, scale=4), nullable=False),
        sa.Column("export_active_price", sa.DECIMAL(precision=10, scale=4), nullable=False),
        sa.Column("import_reactive_price", sa.DECIMAL(precision=10, scale=4), nullable=False),
        sa.Column("export_reactive_price", sa.DECIMAL(precision=10, scale=4), nullable=False),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["site.site_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tariff_id"],
            ["tariff.tariff_id"],
        ),
        sa.PrimaryKeyConstraint("tariff_generated_rate_id"),
        sa.UniqueConstraint("tariff_id", "site_id", "start_time", name="tariff_id_site_id_start_time_uc"),
    )
    op.create_table(
        "site_reading",
        sa.Column("site_reading_id", sa.Integer(), nullable=False),
        sa.Column("site_reading_type_id", sa.Integer(), nullable=False),
        sa.Column("changed_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("local_id", sa.INTEGER(), nullable=True),
        sa.Column("quality_flags", sa.INTEGER(), nullable=False),
        sa.Column("time_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("time_period_seconds", sa.INTEGER(), nullable=False),
        sa.Column("value", sa.INTEGER(), nullable=False),
        sa.ForeignKeyConstraint(
            ["site_reading_type_id"],
            ["site_reading_type.site_reading_type_id"],
        ),
        sa.PrimaryKeyConstraint("site_reading_id"),
        sa.UniqueConstraint(
            "site_reading_type_id", "time_period_start", name="site_reading_type_id_time_period_start_uc"
        ),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("site_reading")
    op.drop_table("tariff_generated_rate")
    op.drop_table("site_reading_type")
    op.drop_table("dynamic_operating_envelope")
    op.drop_table("site")
    op.drop_table("aggregator_certificate_assignment")
    op.drop_table("tariff")
    op.drop_table("certificate")
    op.drop_table("aggregator")
    # ### end Alembic commands ###