from datetime import datetime
from typing import Optional, Sequence

from envoy_schema.admin.schema.log import CalculationLogLabelMetadata as PublicLabelMetadata
from envoy_schema.admin.schema.log import CalculationLogLabelValues as PublicLabelValues
from envoy_schema.admin.schema.log import CalculationLogListResponse, CalculationLogRequest, CalculationLogResponse
from envoy_schema.admin.schema.log import CalculationLogVariableMetadata as PublicVariableMetadata
from envoy_schema.admin.schema.log import CalculationLogVariableValues as PublicVariableValues

from envoy.server.model.log import (
    CalculationLog,
    CalculationLogLabelMetadata,
    CalculationLogLabelValue,
    CalculationLogVariableMetadata,
    CalculationLogVariableValue,
)


class CalculationLogMapper:

    @staticmethod
    def map_from_request(changed_time: datetime, calculation_log: CalculationLogRequest) -> CalculationLog:

        var_vals = calculation_log.variable_values
        if var_vals is None:
            variable_values = []
        else:
            variable_values = [
                CalculationLogVariableValue(
                    variable_id=variable_id,
                    site_id_snapshot=0 if site_id is None else site_id,
                    interval_period=interval_period,
                    value=value,
                )
                for variable_id, site_id, interval_period, value in zip(
                    var_vals.variable_ids, var_vals.site_ids, var_vals.interval_periods, var_vals.values
                )
            ]

        label_vals = calculation_log.label_values
        if label_vals is None:
            label_values = []
        else:
            label_values = [
                CalculationLogLabelValue(
                    label_id=label_id,
                    site_id_snapshot=0 if site_id is None else site_id,
                    label=value,
                )
                for label_id, site_id, value in zip(label_vals.label_ids, label_vals.site_ids, label_vals.values)
            ]

        return CalculationLog(
            created_time=changed_time,
            calculation_range_start=calculation_log.calculation_range_start,
            calculation_range_duration_seconds=calculation_log.calculation_range_duration_seconds,
            interval_width_seconds=calculation_log.interval_width_seconds,
            topology_id=calculation_log.topology_id,
            external_id=calculation_log.external_id,
            description=calculation_log.description,
            power_forecast_creation_time=calculation_log.power_forecast_creation_time,
            power_forecast_basis_time=calculation_log.power_forecast_basis_time,
            weather_forecast_creation_time=calculation_log.weather_forecast_creation_time,
            weather_forecast_location_id=calculation_log.weather_forecast_location_id,
            variable_metadata=[
                CalculationLogVariableMetadata(
                    variable_id=e.variable_id,
                    name=e.name,
                    description=e.description,
                )
                for e in calculation_log.variable_metadata
            ],
            variable_values=variable_values,
            label_metadata=[
                CalculationLogLabelMetadata(
                    label_id=e.label_id,
                    name=e.name,
                    description=e.description,
                )
                for e in calculation_log.label_metadata
            ],
            label_values=label_values,
        )

    @staticmethod
    def map_to_response(calculation_log: CalculationLog) -> CalculationLogResponse:

        # Generate variable data
        variable_metadata = [
            PublicVariableMetadata(variable_id=e.variable_id, name=e.name, description=e.description)
            for e in calculation_log.variable_metadata
        ]

        variable_ids: list[int] = []
        variable_site_ids: list[Optional[int]] = []
        variable_interval_periods: list[int] = []
        variable_values: list[float] = []
        for variable_val in calculation_log.variable_values:
            variable_ids.append(variable_val.variable_id)
            variable_site_ids.append(None if variable_val.site_id_snapshot == 0 else variable_val.site_id_snapshot)
            variable_interval_periods.append(variable_val.interval_period)
            variable_values.append(variable_val.value)

        if len(variable_ids) == 0:
            variable_values_flat = None
        else:
            variable_values_flat = PublicVariableValues(
                variable_ids=variable_ids,
                site_ids=variable_site_ids,
                interval_periods=variable_interval_periods,
                values=variable_values,
            )

        # generate label data
        label_metadata = [
            PublicLabelMetadata(label_id=e.label_id, name=e.name, description=e.description)
            for e in calculation_log.label_metadata
        ]

        label_ids: list[int] = []
        label_site_ids: list[Optional[int]] = []
        label_values: list[str] = []
        for label_val in calculation_log.label_values:
            label_ids.append(label_val.label_id)
            label_site_ids.append(None if label_val.site_id_snapshot == 0 else label_val.site_id_snapshot)
            label_values.append(label_val.label)

        if len(label_ids) == 0:
            label_values_flat = None
        else:
            label_values_flat = PublicLabelValues(label_ids=label_ids, site_ids=label_site_ids, values=label_values)

        return CalculationLogResponse(
            calculation_log_id=calculation_log.calculation_log_id,
            created_time=calculation_log.created_time,
            calculation_range_start=calculation_log.calculation_range_start,
            calculation_range_duration_seconds=calculation_log.calculation_range_duration_seconds,
            interval_width_seconds=calculation_log.interval_width_seconds,
            topology_id=calculation_log.topology_id,
            external_id=calculation_log.external_id,
            description=calculation_log.description,
            power_forecast_creation_time=calculation_log.power_forecast_creation_time,
            power_forecast_basis_time=calculation_log.power_forecast_basis_time,
            weather_forecast_creation_time=calculation_log.weather_forecast_creation_time,
            weather_forecast_location_id=calculation_log.weather_forecast_location_id,
            variable_metadata=variable_metadata,
            variable_values=variable_values_flat,
            label_metadata=label_metadata,
            label_values=label_values_flat,
        )

    @staticmethod
    def map_to_list_response(
        calculation_logs: Sequence[CalculationLog], count: int, start: int, limit: int
    ) -> CalculationLogListResponse:
        return CalculationLogListResponse(
            limit=limit,
            start=start,
            total_calculation_logs=count,
            calculation_logs=[CalculationLogMapper.map_to_response(c) for c in calculation_logs],
        )
