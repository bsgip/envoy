-- Expands the base_config to include more "billing" specific data (i.e. more real readings, does and tariff rates)
-- Everything is injected into 2022-09-10 and 2022-09-11 AEST (aligned on 5 min boundaries with a midnight value)

INSERT INTO public.tariff_generated_rate("tariff_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (1, 1, '2023-09-01 11:22:33', '2023-09-10 00:00+10', 300, 1.1, -1.2, 1.3, -1.4);
INSERT INTO public.tariff_generated_rate("tariff_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (1, 1, '2023-09-01 11:22:33', '2023-09-10 00:05+10', 300, 2.1, -2.2, 2.3, -2.4);
INSERT INTO public.tariff_generated_rate("tariff_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (1, 1, '2023-09-01 11:22:33', '2023-09-10 00:10+10', 300, 3.1, -3.2, 3.3, -3.4);
INSERT INTO public.tariff_generated_rate("tariff_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (1, 1, '2023-09-01 11:22:33', '2023-09-11 00:00+10', 300, 4.1, -4.2, 4.3, -4.4);
INSERT INTO public.tariff_generated_rate("tariff_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (1, 1, '2023-09-01 11:22:33', '2023-09-11 00:05+10', 300, 5.1, -5.2, 5.3, -5.4);
INSERT INTO public.tariff_generated_rate("tariff_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (1, 2, '2023-09-01 11:22:33', '2023-09-10 00:00+10', 300, 6.1, -6.2, 6.3, -6.4);
INSERT INTO public.tariff_generated_rate("tariff_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (1, 3, '2023-09-01 11:22:33', '2023-09-10 00:00+10', 300, 7.1, -7.2, 7.3, -7.4);


INSERT INTO public.dynamic_operating_envelope("site_id", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (1, '2022-05-06 11:22:33', '2023-09-10 00:00+10', 300, 1.11, -1.22);
INSERT INTO public.dynamic_operating_envelope("site_id", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (1, '2022-05-06 11:22:33', '2023-09-10 00:05+10', 300, 2.11, -2.22);
INSERT INTO public.dynamic_operating_envelope("site_id", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (1, '2022-05-06 11:22:33', '2023-09-11 00:00+10', 300, 3.11, -3.22);
INSERT INTO public.dynamic_operating_envelope("site_id", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (1, '2022-05-06 11:22:33', '2023-09-11 00:05+10', 300, 4.11, -4.22);
INSERT INTO public.dynamic_operating_envelope("site_id", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (2, '2022-05-06 11:22:33', '2023-09-10 00:00+10', 300, 5.11, -5.22);
INSERT INTO public.dynamic_operating_envelope("site_id", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (3, '2022-05-06 11:22:33', '2023-09-10 00:00+10', 300, 6.11, -6.22);


SELECT pg_catalog.setval('public.dynamic_operating_envelope_dynamic_operating_envelope_id_seq', 5, true);

-- Real Energy - site 1
INSERT INTO public.site_reading_type("site_reading_type_id", "aggregator_id", "site_id", "uom", "data_qualifier", "flow_direction", "accumulation_behaviour", "kind", "phase", "power_of_ten_multiplier", "default_interval_seconds", "changed_time")
VALUES (1006, -- site_reading_type_id
    1, -- aggregator_id
    1, -- site_id
    72, -- uom
    2, -- data_qualifier
    1, -- flow_direction
    3, -- accumulation_behaviour
    37, -- kind
    64, -- phase
    1, -- power_of_ten_multiplier
    0, -- default_interval_seconds
    '2022-05-06 11:22:33' -- changed_time
    );

-- Reactive Energy - site 1
INSERT INTO public.site_reading_type("site_reading_type_id", "aggregator_id", "site_id", "uom", "data_qualifier", "flow_direction", "accumulation_behaviour", "kind", "phase", "power_of_ten_multiplier", "default_interval_seconds", "changed_time")
VALUES (1007, -- site_reading_type_id
    1, -- aggregator_id
    1, -- site_id
    73, -- uom
    2, -- data_qualifier
    1, -- flow_direction
    3, -- accumulation_behaviour
    37, -- kind
    64, -- phase
    1, -- power_of_ten_multiplier
    0, -- default_interval_seconds
    '2022-05-06 11:22:33' -- changed_time
    );

-- Real Watt Power - site 1
INSERT INTO public.site_reading_type("site_reading_type_id", "aggregator_id", "site_id", "uom", "data_qualifier", "flow_direction", "accumulation_behaviour", "kind", "phase", "power_of_ten_multiplier", "default_interval_seconds", "changed_time")
VALUES (1008, -- site_reading_type_id
    1, -- aggregator_id
    1, -- site_id
    38, -- uom
    2, -- data_qualifier
    1, -- flow_direction
    3, -- accumulation_behaviour
    37, -- kind
    64, -- phase
    1, -- power_of_ten_multiplier
    0, -- default_interval_seconds
    '2022-05-06 11:22:33.500' -- changed_time
    );

-- Real Energy - site 2
INSERT INTO public.site_reading_type("site_reading_type_id", "aggregator_id", "site_id", "uom", "data_qualifier", "flow_direction", "accumulation_behaviour", "kind", "phase", "power_of_ten_multiplier", "default_interval_seconds", "changed_time")
VALUES (1009, -- site_reading_type_id
    1, -- aggregator_id
    2, -- site_id
    72, -- uom
    2, -- data_qualifier
    1, -- flow_direction
    3, -- accumulation_behaviour
    37, -- kind
    64, -- phase
    1, -- power_of_ten_multiplier
    0, -- default_interval_seconds
    '2022-05-06 11:22:33' -- changed_time
    );

-- Real Energy - site 3
INSERT INTO public.site_reading_type("site_reading_type_id", "aggregator_id", "site_id", "uom", "data_qualifier", "flow_direction", "accumulation_behaviour", "kind", "phase", "power_of_ten_multiplier", "default_interval_seconds", "changed_time")
VALUES (1010, -- site_reading_type_id
    2, -- aggregator_id
    3, -- site_id
    72, -- uom
    2, -- data_qualifier
    1, -- flow_direction
    3, -- accumulation_behaviour
    37, -- kind
    64, -- phase
    1, -- power_of_ten_multiplier
    0, -- default_interval_seconds
    '2022-05-06 11:22:33' -- changed_time
    );


SELECT pg_catalog.setval('public.site_reading_type_site_reading_type_id_seq', 1011, true);


INSERT INTO public.site_reading("site_reading_type_id", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1006, -- site_reading_type_id
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-10 00:00:00+10', -- time_period_start
    300, -- time_period_seconds
    11 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1006, -- site_reading_type_id
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-10 00:05:00+10', -- time_period_start
    300, -- time_period_seconds
    22 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1006, -- site_reading_type_id
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-11 00:00:00+10', -- time_period_start
    300, -- time_period_seconds
    33 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1006, -- site_reading_type_id
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-11 00:10:00+10', -- time_period_start
    300, -- time_period_seconds
    44 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1007, -- site_reading_type_id
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-10 00:00:00+10', -- time_period_start
    300, -- time_period_seconds
    55 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1007, -- site_reading_type_id
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-11 00:00:00+10', -- time_period_start
    300, -- time_period_seconds
    66 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1008, -- site_reading_type_id 
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-10 00:00:00+10', -- time_period_start
    300, -- time_period_seconds
    99 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1008, -- site_reading_type_id 
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-10 00:05:00+10', -- time_period_start
    300, -- time_period_seconds
    1010 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1008, -- site_reading_type_id 
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-11 00:00:00+10', -- time_period_start
    300, -- time_period_seconds
    1111 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1009, -- site_reading_type_id
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-10 00:00:00+10', -- time_period_start
    300, -- time_period_seconds
    77 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1010, -- site_reading_type_id
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-10 00:00:00+10', -- time_period_start
    300, -- time_period_seconds
    88 -- value
    );


-- Calc log 4 will align with billing data and sites 1/3
INSERT INTO public.calculation_log("calculation_log_id", "created_time", "calculation_interval_start", "calculation_interval_duration_seconds", "topology_id", "external_id", "description", "power_forecast_creation_time", "weather_forecast_creation_time", "weather_forecast_location_id") 
VALUES (4, '2024-01-21 03:22:33.500', '2023-09-10 00:00+10', 86400, 'topo-id-4', 'external-id-4', 'description-4', '2024-01-20 03:11:00.500', '2024-03-20 01:11:11.500', 'weather-location-4');
-- Calc log 5 will align with billing data and have no sites
INSERT INTO public.calculation_log("calculation_log_id", "created_time", "calculation_interval_start", "calculation_interval_duration_seconds", "topology_id", "external_id", "description", "power_forecast_creation_time", "weather_forecast_creation_time", "weather_forecast_location_id") 
VALUES (5, '2024-01-21 03:22:33.500', '2023-09-10 00:00+10', 86400, 'topo-id-5', 'external-id-5', 'description-5', '2024-01-20 03:11:00.500', '2024-03-20 01:11:11.500', 'weather-location-5');
-- Calc log 6 will align with the first 5 minutes of billing data and site 1
INSERT INTO public.calculation_log("calculation_log_id", "created_time", "calculation_interval_start", "calculation_interval_duration_seconds", "topology_id", "external_id", "description", "power_forecast_creation_time", "weather_forecast_creation_time", "weather_forecast_location_id") 
VALUES (6, '2024-01-21 03:22:33.500', '2023-09-10 00:00+10', 300, 'topo-id-6', 'external-id-6', 'description-6', '2024-01-20 03:11:00.500', '2024-03-20 01:11:11.500', 'weather-location-6');
-- Calc log 7 will NOT align on billing period and will have site 1
INSERT INTO public.calculation_log("calculation_log_id", "created_time", "calculation_interval_start", "calculation_interval_duration_seconds", "topology_id", "external_id", "description", "power_forecast_creation_time", "weather_forecast_creation_time", "weather_forecast_location_id") 
VALUES (7, '2024-01-21 03:22:33.500', '2023-09-09 00:00+10', 86400, 'topo-id-7', 'external-id-7', 'description-7', '2024-01-20 03:11:00.500', '2024-03-20 01:11:11.500', 'weather-location-7');
SELECT pg_catalog.setval('public.calculation_log_calculation_log_id_seq', 8, true);


INSERT INTO public.power_flow_log("power_flow_log_id", "interval_start", "interval_duration_seconds", "site_id", "solve_name", "pu_voltage_min", "pu_voltage_max", "pu_voltage", "thermal_max_percent", "calculation_log_id") 
VALUES (4, '2024-02-01 00:00:05', 115, 1, 'solve-1', 4.01, 4.02, 4.03, 4.04, 4);
INSERT INTO public.power_flow_log("power_flow_log_id", "interval_start", "interval_duration_seconds", "site_id", "solve_name", "pu_voltage_min", "pu_voltage_max", "pu_voltage", "thermal_max_percent", "calculation_log_id") 
VALUES (5, '2024-02-01 00:00:05', 116, NULL, 'solve-1', 5.01, 5.02, 5.03, 5.04, 4);
INSERT INTO public.power_flow_log("power_flow_log_id", "interval_start", "interval_duration_seconds", "site_id", "solve_name", "pu_voltage_min", "pu_voltage_max", "pu_voltage", "thermal_max_percent", "calculation_log_id") 
VALUES (6, '2024-02-01 00:00:05', 117, 1, 'solve-1', 6.01, 6.02, 6.03, 6.04, 7);
SELECT pg_catalog.setval('public.power_flow_log_power_flow_log_id_seq', 7, true);

INSERT INTO public.power_target_log("power_target_log_id", "interval_start", "interval_duration_seconds", "external_device_id", "site_id", "target_active_power_watts", "target_reactive_power_var", "calculation_log_id") 
VALUES (4, '2024-02-01 00:00:05', 117, 'device-id-4', 3, 41, 42, 4);
INSERT INTO public.power_target_log("power_target_log_id", "interval_start", "interval_duration_seconds", "external_device_id", "site_id", "target_active_power_watts", "target_reactive_power_var", "calculation_log_id") 
VALUES (5, '2024-02-01 00:00:05', 118, 'device-id-5', NULL, 51, 52, 4);
SELECT pg_catalog.setval('public.power_target_log_power_target_log_id_seq', 6, true);

INSERT INTO public.power_forecast_log("power_forecast_log_id", "interval_start", "interval_duration_seconds", "external_device_id", "site_id", "active_power_watts", "reactive_power_var", "calculation_log_id") 
VALUES (4, '2024-02-01 01:00:05', 118, 'device-id-4', 1, 411, 412, 6);
INSERT INTO public.power_forecast_log("power_forecast_log_id", "interval_start", "interval_duration_seconds", "external_device_id", "site_id", "active_power_watts", "reactive_power_var", "calculation_log_id") 
VALUES (5, '2024-02-01 01:00:05', 119, 'device-id-5', NULL, 511, 512, 4);
SELECT pg_catalog.setval('public.power_forecast_log_power_forecast_log_id_seq', 6, true);