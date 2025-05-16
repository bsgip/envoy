-- Expands the base_config to include more "billing" specific data (i.e. more real readings, does and tariff rates)
-- Everything is injected into 2022-09-10 and 2022-09-11 AEST (aligned on 5 min boundaries with a midnight value)



-- Calc log 4 will align with billing data and sites 1/3
INSERT INTO public.calculation_log("calculation_log_id", "created_time", "calculation_range_start", "calculation_range_duration_seconds", "interval_width_seconds", "topology_id", "external_id", "description", "power_forecast_creation_time", "power_forecast_basis_time", "weather_forecast_creation_time", "weather_forecast_location_id") 
VALUES (4, '2024-01-21 03:22:33.500', '2023-09-10 00:00+10', 86400, 300, 'topo-id-4', 'external-id-4', 'description-4', '2024-01-20 03:11:00.500', '2024-01-10 03:21:00.500', '2024-03-20 01:11:11.500', 'weather-location-4');
-- Calc log 5 will align with billing data and have no sites
INSERT INTO public.calculation_log("calculation_log_id", "created_time", "calculation_range_start", "calculation_range_duration_seconds", "interval_width_seconds", "topology_id", "external_id", "description", "power_forecast_creation_time", "power_forecast_basis_time", "weather_forecast_creation_time", "weather_forecast_location_id") 
VALUES (5, '2024-01-21 03:22:33.500', '2023-09-10 00:00+10', 86400, 300, 'topo-id-5', 'external-id-5', 'description-5', '2024-01-20 03:11:00.500', '2024-01-10 03:21:00.500', '2024-03-20 01:11:11.500', 'weather-location-5');
-- Calc log 6 will align with the first 5 minutes of billing data and site 1
INSERT INTO public.calculation_log("calculation_log_id", "created_time", "calculation_range_start", "calculation_range_duration_seconds", "interval_width_seconds", "topology_id", "external_id", "description", "power_forecast_creation_time", "power_forecast_basis_time", "weather_forecast_creation_time", "weather_forecast_location_id") 
VALUES (6, '2024-01-21 03:22:33.500', '2023-09-10 00:00+10', 300, 5, 'topo-id-6', 'external-id-6', 'description-6', '2024-01-20 03:11:00.500', '2024-01-10 03:21:00.500', '2024-03-20 01:11:11.500', 'weather-location-6');
-- Calc log 7 will NOT align on billing period and will have site 1
INSERT INTO public.calculation_log("calculation_log_id", "created_time", "calculation_range_start", "calculation_range_duration_seconds", "interval_width_seconds", "topology_id", "external_id", "description", "power_forecast_creation_time", "power_forecast_basis_time", "weather_forecast_creation_time", "weather_forecast_location_id") 
VALUES (7, '2024-01-21 03:22:33.500', '2023-09-09 00:00+10', 86400, 300, 'topo-id-7', 'external-id-7', 'description-7', '2024-01-20 03:11:00.500', '2024-01-10 03:21:00.500', '2024-03-20 01:11:11.500', 'weather-location-7');
SELECT pg_catalog.setval('public.calculation_log_calculation_log_id_seq', 8, true);


INSERT INTO public.calculation_log_variable_value("calculation_log_id", "variable_id", "site_id_snapshot", "interval_period", "value") VALUES (4, 1, 1, 0, 4.01);
INSERT INTO public.calculation_log_variable_value("calculation_log_id", "variable_id", "site_id_snapshot", "interval_period", "value") VALUES (4, 1, 1, 1, 5.01);
INSERT INTO public.calculation_log_variable_value("calculation_log_id", "variable_id", "site_id_snapshot", "interval_period", "value") VALUES (4, 2, 1, 0, 4.02);
INSERT INTO public.calculation_log_variable_value("calculation_log_id", "variable_id", "site_id_snapshot", "interval_period", "value") VALUES (4, 2, 1, 1, 5.02);
INSERT INTO public.calculation_log_variable_value("calculation_log_id", "variable_id", "site_id_snapshot", "interval_period", "value") VALUES (4, 3, 0, 0, 3.02);
INSERT INTO public.calculation_log_variable_value("calculation_log_id", "variable_id", "site_id_snapshot", "interval_period", "value") VALUES (4, 3, 0, 1, 3.02);

INSERT INTO public.calculation_log_variable_value("calculation_log_id", "variable_id", "site_id_snapshot", "interval_period", "value") VALUES (7, 1, 1, 0, 6.01);
INSERT INTO public.calculation_log_variable_value("calculation_log_id", "variable_id", "site_id_snapshot", "interval_period", "value") VALUES (7, 1, 1, 1, 6.01);
INSERT INTO public.calculation_log_variable_value("calculation_log_id", "variable_id", "site_id_snapshot", "interval_period", "value") VALUES (7, 2, 1, 0, 6.02);
INSERT INTO public.calculation_log_variable_value("calculation_log_id", "variable_id", "site_id_snapshot", "interval_period", "value") VALUES (7, 2, 1, 1, 6.02);




INSERT INTO public.tariff_generated_rate("tariff_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (1, 1, NULL, '2000-01-01 00:00:00Z', '2023-09-01 11:22:33', '2023-09-10 00:00+10', 300, 1.1, -1.2, 1.3, -1.4);
INSERT INTO public.tariff_generated_rate("tariff_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (1, 1, 4, '2000-01-01 00:00:00Z', '2023-09-01 11:22:33', '2023-09-10 00:05+10', 300, 2.1, -2.2, 2.3, -2.4);
INSERT INTO public.tariff_generated_rate("tariff_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (1, 1, 4, '2000-01-01 00:00:00Z', '2023-09-01 11:22:33', '2023-09-10 00:10+10', 300, 3.1, -3.2, 3.3, -3.4);
INSERT INTO public.tariff_generated_rate("tariff_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (1, 1, 5, '2000-01-01 00:00:00Z', '2023-09-01 11:22:33', '2023-09-11 00:00+10', 300, 4.1, -4.2, 4.3, -4.4);
INSERT INTO public.tariff_generated_rate("tariff_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (1, 1, 5, '2000-01-01 00:00:00Z', '2023-09-01 11:22:33', '2023-09-11 00:05+10', 300, 5.1, -5.2, 5.3, -5.4);
INSERT INTO public.tariff_generated_rate("tariff_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (1, 2, 5, '2000-01-01 00:00:00Z', '2023-09-01 11:22:33', '2023-09-10 00:00+10', 300, 6.1, -6.2, 6.3, -6.4);
INSERT INTO public.tariff_generated_rate("tariff_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (1, 3, 5, '2000-01-01 00:00:00Z', '2023-09-01 11:22:33', '2023-09-10 00:00+10', 300, 7.1, -7.2, 7.3, -7.4);


INSERT INTO public.dynamic_operating_envelope("site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (1, 1, NULL, '2000-01-01 00:00:00Z', '2022-05-06 11:22:33', '2023-09-10 00:00+10', 300, '2023-09-10 00:05+10', 1.11, -1.22);
INSERT INTO public.dynamic_operating_envelope("site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (1, 1, 4, '2000-01-01 00:00:00Z', '2022-05-06 11:22:33', '2023-09-10 00:05+10', 300, '2023-09-10 00:10+10', 2.11, -2.22);
INSERT INTO public.dynamic_operating_envelope("site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (1, 1, 5, '2000-01-01 00:00:00Z', '2022-05-06 11:22:33', '2023-09-11 00:00+10', 300, '2023-09-11 00:05+10', 3.11, -3.22);
INSERT INTO public.dynamic_operating_envelope("site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (1, 1, 6, '2000-01-01 00:00:00Z', '2022-05-06 11:22:33', '2023-09-11 00:05+10', 300, '2023-09-11 00:10+10', 4.11, -4.22);
INSERT INTO public.dynamic_operating_envelope("site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (1, 2, 5, '2000-01-01 00:00:00Z', '2022-05-06 11:22:33', '2023-09-10 00:00+10', 300, '2023-09-10 00:05+10', 5.11, -5.22);
INSERT INTO public.dynamic_operating_envelope("site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (1, 3, 5, '2000-01-01 00:00:00Z', '2022-05-06 11:22:33', '2023-09-10 00:00+10', 300, '2023-09-10 00:05+10', 6.11, -6.22);


-- Real Energy - site 1
INSERT INTO public.site_reading_type("site_reading_type_id", "aggregator_id", "site_id", "uom", "data_qualifier", "flow_direction", "accumulation_behaviour", "kind", "phase", "power_of_ten_multiplier", "default_interval_seconds", "created_time", "changed_time")
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
    '2000-01-01 00:00:00Z', -- created_time
    '2022-05-06 11:22:33' -- changed_time
    );

-- Reactive Energy - site 1
INSERT INTO public.site_reading_type("site_reading_type_id", "aggregator_id", "site_id", "uom", "data_qualifier", "flow_direction", "accumulation_behaviour", "kind", "phase", "power_of_ten_multiplier", "default_interval_seconds", "created_time", "changed_time")
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
    '2000-01-01 00:00:00Z', -- created_time
    '2022-05-06 11:22:33' -- changed_time
    );

-- Real Watt Power - site 1
INSERT INTO public.site_reading_type("site_reading_type_id", "aggregator_id", "site_id", "uom", "data_qualifier", "flow_direction", "accumulation_behaviour", "kind", "phase", "power_of_ten_multiplier", "default_interval_seconds", "created_time", "changed_time")
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
    '2000-01-01 00:00:00Z', -- created_time
    '2022-05-06 11:22:33.500' -- changed_time
    );

-- Real Energy - site 2
INSERT INTO public.site_reading_type("site_reading_type_id", "aggregator_id", "site_id", "uom", "data_qualifier", "flow_direction", "accumulation_behaviour", "kind", "phase", "power_of_ten_multiplier", "default_interval_seconds", "created_time", "changed_time")
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
    '2000-01-01 00:00:00Z', -- created_time
    '2022-05-06 11:22:33' -- changed_time
    );

-- Real Energy - site 3
INSERT INTO public.site_reading_type("site_reading_type_id", "aggregator_id", "site_id", "uom", "data_qualifier", "flow_direction", "accumulation_behaviour", "kind", "phase", "power_of_ten_multiplier", "default_interval_seconds", "created_time", "changed_time")
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
    '2000-01-01 00:00:00Z', -- created_time
    '2022-05-06 11:22:33' -- changed_time
    );


SELECT pg_catalog.setval('public.site_reading_type_site_reading_type_id_seq', 1011, true);


INSERT INTO public.site_reading("site_reading_type_id", "created_time", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1006, -- site_reading_type_id
    '2000-01-01 00:00:00Z', -- created_time
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-10 00:00:00+10', -- time_period_start
    300, -- time_period_seconds
    11 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "created_time", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1006, -- site_reading_type_id
    '2000-01-01 00:00:00Z', -- created_time
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-10 00:05:00+10', -- time_period_start
    300, -- time_period_seconds
    22 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "created_time", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1006, -- site_reading_type_id
    '2000-01-01 00:00:00Z', -- created_time
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-11 00:00:00+10', -- time_period_start
    300, -- time_period_seconds
    33 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "created_time", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1006, -- site_reading_type_id
    '2000-01-01 00:00:00Z', -- created_time
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-11 00:10:00+10', -- time_period_start
    300, -- time_period_seconds
    44 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "created_time", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1007, -- site_reading_type_id
    '2000-01-01 00:00:00Z', -- created_time
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-10 00:00:00+10', -- time_period_start
    300, -- time_period_seconds
    55 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "created_time", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1007, -- site_reading_type_id
    '2000-01-01 00:00:00Z', -- created_time
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-11 00:00:00+10', -- time_period_start
    300, -- time_period_seconds
    66 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "created_time", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1008, -- site_reading_type_id 
    '2000-01-01 00:00:00Z', -- created_time
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-10 00:00:00+10', -- time_period_start
    300, -- time_period_seconds
    99 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "created_time", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1008, -- site_reading_type_id 
    '2000-01-01 00:00:00Z', -- created_time
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-10 00:05:00+10', -- time_period_start
    300, -- time_period_seconds
    1010 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "created_time", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1008, -- site_reading_type_id 
    '2000-01-01 00:00:00Z', -- created_time
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-11 00:00:00+10', -- time_period_start
    300, -- time_period_seconds
    1111 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "created_time", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1009, -- site_reading_type_id
    '2000-01-01 00:00:00Z', -- created_time
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-10 00:00:00+10', -- time_period_start
    300, -- time_period_seconds
    77 -- value
    );
INSERT INTO public.site_reading("site_reading_type_id", "created_time", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (
    1010, -- site_reading_type_id
    '2000-01-01 00:00:00Z', -- created_time
    '2022-06-07 11:22:33', -- changed_time
    1, -- local_id
    1, -- quality_flags
    '2023-09-10 00:00:00+10', -- time_period_start
    300, -- time_period_seconds
    88 -- value
    );

