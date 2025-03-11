-- "reference" dataset that all database specific tests will build upon
-- designed to be the "minimum useful configuration" that most tests will utilise

SET row_security = off;
SET timezone = 'UTC';

INSERT INTO public.aggregator("aggregator_id", "name", "created_time", "changed_time" ) VALUES (0, 'NULL AGGREGATOR', '2000-01-01 00:00:00Z', '2022-01-02 01:02:03.500'); -- This is supposed to be ID 0
INSERT INTO public.aggregator("aggregator_id", "name", "created_time", "changed_time") VALUES (1, 'Aggregator 1', '2000-01-01 00:00:00Z', '2022-01-03 01:02:03.500');
INSERT INTO public.aggregator("aggregator_id", "name", "created_time", "changed_time") VALUES (2, 'Aggregator 2', '2000-01-01 00:00:00Z', '2022-01-04 01:02:03.500');
INSERT INTO public.aggregator("aggregator_id", "name", "created_time", "changed_time") VALUES (3, 'Aggregator 3', '2000-01-01 00:00:00Z', '2022-01-05 01:02:03.500');

SELECT pg_catalog.setval('public.aggregator_aggregator_id_seq', 4, true);

INSERT INTO public.aggregator_domain("aggregator_domain_id", "aggregator_id", "created_time", "changed_time", "domain") VALUES (1, 1, '2000-01-01 00:00:00Z', '2023-01-02 01:02:03.500', 'example.com');
INSERT INTO public.aggregator_domain("aggregator_domain_id", "aggregator_id", "created_time", "changed_time", "domain") VALUES (2, 2, '2000-01-01 00:00:00Z', '2023-01-02 02:02:03.500', 'example.com');
INSERT INTO public.aggregator_domain("aggregator_domain_id", "aggregator_id", "created_time", "changed_time", "domain") VALUES (3, 3, '2000-01-01 00:00:00Z', '2023-01-02 03:02:03.500', 'example.com');
INSERT INTO public.aggregator_domain("aggregator_domain_id", "aggregator_id", "created_time", "changed_time", "domain") VALUES (4, 1, '2000-01-01 00:00:00Z', '2023-01-02 04:02:03.500', 'another.example.com');

SELECT pg_catalog.setval('public.aggregator_domain_aggregator_domain_id_seq', 5, true);

-- See tests/data/certificates for how these were generated
INSERT INTO public.certificate("certificate_id", "created", "lfdi", "expiry") VALUES (1, '2023-01-01 01:02:03.500', '854d10a201ca99e5e90d3c3e1f9bc1c3bd075f3b', '2037-01-01 01:02:03'); -- certificate 1
INSERT INTO public.certificate("certificate_id", "created", "lfdi", "expiry") VALUES (2, '2023-01-01 02:03:04.500', '403ba02aa36fa072c47eb3299daaafe94399adad', '2037-01-01 02:03:04'); -- certificate 2
INSERT INTO public.certificate("certificate_id", "created", "lfdi", "expiry") VALUES (3, '2023-01-01 01:02:03.500', 'c9ed55b4b4f8647916bfb7f426792e015ffc2441', '2023-01-01 01:02:04'); -- expired certificate 3
INSERT INTO public.certificate("certificate_id", "created", "lfdi", "expiry") VALUES (4, '2023-01-01 01:02:03.500', '8ad1d4ce1d3b353ebee21230a89e4172b18f520e', '2037-01-01 01:02:03'); -- certificate 4
INSERT INTO public.certificate("certificate_id", "created", "lfdi", "expiry") VALUES (5, '2023-01-01 01:02:03.500', 'ec08e4c9d68a0669c3673708186fde317f7c67a2', '2037-01-01 01:02:03'); -- certificate 5

SELECT pg_catalog.setval('public.certificate_certificate_id_seq', 6, true);

INSERT INTO public.aggregator_certificate_assignment("assignment_id", "certificate_id", "aggregator_id") VALUES (1, 1, 1);
INSERT INTO public.aggregator_certificate_assignment("assignment_id", "certificate_id", "aggregator_id") VALUES (2, 2, 1);
INSERT INTO public.aggregator_certificate_assignment("assignment_id", "certificate_id", "aggregator_id") VALUES (3, 3, 1);
INSERT INTO public.aggregator_certificate_assignment("assignment_id", "certificate_id", "aggregator_id") VALUES (4, 4, 2);
INSERT INTO public.aggregator_certificate_assignment("assignment_id", "certificate_id", "aggregator_id") VALUES (5, 5, 3);

SELECT pg_catalog.setval('public.aggregator_certificate_assignment_assignment_id_seq', 6, true);

INSERT INTO public.site("site_id", "nmi", "aggregator_id", "timezone_id", "created_time", "changed_time", "lfdi", "sfdi", "device_category", "registration_pin") VALUES (1, '1111111111', 1, 'Australia/Brisbane', '2000-01-01 00:00:00Z', '2022-02-03 04:05:06.500', 'site1-lfdi', 1111, 0, 11111);
INSERT INTO public.site("site_id", "nmi", "aggregator_id", "timezone_id", "created_time", "changed_time", "lfdi", "sfdi", "device_category", "registration_pin") VALUES (2, '2222222222', 1, 'Australia/Brisbane', '2000-01-01 00:00:00Z', '2022-02-03 05:06:07.500', 'site2-lfdi', 2222, 1, 22222);
INSERT INTO public.site("site_id", "nmi", "aggregator_id", "timezone_id", "created_time", "changed_time", "lfdi", "sfdi", "device_category", "registration_pin") VALUES (3, '3333333333', 2, 'Australia/Brisbane', '2000-01-01 00:00:00Z', '2022-02-03 08:09:10.500', 'site3-lfdi', 3333, 2, 33333);
INSERT INTO public.site("site_id", "nmi", "aggregator_id", "timezone_id", "created_time", "changed_time", "lfdi", "sfdi", "device_category", "registration_pin") VALUES (4, '4444444444', 1, 'Australia/Brisbane', '2000-01-01 00:00:00Z', '2022-02-03 11:12:13.500', 'site4-lfdi', 4444, 3, 44444);
-- Device registered site - using cert from certificate6.py
INSERT INTO public.site("site_id", "nmi", "aggregator_id", "timezone_id", "created_time", "changed_time", "lfdi", "sfdi", "device_category", "registration_pin") VALUES (5, '5555555555', 0, 'Australia/Brisbane', '2000-01-01 00:00:00Z', '2022-02-03 14:15:16.500', 'ec80646c5131ffa8ade49ac24be5295a7cfeb69d', 634853966776, 4, 55555); 
-- Device registered site - using cert from certificate7.py
INSERT INTO public.site("site_id", "nmi", "aggregator_id", "timezone_id", "created_time", "changed_time", "lfdi", "sfdi", "device_category", "registration_pin") VALUES (6, '6666666666', 0, 'Australia/Brisbane', '2000-01-01 00:00:00Z', '2022-02-03 17:18:19.500', '93a527c16d8fca36e0f7da189fde375d5e494717', 396331899108, 5, 66666); 

SELECT pg_catalog.setval('public.site_site_id_seq', 7, true);


-- Calculation log 1/2 have the same interval but calculation log 2 has a more recent created time
-- Only calculation log 2 will have child entities
INSERT INTO public.calculation_log("calculation_log_id", "created_time", "calculation_range_start", "calculation_range_duration_seconds", "interval_width_seconds", "topology_id", "external_id", "description", "power_forecast_creation_time", "power_forecast_basis_time", "weather_forecast_creation_time", "weather_forecast_location_id") 
VALUES (1, '2024-01-21 01:22:33.500', '2024-01-31 01:02:03', 86401, 301, 'topo-id-1', 'external-id-1', 'description-1', '2024-01-20 01:11:00.500', '2024-01-19 01:22:00.500', '2024-01-20 01:11:11.500', 'weather-location-1');
INSERT INTO public.calculation_log("calculation_log_id", "created_time", "calculation_range_start", "calculation_range_duration_seconds", "interval_width_seconds", "topology_id", "external_id", "description", "power_forecast_creation_time", "power_forecast_basis_time", "weather_forecast_creation_time", "weather_forecast_location_id") 
VALUES (2, '2024-01-21 02:22:33.500', '2024-01-31 01:02:03', 86402, 302, 'topo-id-2', 'external-id-2', 'description-2', '2024-01-20 02:11:00.500', '2024-01-19 02:22:00.500', '2024-02-20 01:11:11.500', 'weather-location-2');
INSERT INTO public.calculation_log("calculation_log_id", "created_time", "calculation_range_start", "calculation_range_duration_seconds", "interval_width_seconds", "topology_id", "external_id", "description", "power_forecast_creation_time", "power_forecast_basis_time", "weather_forecast_creation_time", "weather_forecast_location_id") 
VALUES (3, '2024-01-21 03:22:33.500', '2024-01-31 02:02:03', 86403, 303, 'topo-id-3', 'external-id-3', 'description-3', '2024-01-20 03:11:00.500', '2024-01-19 03:22:00.500', '2024-03-20 01:11:11.500', 'weather-location-3');
SELECT pg_catalog.setval('public.calculation_log_calculation_log_id_seq', 4, true);

INSERT INTO public.calculation_log_variable_metadata("calculation_log_id", "variable_id", "name", "description") VALUES (2, 1, 'Var-1', 'Var-1-Desc');
INSERT INTO public.calculation_log_variable_metadata("calculation_log_id", "variable_id", "name", "description") VALUES (2, 2, 'Var-2', 'Var-2-Desc');
INSERT INTO public.calculation_log_variable_metadata("calculation_log_id", "variable_id", "name", "description") VALUES (2, 3, 'Var-3', 'Var-3-Desc');

INSERT INTO public.calculation_log_variable_value("calculation_log_id", "variable_id", "site_id_snapshot", "interval_period", "value") VALUES (2, 3, 1, 0, 0);
INSERT INTO public.calculation_log_variable_value("calculation_log_id", "variable_id", "site_id_snapshot", "interval_period", "value") VALUES (2, 3, 1, 1, 1.1);
INSERT INTO public.calculation_log_variable_value("calculation_log_id", "variable_id", "site_id_snapshot", "interval_period", "value") VALUES (2, 1, 0, 1, 2.2);
INSERT INTO public.calculation_log_variable_value("calculation_log_id", "variable_id", "site_id_snapshot", "interval_period", "value") VALUES (2, 1, 0, 0, 3.3);
INSERT INTO public.calculation_log_variable_value("calculation_log_id", "variable_id", "site_id_snapshot", "interval_period", "value") VALUES (2, 1, 0, 2, 4.4);
INSERT INTO public.calculation_log_variable_value("calculation_log_id", "variable_id", "site_id_snapshot", "interval_period", "value") VALUES (2, 2, 2, 0, -5.5);

INSERT INTO public.calculation_log_label_metadata("calculation_log_id", "label_id", "name", "description") VALUES (2, 2, 'Label-2', 'Label-2-Desc');
INSERT INTO public.calculation_log_label_metadata("calculation_log_id", "label_id", "name", "description") VALUES (2, 3, 'Label-3', 'Label-3-Desc');

INSERT INTO public.calculation_log_label_value("calculation_log_id", "label_id", "site_id_snapshot", "label") VALUES (2, 3, 0, 'label-2-3-0');
INSERT INTO public.calculation_log_label_value("calculation_log_id", "label_id", "site_id_snapshot", "label") VALUES (2, 3, 1, 'label-2-3-1');
INSERT INTO public.calculation_log_label_value("calculation_log_id", "label_id", "site_id_snapshot", "label") VALUES (2, 1, 2, 'label-2-1-2');



INSERT INTO public.tariff("tariff_id", "name", "dnsp_code", "currency_code", "created_time", "changed_time") VALUES (1, 'tariff-1', 'tariff-dnsp-code-1', 36, '2000-01-01 00:00:00Z', '2023-01-02 11:01:02');
INSERT INTO public.tariff("tariff_id", "name", "dnsp_code", "currency_code", "created_time", "changed_time") VALUES (2, 'tariff-2', 'tariff-dnsp-code-2', 124, '2000-01-01 00:00:00Z', '2023-01-02 12:01:02');
INSERT INTO public.tariff("tariff_id", "name", "dnsp_code", "currency_code", "created_time", "changed_time") VALUES (3, 'tariff-3', 'tariff-dnsp-code-3', 840, '2000-01-01 00:00:00Z', '2023-01-02 13:01:02');

SELECT pg_catalog.setval('public.tariff_tariff_id_seq', 4, true);

INSERT INTO public.tariff_generated_rate("tariff_generated_rate_id", "tariff_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (1, 1, 1, 2, '2000-01-01 00:00:00Z', '2022-03-04 11:22:33.500', '2022-03-05 01:02+10', 11, 1.1, -1.22, 1.333, -1.4444);
INSERT INTO public.tariff_generated_rate("tariff_generated_rate_id", "tariff_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (2, 1, 1, 2, '2000-01-01 00:00:00Z', '2022-03-04 12:22:33.500', '2022-03-05 03:04+10', 12, 2.1, -2.22, 2.333, -2.4444);
INSERT INTO public.tariff_generated_rate("tariff_generated_rate_id", "tariff_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (3, 1, 2, 2, '2000-01-01 00:00:00Z', '2022-03-04 13:22:33.500', '2022-03-05 01:02+10', 13, 3.1, -3.22, 3.333, -3.4444);
INSERT INTO public.tariff_generated_rate("tariff_generated_rate_id", "tariff_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (4, 1, 1, NULL, '2000-01-01 00:00:00Z', '2022-03-04 14:22:33.500', '2022-03-06 01:02+10', 14, 4.1, -4.22, 4.333, -4.4444);

SELECT pg_catalog.setval('public.tariff_generated_rate_tariff_generated_rate_id_seq', 5, true);


INSERT INTO public.tariff_generated_rate_response("tariff_generated_rate_response_id", "tariff_generated_rate_id", "site_id", "created_time", "response_type", "pricing_reading_type") VALUES (1, 1, 1, '2022-01-01 00:00:00+10', 1, 1);
INSERT INTO public.tariff_generated_rate_response("tariff_generated_rate_response_id", "tariff_generated_rate_id", "site_id", "created_time", "response_type", "pricing_reading_type") VALUES (2, 1, 1, '2022-01-02 00:00:00+10', NULL, 2);
INSERT INTO public.tariff_generated_rate_response("tariff_generated_rate_response_id", "tariff_generated_rate_id", "site_id", "created_time", "response_type", "pricing_reading_type") VALUES (3, 3, 2, '2022-01-03 00:00:00+10', 2, 3);

SELECT pg_catalog.setval('public.tariff_generated_rate_respons_tariff_generated_rate_respons_seq', 4, true);


INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (1, 1, 2, '2000-01-01 00:00:00Z', '2022-05-06 11:22:33.500', '2022-05-07 01:02+10', 11, 1.11, -1.22);
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (2, 1, 2, '2000-01-01 00:00:00Z', '2022-05-06 12:22:33.500', '2022-05-07 03:04+10', 22, 2.11, -2.22);
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (3, 2, 2, '2000-01-01 00:00:00Z', '2022-05-06 13:22:33.500', '2022-05-07 01:02+10', 33, 3.11, -3.22);
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (4, 1, NULL, '2000-01-01 00:00:00Z', '2022-05-06 14:22:33.500', '2022-05-08 01:02+10', 44, 4.11, -4.22);

SELECT pg_catalog.setval('public.dynamic_operating_envelope_dynamic_operating_envelope_id_seq', 5, true);


INSERT INTO public.dynamic_operating_envelope_response("dynamic_operating_envelope_response_id", "dynamic_operating_envelope_id", "site_id", "created_time", "response_type") VALUES (1, 1, 1, '2023-01-01 00:00:00+10', 3);
INSERT INTO public.dynamic_operating_envelope_response("dynamic_operating_envelope_response_id", "dynamic_operating_envelope_id", "site_id", "created_time", "response_type") VALUES (2, 1, 1, '2023-01-02 00:00:00+10', NULL);
INSERT INTO public.dynamic_operating_envelope_response("dynamic_operating_envelope_response_id", "dynamic_operating_envelope_id", "site_id", "created_time", "response_type") VALUES (3, 3, 2, '2023-01-03 00:00:00+10', 4);

SELECT pg_catalog.setval('public.dynamic_operating_envelope_re_dynamic_operating_envelope_re_seq', 4, true);


INSERT INTO public.site_reading_type("site_reading_type_id", "aggregator_id", "site_id", "uom", "data_qualifier", "flow_direction", "accumulation_behaviour", "kind", "phase", "power_of_ten_multiplier", "default_interval_seconds", "created_time", "changed_time")
VALUES (1, -- site_reading_type_id
    1, -- aggregator_id
    1, -- site_id
    38, -- uom
    2, -- data_qualifier
    1, -- flow_direction
    3, -- accumulation_behaviour
    37, -- kind
    64, -- phase
    3, -- power_of_ten_multiplier
    0, -- default_interval_seconds
    '2000-01-01 00:00:00Z', -- created_time
    '2022-05-06 11:22:33.500' -- changed_time
    );
INSERT INTO public.site_reading_type("site_reading_type_id", "aggregator_id", "site_id", "uom", "data_qualifier", "flow_direction", "accumulation_behaviour", "kind", "phase", "power_of_ten_multiplier", "default_interval_seconds", "created_time", "changed_time")
VALUES (2, -- site_reading_type_id
    3, -- aggregator_id
    1, -- site_id
    61, -- uom
    2, -- data_qualifier
    1, -- flow_direction
    3, -- accumulation_behaviour
    37, -- kind
    64, -- phase
    0, -- power_of_ten_multiplier
    0, -- default_interval_seconds
    '2000-01-01 00:00:00Z', -- created_time
    '2022-05-06 12:22:33.500' -- changed_time
    );
INSERT INTO public.site_reading_type("site_reading_type_id", "aggregator_id", "site_id", "uom", "data_qualifier", "flow_direction", "accumulation_behaviour", "kind", "phase", "power_of_ten_multiplier", "default_interval_seconds", "created_time", "changed_time")
VALUES (3, -- site_reading_type_id
    1, -- aggregator_id
    1, -- site_id
    38, -- uom
    8, -- data_qualifier
    1, -- flow_direction
    3, -- accumulation_behaviour
    37, -- kind
    64, -- phase
    0, -- power_of_ten_multiplier
    3600, -- default_interval_seconds
    '2000-01-01 00:00:00Z', -- created_time
    '2022-05-06 13:22:33.500' -- changed_time
    );
INSERT INTO public.site_reading_type("site_reading_type_id", "aggregator_id", "site_id", "uom", "data_qualifier", "flow_direction", "accumulation_behaviour", "kind", "phase", "power_of_ten_multiplier", "default_interval_seconds", "created_time", "changed_time")
VALUES (4, -- site_reading_type_id
    1, -- aggregator_id
    2, -- site_id
    38, -- uom
    9, -- data_qualifier
    19, -- flow_direction
    12, -- accumulation_behaviour
    12, -- kind
    0, -- phase
    -1, -- power_of_ten_multiplier
    0, -- default_interval_seconds
    '2000-01-01 00:00:00Z', -- created_time
    '2022-05-06 14:22:33.500' -- changed_time
    );

SELECT pg_catalog.setval('public.site_reading_type_site_reading_type_id_seq', 5, true);


INSERT INTO public.site_reading("site_reading_id", "site_reading_type_id", "created_time", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (1, -- site_reading_id
    1, -- site_reading_type_id
    '2000-01-01 00:00:00Z', -- created_time
    '2022-06-07 11:22:33.500', -- changed_time
    11111, -- local_id
    1, -- quality_flags
    '2022-06-07 01:00:00+10', -- time_period_start
    300, -- time_period_seconds
    11 -- value
    );
INSERT INTO public.site_reading("site_reading_id", "site_reading_type_id", "created_time", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (2, -- site_reading_id
    1, -- site_reading_type_id
    '2000-01-01 00:00:00Z', -- created_time
    '2022-06-07 12:22:33.500', -- changed_time
    22222, -- local_id
    2, -- quality_flags
    '2022-06-07 02:00:00+10', -- time_period_start
    300, -- time_period_seconds
    12 -- value
    );
INSERT INTO public.site_reading("site_reading_id", "site_reading_type_id", "created_time", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (3, -- site_reading_id
    2, -- site_reading_type_id
    '2000-01-01 00:00:00Z', -- created_time
    '2022-06-07 13:22:33.500', -- changed_time
    33333, -- local_id
    3, -- quality_flags
    '2022-06-07 01:00:00+10', -- time_period_start
    300, -- time_period_seconds
    13 -- value
    );
INSERT INTO public.site_reading("site_reading_id", "site_reading_type_id", "created_time", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (4, -- site_reading_id
    4, -- site_reading_type_id
    '2000-01-01 00:00:00Z', -- created_time
    '2022-06-07 14:22:33.500', -- changed_time
    44444, -- local_id
    4, -- quality_flags
    '2022-06-07 01:00:00+10', -- time_period_start
    300, -- time_period_seconds
    14 -- value
    );

SELECT pg_catalog.setval('public.site_reading_site_reading_id_seq', 5, true);


INSERT INTO public.subscription("subscription_id", "aggregator_id", "created_time", "changed_time", "resource_type", "resource_id", "scoped_site_id", "notification_uri", "entity_limit")
VALUES (1, -- subscription_id
    1, -- aggregator_id
    '2000-01-01 00:00:00Z', -- created_time
    '2024-01-02 11:22:33.500', -- changed_time
    1, -- resource_type
    NULL, -- resource_id
    NULL, -- scoped_site_id
    'https://example.com:11/path/', -- notification_uri
    11 -- entity_limit
    );
INSERT INTO public.subscription("subscription_id", "aggregator_id", "created_time", "changed_time", "resource_type", "resource_id", "scoped_site_id", "notification_uri", "entity_limit")
VALUES (2, -- subscription_id
    1, -- aggregator_id
    '2000-01-01 00:00:00Z', -- created_time
    '2024-01-02 12:22:33.500', -- changed_time
    2, -- resource_type
    NULL, -- resource_id
    2, -- scoped_site_id
    'https://example.com:22/path/', -- notification_uri
    22 -- entity_limit
    );
INSERT INTO public.subscription("subscription_id", "aggregator_id", "created_time", "changed_time", "resource_type", "resource_id", "scoped_site_id", "notification_uri", "entity_limit")
VALUES (3, -- subscription_id
    2, -- aggregator_id
    '2000-01-01 00:00:00Z', -- created_time
    '2024-01-02 13:22:33.500', -- changed_time
    3, -- resource_type
    3, -- resource_id
    3, -- scoped_site_id
    'https://example.com:33/path/', -- notification_uri
    33 -- entity_limit
    );
INSERT INTO public.subscription("subscription_id", "aggregator_id", "created_time", "changed_time", "resource_type", "resource_id", "scoped_site_id", "notification_uri", "entity_limit")
VALUES (4, -- subscription_id
    1, -- aggregator_id
    '2000-01-01 00:00:00Z', -- created_time
    '2024-01-02 14:22:33.500', -- changed_time
    1, -- resource_type
    4, -- resource_id
    4, -- scoped_site_id
    'https://example.com:44/path/', -- notification_uri
    44 -- entity_limit
    );
INSERT INTO public.subscription("subscription_id", "aggregator_id", "created_time", "changed_time", "resource_type", "resource_id", "scoped_site_id", "notification_uri", "entity_limit")
VALUES (5, -- subscription_id
    1, -- aggregator_id
    '2000-01-01 00:00:00Z', -- created_time
    '2024-01-02 15:22:33.500', -- changed_time
    4, -- resource_type
    1, -- resource_id
    NULL, -- scoped_site_id
    'https://example.com:55/path/', -- notification_uri
    55 -- entity_limit
    );

SELECT pg_catalog.setval('public.subscription_subscription_id_seq', 6, true);


INSERT INTO public.subscription_condition("subscription_condition_id", "subscription_id", "attribute", "lower_threshold", "upper_threshold")
VALUES (1, -- subscription_condition_id
    5, -- subscription_id
    0, -- attribute
    1, -- lower_threshold
    11 -- upper_threshold
    );
INSERT INTO public.subscription_condition("subscription_condition_id", "subscription_id", "attribute", "lower_threshold", "upper_threshold")
VALUES (2, -- subscription_condition_id
    5, -- subscription_id
    0, -- attribute
    2, -- lower_threshold
    12 -- upper_threshold
    );

SELECT pg_catalog.setval('public.subscription_condition_subscription_condition_id_seq', 3, true);


INSERT INTO public.site_group("site_group_id", "created_time", "changed_time", "name") VALUES (1, '2000-01-01 00:00:00Z', '2024-02-10 01:55:44.500', 'Group-1');
INSERT INTO public.site_group("site_group_id", "created_time", "changed_time", "name") VALUES (2, '2000-01-01 00:00:00Z', '2024-02-10 02:55:44.500', 'Group-2');
INSERT INTO public.site_group("site_group_id", "created_time", "changed_time", "name") VALUES (3, '2000-01-01 00:00:00Z', '2024-02-10 03:55:44.500', 'Group-3');

SELECT pg_catalog.setval('public.site_group_site_group_id_seq', 4, true);

INSERT INTO public.site_group_assignment("site_group_assignment_id", "created_time", "changed_time", "site_id", "site_group_id") 
VALUES (1, '2000-01-01 00:00:00Z', '2024-02-11 01:55:44.500', 1, 1);
INSERT INTO public.site_group_assignment("site_group_assignment_id", "created_time", "changed_time", "site_id", "site_group_id") 
VALUES (2, '2000-01-01 00:00:00Z', '2024-02-11 02:55:44.500', 2, 1);
INSERT INTO public.site_group_assignment("site_group_assignment_id", "created_time", "changed_time", "site_id", "site_group_id") 
VALUES (3, '2000-01-01 00:00:00Z', '2024-02-11 03:55:44.500', 3, 1);
INSERT INTO public.site_group_assignment("site_group_assignment_id", "created_time", "changed_time", "site_id", "site_group_id") 
VALUES (4, '2000-01-01 00:00:00Z', '2024-02-11 04:55:44.500', 1, 2);

SELECT pg_catalog.setval('public.site_group_assignment_site_group_assignment_id_seq', 5, true);


INSERT INTO public.site_der("site_der_id", "created_time", "changed_time", "site_id") 
VALUES (1, '2000-01-01 00:00:00Z', '2024-03-14 04:55:44.500', 2);
INSERT INTO public.site_der("site_der_id", "created_time", "changed_time", "site_id") 
VALUES (2, '2000-01-01 00:00:00Z', '2024-03-14 05:55:44.500', 1);
SELECT pg_catalog.setval('public.site_der_site_der_id_seq', 3, true);

-- These DER values have been autogenerated due to their enormous size
-- They assign a DERAvailability, DERCapability, DERSettings and DERStatus to DER 2 which belongs to site 1

INSERT INTO public.site_der_availability (site_der_availability_id, site_der_id, created_time, changed_time, availability_duration_sec, max_charge_duration_sec, reserved_charge_percent, reserved_deliver_percent, estimated_var_avail_value, estimated_var_avail_multiplier, estimated_w_avail_value, estimated_w_avail_multiplier) 
VALUES (1, 2, '2000-01-01 00:00:00Z', '2022-07-23 10:03:23.500', 202, 208, 12.12, 13.12, 205, 204, 207, 206);
SELECT pg_catalog.setval('public.site_der_availability_site_der_availability_id_seq', 2, true);

INSERT INTO public.site_der_rating (site_der_rating_id, site_der_id, created_time, changed_time, modes_supported, abnormal_category, max_a_value, max_a_multiplier, max_ah_value, max_ah_multiplier, max_charge_rate_va_value, max_charge_rate_va_multiplier, max_charge_rate_w_value, max_charge_rate_w_multiplier, max_discharge_rate_va_value, max_discharge_rate_va_multiplier, max_discharge_rate_w_value, max_discharge_rate_w_multiplier, max_v_value, max_v_multiplier, max_va_value, max_va_multiplier, max_var_value, max_var_multiplier, max_var_neg_value, max_var_neg_multiplier, max_w_value, max_w_multiplier, max_wh_value, max_wh_multiplier, min_pf_over_excited_displacement, min_pf_over_excited_multiplier, min_pf_under_excited_displacement, min_pf_under_excited_multiplier, min_v_value, min_v_multiplier, normal_category, over_excited_pf_displacement, over_excited_pf_multiplier, over_excited_w_value, over_excited_w_multiplier, reactive_susceptance_value, reactive_susceptance_multiplier, under_excited_pf_displacement, under_excited_pf_multiplier, under_excited_w_value, under_excited_w_multiplier, v_nom_value, v_nom_multiplier, der_type, doe_modes_supported) 
VALUES (1, 2, '2000-01-01 00:00:00Z', '2022-04-13 10:01:42.500', 1, 1, 106, 105, 108, 107, 110, 109, 112, 111, 114, 113, 116, 115, 118, 117, 120, 119, 124, 121, 123, 122, 126, 125, 128, 127, 129, 130, 131, 132, 134, 133, 1, 137, 138, 140, 139, 142, 141, 1145, 1146, 1148, 1147, 1150, 1149, 4, 1);
SELECT pg_catalog.setval('public.site_der_rating_site_der_rating_id_seq', 2, true);

INSERT INTO public.site_der_setting (site_der_setting_id, site_der_id, created_time, changed_time, modes_enabled, es_delay, es_high_freq, es_high_volt, es_low_freq, es_low_volt, es_ramp_tms, es_random_delay, grad_w, max_a_value, max_a_multiplier, max_ah_value, max_ah_multiplier, max_charge_rate_va_value, max_charge_rate_va_multiplier, max_charge_rate_w_value, max_charge_rate_w_multiplier, max_discharge_rate_va_value, max_discharge_rate_va_multiplier, max_discharge_rate_w_value, max_discharge_rate_w_multiplier, max_v_value, max_v_multiplier, max_va_value, max_va_multiplier, max_var_value, max_var_multiplier, max_var_neg_value, max_var_neg_multiplier, max_w_value, max_w_multiplier, max_wh_value, max_wh_multiplier, min_pf_over_excited_displacement, min_pf_over_excited_multiplier, min_pf_under_excited_displacement, min_pf_under_excited_multiplier, min_v_value, min_v_multiplier, soft_grad_w, v_nom_value, v_nom_multiplier, v_ref_value, v_ref_multiplier, v_ref_ofs_value, v_ref_ofs_multiplier, doe_modes_enabled)
VALUES (1, 2, '2000-01-01 00:00:00Z', '2022-02-09 11:06:44.500', 4096, 406, 407, 408, 409, 410, 411, 412, 413, 415, 414, 417, 416, 419, 418, 421, 420, 423, 422, 425, 424, 427, 426, 429, 428, 433, 430, 432, 431, 435, 434, 437, 436, 438, 439, 440, 441, 443, 442, 1447, 1449, 1448, 1453, 1450, 1452, 1451, 2);
SELECT pg_catalog.setval('public.site_der_setting_site_der_setting_id_seq', 2, true);

INSERT INTO public.site_der_status (site_der_status_id, site_der_id, created_time, changed_time, alarm_status, generator_connect_status, generator_connect_status_time, inverter_status, inverter_status_time, local_control_mode_status, local_control_mode_status_time, manufacturer_status, manufacturer_status_time, operational_mode_status, operational_mode_status_time, state_of_charge_status, state_of_charge_status_time, storage_mode_status, storage_mode_status_time, storage_connect_status, storage_connect_status_time) 
VALUES (1, 2, '2000-01-01 00:00:00Z', '2022-11-01 11:05:04.500', 64, 1, '2010-11-03 11:05:06+11', 10, '2010-11-05 11:05:08+11', 1, '2010-11-07 11:05:10+11', 'mnstat', '2010-11-09 11:05:12+11', 1, '2010-11-11 11:05:14+11', NULL, '2016-05-06 10:38:37+10', 1, '2016-05-10 10:38:41+10', 8, '2016-05-08 10:38:39+10');
SELECT pg_catalog.setval('public.site_der_status_site_der_status_id_seq', 2, true);

