"""added_siteder

Revision ID: 9edddd3c2d15
Revises: 28d4321746ee
Create Date: 2024-03-11 18:12:02.282504

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9edddd3c2d15"
down_revision = "28d4321746ee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "site_der",
        sa.Column("site_der_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("changed_time", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["site.site_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("site_der_id"),
    )
    op.create_index(op.f("ix_site_der_changed_time"), "site_der", ["changed_time"], unique=False)
    op.create_table(
        "site_der_availability",
        sa.Column("site_der_availability_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_der_id", sa.Integer(), nullable=False),
        sa.Column("changed_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("availability_duration_sec", sa.INTEGER(), nullable=True),
        sa.Column("max_charge_duration_sec", sa.INTEGER(), nullable=True),
        sa.Column("reserved_charge_percent", sa.DECIMAL(precision=8, scale=4), nullable=True),
        sa.Column("reserved_deliver_percent", sa.DECIMAL(precision=8, scale=4), nullable=True),
        sa.Column("estimated_var_avail_value", sa.INTEGER(), nullable=True),
        sa.Column("estimated_var_avail_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("estimated_w_avail_value", sa.INTEGER(), nullable=True),
        sa.Column("estimated_w_avail_multiplier", sa.INTEGER(), nullable=True),
        sa.ForeignKeyConstraint(["site_der_id"], ["site_der.site_der_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("site_der_availability_id"),
        sa.UniqueConstraint("site_der_id"),
    )
    op.create_index(
        op.f("ix_site_der_availability_changed_time"), "site_der_availability", ["changed_time"], unique=False
    )
    op.create_table(
        "site_der_rating",
        sa.Column("site_der_rating_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_der_id", sa.Integer(), nullable=False),
        sa.Column("changed_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modes_supported", sa.INTEGER(), nullable=True),
        sa.Column("abnormal_category", sa.INTEGER(), nullable=True),
        sa.Column("max_a_value", sa.INTEGER(), nullable=True),
        sa.Column("max_a_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_ah_value", sa.INTEGER(), nullable=True),
        sa.Column("max_ah_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_charge_rate_va_value", sa.INTEGER(), nullable=True),
        sa.Column("max_charge_rate_va_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_charge_rate_w_value", sa.INTEGER(), nullable=True),
        sa.Column("max_charge_rate_w_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_discharge_rate_va_value", sa.INTEGER(), nullable=True),
        sa.Column("max_discharge_rate_va_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_discharge_rate_w_value", sa.INTEGER(), nullable=True),
        sa.Column("max_discharge_rate_w_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_v_value", sa.INTEGER(), nullable=True),
        sa.Column("max_v_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_va_value", sa.INTEGER(), nullable=True),
        sa.Column("max_va_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_var_value", sa.INTEGER(), nullable=True),
        sa.Column("max_var_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_var_neg_value", sa.INTEGER(), nullable=True),
        sa.Column("max_var_neg_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_w_value", sa.INTEGER(), nullable=False),
        sa.Column("max_w_multiplier", sa.INTEGER(), nullable=False),
        sa.Column("max_wh_value", sa.INTEGER(), nullable=True),
        sa.Column("max_wh_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("min_pf_over_excited_displacement", sa.INTEGER(), nullable=True),
        sa.Column("min_pf_over_excited_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("min_pf_under_excited_displacement", sa.INTEGER(), nullable=True),
        sa.Column("min_pf_under_excited_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("min_v_value", sa.INTEGER(), nullable=True),
        sa.Column("min_v_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("normal_category", sa.INTEGER(), nullable=True),
        sa.Column("over_excited_pf_displacement", sa.INTEGER(), nullable=True),
        sa.Column("over_excited_pf_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("over_excited_w_value", sa.INTEGER(), nullable=True),
        sa.Column("over_excited_w_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("reactive_susceptance_value", sa.INTEGER(), nullable=True),
        sa.Column("reactive_susceptance_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("under_excited_pf_displacement", sa.INTEGER(), nullable=True),
        sa.Column("under_excited_pf_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("under_excited_w_value", sa.INTEGER(), nullable=True),
        sa.Column("under_excited_w_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("v_nom_value", sa.INTEGER(), nullable=True),
        sa.Column("v_nom_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("der_type", sa.INTEGER(), nullable=False),
        sa.Column("doe_modes_supported", sa.INTEGER(), nullable=True),
        sa.ForeignKeyConstraint(["site_der_id"], ["site_der.site_der_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("site_der_rating_id"),
        sa.UniqueConstraint("site_der_id"),
    )
    op.create_index(op.f("ix_site_der_rating_changed_time"), "site_der_rating", ["changed_time"], unique=False)
    op.create_table(
        "site_der_setting",
        sa.Column("site_der_setting_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_der_id", sa.Integer(), nullable=False),
        sa.Column("changed_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modes_enabled", sa.INTEGER(), nullable=True),
        sa.Column("es_delay", sa.INTEGER(), nullable=True),
        sa.Column("es_high_freq", sa.INTEGER(), nullable=True),
        sa.Column("es_high_volt", sa.INTEGER(), nullable=True),
        sa.Column("es_low_freq", sa.INTEGER(), nullable=True),
        sa.Column("es_low_volt", sa.INTEGER(), nullable=True),
        sa.Column("es_ramp_tms", sa.INTEGER(), nullable=True),
        sa.Column("es_random_delay", sa.INTEGER(), nullable=True),
        sa.Column("grad_w", sa.INTEGER(), nullable=False),
        sa.Column("max_a_value", sa.INTEGER(), nullable=True),
        sa.Column("max_a_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_ah_value", sa.INTEGER(), nullable=True),
        sa.Column("max_ah_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_charge_rate_va_value", sa.INTEGER(), nullable=True),
        sa.Column("max_charge_rate_va_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_charge_rate_w_value", sa.INTEGER(), nullable=True),
        sa.Column("max_charge_rate_w_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_discharge_rate_va_value", sa.INTEGER(), nullable=True),
        sa.Column("max_discharge_rate_va_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_discharge_rate_w_value", sa.INTEGER(), nullable=True),
        sa.Column("max_discharge_rate_w_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_v_value", sa.INTEGER(), nullable=True),
        sa.Column("max_v_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_va_value", sa.INTEGER(), nullable=True),
        sa.Column("max_va_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_var_value", sa.INTEGER(), nullable=True),
        sa.Column("max_var_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_var_neg_value", sa.INTEGER(), nullable=True),
        sa.Column("max_var_neg_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("max_w_value", sa.INTEGER(), nullable=False),
        sa.Column("max_w_multiplier", sa.INTEGER(), nullable=False),
        sa.Column("max_wh_value", sa.INTEGER(), nullable=True),
        sa.Column("max_wh_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("min_pf_over_excited_displacement", sa.INTEGER(), nullable=True),
        sa.Column("min_pf_over_excited_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("min_pf_under_excited_displacement", sa.INTEGER(), nullable=True),
        sa.Column("min_pf_under_excited_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("min_v_value", sa.INTEGER(), nullable=True),
        sa.Column("min_v_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("soft_grad_w", sa.INTEGER(), nullable=True),
        sa.Column("v_nom_value", sa.INTEGER(), nullable=True),
        sa.Column("v_nom_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("v_ref_value", sa.INTEGER(), nullable=True),
        sa.Column("v_ref_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("v_ref_ofs_value", sa.INTEGER(), nullable=True),
        sa.Column("v_ref_ofs_multiplier", sa.INTEGER(), nullable=True),
        sa.Column("doe_modes_enabled", sa.INTEGER(), nullable=True),
        sa.ForeignKeyConstraint(["site_der_id"], ["site_der.site_der_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("site_der_setting_id"),
        sa.UniqueConstraint("site_der_id"),
    )
    op.create_index(op.f("ix_site_der_setting_changed_time"), "site_der_setting", ["changed_time"], unique=False)
    op.create_table(
        "site_der_status",
        sa.Column("site_der_status_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_der_id", sa.Integer(), nullable=False),
        sa.Column("changed_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("alarm_status", sa.INTEGER(), nullable=True),
        sa.Column("generator_connect_status", sa.INTEGER(), nullable=True),
        sa.Column("generator_connect_status_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("inverter_status", sa.INTEGER(), nullable=True),
        sa.Column("inverter_status_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("local_control_mode_status", sa.INTEGER(), nullable=True),
        sa.Column("local_control_mode_status_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("manufacturer_status", sa.VARCHAR(length=6), nullable=True),
        sa.Column("manufacturer_status_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("operational_mode_status", sa.INTEGER(), nullable=True),
        sa.Column("operational_mode_status_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state_of_charge_status", sa.INTEGER(), nullable=True),
        sa.Column("state_of_charge_status_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("storage_mode_status", sa.INTEGER(), nullable=True),
        sa.Column("storage_mode_status_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("storage_connect_status", sa.INTEGER(), nullable=True),
        sa.Column("storage_connect_status_time", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["site_der_id"], ["site_der.site_der_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("site_der_status_id"),
        sa.UniqueConstraint("site_der_id"),
    )
    op.create_index(op.f("ix_site_der_status_changed_time"), "site_der_status", ["changed_time"], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_site_der_status_changed_time"), table_name="site_der_status")
    op.drop_table("site_der_status")
    op.drop_index(op.f("ix_site_der_setting_changed_time"), table_name="site_der_setting")
    op.drop_table("site_der_setting")
    op.drop_index(op.f("ix_site_der_rating_changed_time"), table_name="site_der_rating")
    op.drop_table("site_der_rating")
    op.drop_index(op.f("ix_site_der_availability_changed_time"), table_name="site_der_availability")
    op.drop_table("site_der_availability")
    op.drop_index(op.f("ix_site_der_changed_time"), table_name="site_der")
    op.drop_table("site_der")
    # ### end Alembic commands ###