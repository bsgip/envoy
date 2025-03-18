from datetime import datetime
from decimal import Decimal
from typing import Optional

from envoy_schema.server.schema.sep2.der import (
    AbnormalCategoryType,
    AlarmStatusType,
    ConnectStatusType,
    DERControlType,
    DERType,
    DOESupportedMode,
    InverterStatusType,
    LocalControlModeStatusType,
    NormalCategoryType,
    OperationalModeStatusType,
    StorageModeStatusType,
)
from envoy_schema.server.schema.sep2.types import DeviceCategory
from sqlalchemy import DECIMAL, INTEGER, VARCHAR, BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column

import envoy.server.model as original_models
from envoy.server.model.archive import ArchiveBase
from envoy.server.model.archive.base import ARCHIVE_TABLE_PREFIX


class ArchiveSite(ArchiveBase):
    __tablename__ = ARCHIVE_TABLE_PREFIX + original_models.Site.__tablename__  # type: ignore

    site_id: Mapped[int] = mapped_column(index=True)  # This is the original PK
    nmi: Mapped[Optional[str]] = mapped_column(VARCHAR(length=11), nullable=True)
    aggregator_id: Mapped[int] = mapped_column(INTEGER, nullable=False)  # This was originally a FK

    timezone_id: Mapped[str] = mapped_column(VARCHAR(length=64), nullable=False)
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lfdi: Mapped[str] = mapped_column(VARCHAR(length=42), nullable=False)
    sfdi: Mapped[int] = mapped_column(BigInteger, nullable=False)
    device_category: Mapped[DeviceCategory] = mapped_column(INTEGER, nullable=False)
    registration_pin: Mapped[int] = mapped_column(INTEGER, nullable=False)


class ArchiveSiteDER(ArchiveBase):
    __tablename__ = ARCHIVE_TABLE_PREFIX + original_models.SiteDER.__tablename__  # type: ignore

    site_der_id: Mapped[int] = mapped_column(index=True)  # This is the original PK
    site_id: Mapped[int] = mapped_column(INTEGER)  # This was originally a FK

    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArchiveSiteDERRating(ArchiveBase):
    __tablename__ = ARCHIVE_TABLE_PREFIX + original_models.SiteDERRating.__tablename__  # type: ignore

    site_der_rating_id: Mapped[int] = mapped_column(index=True)  # This is the original PK
    site_der_id: Mapped[int] = mapped_column(INTEGER)  # This was originally a FK
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    modes_supported: Mapped[Optional[DERControlType]] = mapped_column(INTEGER, nullable=True)
    abnormal_category: Mapped[Optional[AbnormalCategoryType]] = mapped_column(INTEGER, nullable=True)
    max_a_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_a_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_ah_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_ah_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_charge_rate_va_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_charge_rate_va_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_charge_rate_w_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_charge_rate_w_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_discharge_rate_va_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_discharge_rate_va_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_discharge_rate_w_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_discharge_rate_w_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_v_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_v_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_va_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_va_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_var_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_var_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_var_neg_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_var_neg_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_w_value: Mapped[int] = mapped_column(INTEGER)
    max_w_multiplier: Mapped[int] = mapped_column(INTEGER)
    max_wh_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_wh_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    min_pf_over_excited_displacement: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    min_pf_over_excited_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    min_pf_under_excited_displacement: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    min_pf_under_excited_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    min_v_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    min_v_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    normal_category: Mapped[Optional[NormalCategoryType]] = mapped_column(INTEGER, nullable=True)
    over_excited_pf_displacement: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    over_excited_pf_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    over_excited_w_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    over_excited_w_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    reactive_susceptance_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    reactive_susceptance_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    under_excited_pf_displacement: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    under_excited_pf_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    under_excited_w_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    under_excited_w_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    v_nom_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    v_nom_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    der_type: Mapped[DERType] = mapped_column(INTEGER)
    doe_modes_supported: Mapped[Optional[DOESupportedMode]] = mapped_column(INTEGER, nullable=True)


class ArchiveSiteDERSetting(ArchiveBase):
    __tablename__ = ARCHIVE_TABLE_PREFIX + original_models.SiteDERSetting.__tablename__  # type: ignore

    site_der_setting_id: Mapped[int] = mapped_column(INTEGER, index=True)  # This is the original PK
    site_der_id: Mapped[int] = mapped_column(INTEGER)  # This was originally a FK
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    modes_enabled: Mapped[Optional[DERControlType]] = mapped_column(INTEGER, nullable=True)
    es_delay: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    es_high_freq: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    es_high_volt: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    es_low_freq: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    es_low_volt: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    es_ramp_tms: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    es_random_delay: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    grad_w: Mapped[int] = mapped_column(INTEGER)
    max_a_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_a_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_ah_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_ah_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_charge_rate_va_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_charge_rate_va_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_charge_rate_w_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_charge_rate_w_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_discharge_rate_va_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_discharge_rate_va_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_discharge_rate_w_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_discharge_rate_w_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_v_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_v_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_va_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_va_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_var_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_var_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_var_neg_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_var_neg_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_w_value: Mapped[int] = mapped_column(INTEGER)
    max_w_multiplier: Mapped[int] = mapped_column(INTEGER)
    max_wh_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_wh_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    min_pf_over_excited_displacement: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    min_pf_over_excited_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    min_pf_under_excited_displacement: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    min_pf_under_excited_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    min_v_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    min_v_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    soft_grad_w: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    v_nom_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    v_nom_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    v_ref_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    v_ref_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    v_ref_ofs_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    v_ref_ofs_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    doe_modes_enabled: Mapped[Optional[DOESupportedMode]] = mapped_column(INTEGER, nullable=True)


class ArchiveSiteDERAvailability(ArchiveBase):
    __tablename__ = ARCHIVE_TABLE_PREFIX + original_models.SiteDERAvailability.__tablename__  # type: ignore

    site_der_availability_id: Mapped[int] = mapped_column(index=True)  # This is the original PK
    site_der_id: Mapped[int] = mapped_column(INTEGER)  # This was originally a FK
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # When the SiteDERAvailability was created
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    availability_duration_sec: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    max_charge_duration_sec: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    reserved_charge_percent: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(8, original_models.PERCENT_DECIMAL_PLACES), nullable=True
    )
    reserved_deliver_percent: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(8, original_models.PERCENT_DECIMAL_PLACES), nullable=True
    )
    estimated_var_avail_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    estimated_var_avail_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    estimated_w_avail_value: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    estimated_w_avail_multiplier: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)


class ArchiveSiteDERStatus(ArchiveBase):
    __tablename__ = ARCHIVE_TABLE_PREFIX + original_models.SiteDERStatus.__tablename__  # type: ignore

    site_der_status_id: Mapped[int] = mapped_column(index=True)  # This is the original PK
    site_der_id: Mapped[int] = mapped_column(INTEGER)  # This was originally a FK
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    alarm_status: Mapped[Optional[AlarmStatusType]] = mapped_column(INTEGER, nullable=True)
    generator_connect_status: Mapped[Optional[ConnectStatusType]] = mapped_column(INTEGER, nullable=True)
    generator_connect_status_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    inverter_status: Mapped[Optional[InverterStatusType]] = mapped_column(INTEGER, nullable=True)
    inverter_status_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    local_control_mode_status: Mapped[Optional[LocalControlModeStatusType]] = mapped_column(INTEGER, nullable=True)
    local_control_mode_status_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    manufacturer_status: Mapped[Optional[str]] = mapped_column(VARCHAR(6), nullable=True)
    manufacturer_status_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    operational_mode_status: Mapped[Optional[OperationalModeStatusType]] = mapped_column(INTEGER, nullable=True)
    operational_mode_status_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    state_of_charge_status: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    state_of_charge_status_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    storage_mode_status: Mapped[Optional[StorageModeStatusType]] = mapped_column(INTEGER, nullable=True)
    storage_mode_status_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    storage_connect_status: Mapped[Optional[ConnectStatusType]] = mapped_column(INTEGER, nullable=True)
    storage_connect_status_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
