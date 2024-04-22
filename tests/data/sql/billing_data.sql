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

-- Reactive Energy - site 3
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