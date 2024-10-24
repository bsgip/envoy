from datetime import datetime
from typing import Optional

from sqlalchemy import DOUBLE_PRECISION, INTEGER, VARCHAR, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from envoy.server.model import Base


class CalculationLogVariableValue(Base):
    """Represents a single time series observation for a calculation log. The observation is differentiated
    by the variable id, the site_id that it applies to (if any) and the moment in time it references"""

    __tablename__ = "calculation_log_variable_value"

    # Id of the parent calculation log that owns this value
    calculation_log_id: Mapped[int] = mapped_column(
        ForeignKey("calculation_log.calculation_log_id", ondelete="CASCADE"), primary_key=True
    )

    # ID defined by the client that disambiguate one set of time-series from another data from another. eg: a value of 1
    # might represent weather forecast temperature, a value of 2 might represent forecast load etc. The actual
    # definitions are completely opaque to utility server.
    variable_id: Mapped[int] = mapped_column(INTEGER, primary_key=True)

    # This is DELIBERATELY not a foreign key relationship as we want to track a moment in time correlation of
    # site ID. This is for the client managing this log to ensure correctness. If the site is deleted in the future
    # we want this to remain as is.
    #
    # What site does this value apply to (0 corresponds to a value of None in the public model)
    site_id_snapshot: Mapped[int] = mapped_column(INTEGER, primary_key=True)

    # When does this time series observation occur? Defines the numbered "interval" relative to the parent
    # CalculationLog.calculation_range_start. A value of N uses the following formula for calculating datetime:
    # CalculationLog.calculation_range_start + N * CalculationLog.interval_width_seconds
    interval_period: Mapped[int] = mapped_column(INTEGER, primary_key=True)

    # The actual time series value associated with the linked variable_id, site_id and interval_period
    value: Mapped[float] = mapped_column(DOUBLE_PRECISION)

    calculation_log: Mapped["CalculationLog"] = relationship(back_populates="variable_values", lazy="raise")


class CalculationLogVariableMetadata(Base):
    """Human readable metadata for describing a variable with an ID associated with a CalculationLog"""

    __tablename__ = "calculation_log_variable_metadata"

    # The parent calculation log ID
    calculation_log_id: Mapped[int] = mapped_column(
        ForeignKey("calculation_log.calculation_log_id", ondelete="CASCADE"), primary_key=True
    )

    # ID defined by the client that disambiguate one set of time-series from another data from another. eg: a value of 1
    # might represent weather forecast temperature, a value of 2 might represent forecast load etc. The actual
    # definitions are completely opaque to utility server.
    variable_id: Mapped[int] = mapped_column(INTEGER, primary_key=True)
    name: Mapped[str] = mapped_column(VARCHAR(length=64))  # Human readable name of variable
    description: Mapped[str] = mapped_column(VARCHAR(length=512))  # Human readable description of variable

    calculation_log: Mapped["CalculationLog"] = relationship(back_populates="variable_metadata", lazy="raise")


class CalculationLog(Base):
    """Represents the top level entity describing a single audit log of a historical calculation run.

    Calculation runs typically represent running powerflow / other model for some network. A calculation log represents
    a (mostly) opaque log of values defined by an external calculation engine. Any given calculation log has the
    following assumptions:
        * A calculation log represents a defined "range" of time for which the output calculations apply for
           eg: A single log might represent a 24 hour period of time - typically this range is in advance of when the
               calculations are being made.
        * A calculation log is divided into fixed width intervals of a known size, eg 5 minutes. All input data/outputs
          are aligned with these intervals. Eg - A 24 hour period is broken down into intervals of length 1 hour.
        * A calculation log has logged "variable" data representing input/intermediate/output data. This data is opaque
          to the utility server but it WILL align with intervals."""

    __tablename__ = "calculation_log"

    calculation_log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    calculation_range_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )  # The start time of the first interval within this calculation log.

    # Number of seconds that define the width of this entire calculation log
    calculation_range_duration_seconds: Mapped[int] = mapped_column(INTEGER)

    # Number of seconds for the fixed width intervals that comprise this calculation log
    interval_width_seconds: Mapped[int] = mapped_column(INTEGER)

    topology_id: Mapped[Optional[str]] = mapped_column(
        VARCHAR(length=64), nullable=True
    )  # id for topology used in this calculation (eg - Feeder ID)

    external_id: Mapped[Optional[str]] = mapped_column(VARCHAR(length=64), nullable=True)  # External unique reference
    description: Mapped[Optional[str]] = mapped_column(VARCHAR(length=1024), nullable=True)  # Free text description

    power_forecast_creation_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # When was the power forecast made (not when it's for)

    # When was the last (most recent) historical lag. The time between this and the calculation_range_start
    # represents how stale the lag data was.
    power_forecast_basis_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    weather_forecast_creation_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # When was the weather forecast made (not when it's for)
    weather_forecast_location_id: Mapped[Optional[str]] = mapped_column(
        VARCHAR(length=128), nullable=True
    )  # External unique identifier for the location that the weather forecast was drawn from

    variable_values: Mapped[list["CalculationLogVariableValue"]] = relationship(
        back_populates="calculation_log",
        lazy="raise",
        cascade="all, delete",
        passive_deletes=True,
        order_by=[
            CalculationLogVariableValue.calculation_log_id,
            CalculationLogVariableValue.variable_id,
            CalculationLogVariableValue.site_id_snapshot,
            CalculationLogVariableValue.interval_period,
        ],
    )  # What variable values reference this calculation log
    variable_metadata: Mapped[list["CalculationLogVariableMetadata"]] = relationship(
        back_populates="calculation_log",
        lazy="raise",
        cascade="all, delete",
        passive_deletes=True,
    )  # What variable metadata reference this calculation log
