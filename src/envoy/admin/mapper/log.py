from datetime import datetime
from typing import Optional, Sequence

from envoy_schema.admin.schema.log import CalculationLogListResponse
from envoy_schema.admin.schema.log import CalculationLogMetadata as PublicVariableMetadata
from envoy_schema.admin.schema.log import CalculationLogRequest, CalculationLogResponse
from envoy_schema.admin.schema.log import CalculationLogVariableValues as PublicVariableValues

from envoy.server.model.log import CalculationLog, CalculationLogVariableMetadata, CalculationLogVariableValue


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
        )

    @staticmethod
    def map_to_response(calculation_log: CalculationLog, include_child_logs: bool = True) -> CalculationLogResponse:

        if include_child_logs:
            variable_metadata = [
                PublicVariableMetadata(variable_id=e.variable_id, name=e.name, description=e.description)
                for e in calculation_log.variable_metadata
            ]

            variable_ids: list[int] = []
            site_ids: list[Optional[int]] = []
            interval_periods: list[int] = []
            values: list[float] = []
            for e in calculation_log.variable_values:
                variable_ids.append(e.variable_id)
                site_ids.append(None if e.site_id_snapshot == 0 else e.site_id_snapshot)
                interval_periods.append(e.interval_period)
                values.append(e.value)

            variable_values = PublicVariableValues(
                variable_ids=variable_ids, site_ids=site_ids, interval_periods=interval_periods, values=values
            )
        else:
            variable_metadata = []
            variable_values = None

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
            variable_values=variable_values,
        )

    @staticmethod
    def map_to_list_response(
        calculation_logs: Sequence[CalculationLog], count: int, start: int, limit: int
    ) -> CalculationLogListResponse:
        return CalculationLogListResponse(
            limit=limit,
            start=start,
            total_calculation_logs=count,
            calculation_logs=[
                CalculationLogMapper.map_to_response(c, include_child_logs=False) for c in calculation_logs
            ],
        )
