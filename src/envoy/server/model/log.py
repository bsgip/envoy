from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DECIMAL, INTEGER, VARCHAR, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from envoy.server.model import Base


class PowerForecastLog(Base):
    """Represents a power forecast (either for a site known to utility server or something else) for a specific
    timestamp that was used to inform a parent CalculationLog"""

    __tablename__ = "power_forecast_log"

    power_forecast_log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    interval_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # When is this forecast specifically for?
    interval_duration_seconds: Mapped[int] = mapped_column(INTEGER)
    external_device_id: Mapped[Optional[str]] = mapped_column(
        VARCHAR(length=64), nullable=True
    )  # External unique reference to the device (if any) that this target is for
    site_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("site.site_id"), nullable=True
    )  # A reference to an internal site (if applicable) that this target is for

    active_power_watts: Mapped[Optional[int]] = mapped_column(
        INTEGER, nullable=True
    )  # The forecast active power in watts (+ import, - export)
    reactive_power_var: Mapped[Optional[int]] = mapped_column(
        INTEGER, nullable=True
    )  # The forecast reactive power in var

    calculation_log_id: Mapped[int] = mapped_column(
        ForeignKey("calculation_log.calculation_log_id", ondelete="CASCADE")
    )
    calculation_log: Mapped["CalculationLog"] = relationship(back_populates="power_forecast_logs", lazy="raise")


class PowerTargetLog(Base):
    """Represents a power target (either for a site known to utility server or something else) for a specific
    timestamp that was the result of a CalculationLog"""

    __tablename__ = "power_target_log"

    power_target_log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    interval_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # When is this forecast specifically for?
    interval_duration_seconds: Mapped[int] = mapped_column(INTEGER)
    external_device_id: Mapped[Optional[str]] = mapped_column(
        VARCHAR(length=64), nullable=True
    )  # External unique reference to the device (if any) that this target is for
    site_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("site.site_id"), nullable=True
    )  # A reference to an internal site (if applicable) that this target is for

    target_active_power_watts: Mapped[Optional[int]] = mapped_column(
        INTEGER, nullable=True
    )  # Target active power in watts (+import -export)
    target_reactive_power_var: Mapped[Optional[int]] = mapped_column(
        INTEGER, nullable=True
    )  # Target reactive power in var (+import -export)

    calculation_log_id: Mapped[int] = mapped_column(
        ForeignKey("calculation_log.calculation_log_id", ondelete="CASCADE")
    )
    calculation_log: Mapped["CalculationLog"] = relationship(back_populates="power_target_logs", lazy="raise")


class PowerFlowLog(Base):
    """Represents a log of a power flow calculation (either for a site known to utility server or something else) for
    a specific timestamp that was run at some point during the calculation process"""

    __tablename__ = "power_flow_log"

    power_flow_log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    interval_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # When is this forecast specifically for?
    interval_duration_seconds: Mapped[int] = mapped_column(INTEGER)
    external_device_id: Mapped[Optional[str]] = mapped_column(
        VARCHAR(length=64), nullable=True
    )  # External unique reference to the device (if any) that this target is for
    site_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("site.site_id"), nullable=True
    )  # A reference to an internal site (if applicable) that this target is for
    solve_name: Mapped[Optional[str]] = mapped_column(
        VARCHAR(length=16), nullable=True
    )  # Identifier of this solve - for distinguishing multiple power flow solves (eg: PRE / POST calculation solves)

    pu_voltage_min: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(8, 6))  # Constraint lower bound of pu_voltage
    pu_voltage_max: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(8, 6))  # Constraint upper bound of pu_voltage
    pu_voltage: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(8, 6))  # per unit voltage (1.0 being nominal)
    thermal_max_percent: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(8, 4))  # percent of thermal rating

    calculation_log_id: Mapped[int] = mapped_column(
        ForeignKey("calculation_log.calculation_log_id", ondelete="CASCADE")
    )
    calculation_log: Mapped["CalculationLog"] = relationship(back_populates="power_flow_logs", lazy="raise")


class WeatherForecastLog(Base):
    """Represents a weather forecast for a specific timestamp that was used to inform a parent CalculationLog"""

    __tablename__ = "weather_forecast_log"

    weather_forecast_log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    interval_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # When is this forecast specifically for?
    interval_duration_seconds: Mapped[int] = mapped_column(INTEGER)

    air_temperature_degrees_c: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2), nullable=True)
    apparent_temperature_degrees_c: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2), nullable=True)
    dew_point_degrees_c: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2), nullable=True)
    humidity_percent: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2), nullable=True)
    cloud_cover_percent: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2), nullable=True)
    rain_probability_percent: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2), nullable=True)
    rain_mm: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(8, 2), nullable=True)
    rain_rate_mm: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(8, 2), nullable=True)
    global_horizontal_irradiance_watts_m2: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(8, 2), nullable=True)
    wind_speed_50m_km_h: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(8, 2), nullable=True
    )  # wind speed at 50m elevation in kilometres per hour

    calculation_log_id: Mapped[int] = mapped_column(
        ForeignKey("calculation_log.calculation_log_id", ondelete="CASCADE")
    )

    calculation_log: Mapped["CalculationLog"] = relationship(back_populates="weather_forecast_logs", lazy="raise")


class CalculationLog(Base):
    """Represents the top level entity describing a single audit log of a historical calculation run.

    Calculation runs typically represent running powerflow / other model for some network based on forecast
    power/weather data (usually over multiple time steps) that may propose certain changes in DER behavior
    in order to satisfy certain network constraints"""

    __tablename__ = "calculation_log"

    calculation_log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    calculation_interval_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )  # What is the time period under calculation (start time - inclusive)
    calculation_interval_duration_seconds: Mapped[int] = mapped_column(INTEGER)

    topology_id: Mapped[Optional[str]] = mapped_column(
        VARCHAR(length=64), nullable=True
    )  # id for topology used in this calculation (eg - Feeder ID)

    external_id: Mapped[Optional[str]] = mapped_column(VARCHAR(length=64), nullable=True)  # External unique reference
    description: Mapped[Optional[str]] = mapped_column(VARCHAR(length=1024), nullable=True)  # Free text description

    power_forecast_creation_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # When was the power forecast made (not when it's for)
    weather_forecast_creation_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # When was the weather forecast made (not when it's for)
    weather_forecast_location_id: Mapped[Optional[str]] = mapped_column(
        VARCHAR(length=128), nullable=True
    )  # External unique identifier for the location that the weather forecast was drawn from

    power_forecast_logs: Mapped[list["PowerForecastLog"]] = relationship(
        back_populates="calculation_log",
        lazy="raise",
        cascade="all, delete",
        passive_deletes=True,
    )  # What weather forecast logs reference this calculation log
    power_target_logs: Mapped[list["PowerTargetLog"]] = relationship(
        back_populates="calculation_log",
        lazy="raise",
        cascade="all, delete",
        passive_deletes=True,
    )  # What power target logs reference this calculation log
    power_flow_logs: Mapped[list["PowerFlowLog"]] = relationship(
        back_populates="calculation_log",
        lazy="raise",
        cascade="all, delete",
        passive_deletes=True,
    )  # What power flow logs reference this calculation log
    weather_forecast_logs: Mapped[list["WeatherForecastLog"]] = relationship(
        back_populates="calculation_log",
        lazy="raise",
        cascade="all, delete",
        passive_deletes=True,
    )  # What weather forecast logs reference this calculation log
