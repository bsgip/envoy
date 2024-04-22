from datetime import datetime

from envoy_schema.admin.schema.log import CalculationLogRequest, CalculationLogResponse
from envoy_schema.admin.schema.log import PowerFlowLog as PublicPowerFlowLog
from envoy_schema.admin.schema.log import PowerForecastLog as PublicPowerForecastLog
from envoy_schema.admin.schema.log import PowerTargetLog as PublicPowerTargetLog
from envoy_schema.admin.schema.log import WeatherForecastLog as PublicWeatherForecastLog

from envoy.server.model.log import CalculationLog, PowerFlowLog, PowerForecastLog, PowerTargetLog, WeatherForecastLog


class CalculationLogMapper:

    @staticmethod
    def map_from_request(changed_time: datetime, calculation_log: CalculationLogRequest) -> CalculationLog:
        return CalculationLog(
            created_time=changed_time,
            calculation_interval_start=calculation_log.calculation_interval_start,
            calculation_interval_duration_seconds=calculation_log.calculation_interval_duration_seconds,
            topology_id=calculation_log.topology_id,
            external_id=calculation_log.external_id,
            description=calculation_log.description,
            power_forecast_creation_time=calculation_log.power_forecast_creation_time,
            weather_forecast_creation_time=calculation_log.weather_forecast_creation_time,
            weather_forecast_location_id=calculation_log.weather_forecast_location_id,
            power_forecast_logs=[
                PowerForecastLog(
                    interval_start=e.interval_start,
                    interval_duration_seconds=e.interval_duration_seconds,
                    external_device_id=e.external_device_id,
                    site_id=e.site_id,
                    active_power_watts=e.active_power_watts,
                    reactive_power_var=e.reactive_power_var,
                )
                for e in calculation_log.power_forecast_logs
            ],
            power_target_logs=[
                PowerTargetLog(
                    interval_start=e.interval_start,
                    interval_duration_seconds=e.interval_duration_seconds,
                    external_device_id=e.external_device_id,
                    site_id=e.site_id,
                    target_active_power_watts=e.target_active_power_watts,
                    target_reactive_power_var=e.target_reactive_power_var,
                )
                for e in calculation_log.power_target_logs
            ],
            power_flow_logs=[
                PowerFlowLog(
                    interval_start=e.interval_start,
                    interval_duration_seconds=e.interval_duration_seconds,
                    external_device_id=e.external_device_id,
                    site_id=e.site_id,
                    solve_name=e.solve_name,
                    pu_voltage_min=e.pu_voltage_min,
                    pu_voltage_max=e.pu_voltage_max,
                    pu_voltage=e.pu_voltage,
                    thermal_max_percent=e.thermal_max_percent,
                )
                for e in calculation_log.power_flow_logs
            ],
            weather_forecast_logs=[
                WeatherForecastLog(
                    interval_start=e.interval_start,
                    interval_duration_seconds=e.interval_duration_seconds,
                    air_temperature_degrees_c=e.air_temperature_degrees_c,
                    apparent_temperature_degrees_c=e.apparent_temperature_degrees_c,
                    dew_point_degrees_c=e.dew_point_degrees_c,
                    humidity_percent=e.humidity_percent,
                    cloud_cover_percent=e.cloud_cover_percent,
                    rain_probability_percent=e.rain_probability_percent,
                    rain_mm=e.rain_mm,
                    rain_rate_mm=e.rain_rate_mm,
                    global_horizontal_irradiance_watts_m2=e.global_horizontal_irradiance_watts_m2,
                    wind_speed_50m_km_h=e.wind_speed_50m_km_h,
                )
                for e in calculation_log.weather_forecast_logs
            ],
        )

    @staticmethod
    def map_to_response(calculation_log: CalculationLog) -> CalculationLogResponse:
        return CalculationLogResponse(
            calculation_log_id=calculation_log.calculation_log_id,
            created_time=calculation_log.created_time,
            calculation_interval_start=calculation_log.calculation_interval_start,
            calculation_interval_duration_seconds=calculation_log.calculation_interval_duration_seconds,
            topology_id=calculation_log.topology_id,
            external_id=calculation_log.external_id,
            description=calculation_log.description,
            power_forecast_creation_time=calculation_log.power_forecast_creation_time,
            weather_forecast_creation_time=calculation_log.weather_forecast_creation_time,
            weather_forecast_location_id=calculation_log.weather_forecast_location_id,
            power_forecast_logs=[
                PublicPowerForecastLog(
                    interval_start=e.interval_start,
                    interval_duration_seconds=e.interval_duration_seconds,
                    external_device_id=e.external_device_id,
                    site_id=e.site_id,
                    active_power_watts=e.active_power_watts,
                    reactive_power_var=e.reactive_power_var,
                )
                for e in calculation_log.power_forecast_logs
            ],
            power_target_logs=[
                PublicPowerTargetLog(
                    interval_start=e.interval_start,
                    interval_duration_seconds=e.interval_duration_seconds,
                    external_device_id=e.external_device_id,
                    site_id=e.site_id,
                    target_active_power_watts=e.target_active_power_watts,
                    target_reactive_power_var=e.target_reactive_power_var,
                )
                for e in calculation_log.power_target_logs
            ],
            power_flow_logs=[
                PublicPowerFlowLog(
                    interval_start=e.interval_start,
                    interval_duration_seconds=e.interval_duration_seconds,
                    external_device_id=e.external_device_id,
                    site_id=e.site_id,
                    solve_name=e.solve_name,
                    pu_voltage_min=e.pu_voltage_min,
                    pu_voltage_max=e.pu_voltage_max,
                    pu_voltage=e.pu_voltage,
                    thermal_max_percent=e.thermal_max_percent,
                )
                for e in calculation_log.power_flow_logs
            ],
            weather_forecast_logs=[
                PublicWeatherForecastLog(
                    interval_start=e.interval_start,
                    interval_duration_seconds=e.interval_duration_seconds,
                    air_temperature_degrees_c=e.air_temperature_degrees_c,
                    apparent_temperature_degrees_c=e.apparent_temperature_degrees_c,
                    dew_point_degrees_c=e.dew_point_degrees_c,
                    humidity_percent=e.humidity_percent,
                    cloud_cover_percent=e.cloud_cover_percent,
                    rain_probability_percent=e.rain_probability_percent,
                    rain_mm=e.rain_mm,
                    rain_rate_mm=e.rain_rate_mm,
                    global_horizontal_irradiance_watts_m2=e.global_horizontal_irradiance_watts_m2,
                    wind_speed_50m_km_h=e.wind_speed_50m_km_h,
                )
                for e in calculation_log.weather_forecast_logs
            ],
        )
