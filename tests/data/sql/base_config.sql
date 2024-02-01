-- "reference" dataset that all database specific tests will build upon
-- designed to be the "minimum useful configuration" that most tests will utilise

SET row_security = off;
SET timezone = 'UTC';

INSERT INTO public.aggregator("aggregator_id", "name") VALUES (1, 'Aggregator 1');
INSERT INTO public.aggregator("aggregator_id", "name") VALUES (2, 'Aggregator 2');
INSERT INTO public.aggregator("aggregator_id", "name") VALUES (3, 'Aggregator 3');

SELECT pg_catalog.setval('public.aggregator_aggregator_id_seq', 4, true);

-- See tests/data/certificates for how these were generated
INSERT INTO public.certificate("certificate_id", "created", "lfdi", "expiry") VALUES (1, '2023-01-01 01:02:03', '854d10a201ca99e5e90d3c3e1f9bc1c3bd075f3b', '2037-01-01 01:02:03'); -- certificate 1
INSERT INTO public.certificate("certificate_id", "created", "lfdi", "expiry") VALUES (2, '2023-01-01 02:03:04', '403ba02aa36fa072c47eb3299daaafe94399adad', '2037-01-01 02:03:04'); -- certificate 2
INSERT INTO public.certificate("certificate_id", "created", "lfdi", "expiry") VALUES (3, '2023-01-01 01:02:03', 'c9ed55b4b4f8647916bfb7f426792e015ffc2441', '2023-01-01 01:02:04'); -- expired certificate 3
INSERT INTO public.certificate("certificate_id", "created", "lfdi", "expiry") VALUES (4, '2023-01-01 01:02:03', '8ad1d4ce1d3b353ebee21230a89e4172b18f520e', '2037-01-01 01:02:03'); -- certificate 4
INSERT INTO public.certificate("certificate_id", "created", "lfdi", "expiry") VALUES (5, '2023-01-01 01:02:03', 'ec08e4c9d68a0669c3673708186fde317f7c67a2', '2037-01-01 01:02:03'); -- certificate 5

SELECT pg_catalog.setval('public.certificate_certificate_id_seq', 6, true);

INSERT INTO public.aggregator_certificate_assignment("assignment_id", "certificate_id", "aggregator_id") VALUES (1, 1, 1);
INSERT INTO public.aggregator_certificate_assignment("assignment_id", "certificate_id", "aggregator_id") VALUES (2, 2, 1);
INSERT INTO public.aggregator_certificate_assignment("assignment_id", "certificate_id", "aggregator_id") VALUES (3, 3, 1);
INSERT INTO public.aggregator_certificate_assignment("assignment_id", "certificate_id", "aggregator_id") VALUES (4, 4, 2);
INSERT INTO public.aggregator_certificate_assignment("assignment_id", "certificate_id", "aggregator_id") VALUES (5, 5, 3);

SELECT pg_catalog.setval('public.aggregator_certificate_assignment_assignment_id_seq', 6, true);

INSERT INTO public.site("site_id", "nmi", "aggregator_id", "timezone_id", "changed_time", "lfdi", "sfdi", "device_category") VALUES (1, '1111111111', 1, 'Australia/Brisbane', '2022-02-03 04:05:06', 'site1-lfdi', 1111, 0);
INSERT INTO public.site("site_id", "nmi", "aggregator_id", "timezone_id", "changed_time", "lfdi", "sfdi", "device_category") VALUES (2, '2222222222', 1, 'Australia/Brisbane', '2022-02-03 05:06:07', 'site2-lfdi', 2222, 1);
INSERT INTO public.site("site_id", "nmi", "aggregator_id", "timezone_id", "changed_time", "lfdi", "sfdi", "device_category") VALUES (3, '3333333333', 2, 'Australia/Brisbane', '2022-02-03 08:09:10', 'site3-lfdi', 3333, 2);
INSERT INTO public.site("site_id", "nmi", "aggregator_id", "timezone_id", "changed_time", "lfdi", "sfdi", "device_category") VALUES (4, '4444444444', 1, 'Australia/Brisbane', '2022-02-03 11:12:13', 'site4-lfdi', 4444, 3);

SELECT pg_catalog.setval('public.site_site_id_seq', 5, true);

INSERT INTO public.tariff("tariff_id", "name", "dnsp_code", "currency_code", "changed_time") VALUES (1, 'tariff-1', 'tariff-dnsp-code-1', 36, '2023-01-02 11:01:02');
INSERT INTO public.tariff("tariff_id", "name", "dnsp_code", "currency_code", "changed_time") VALUES (2, 'tariff-2', 'tariff-dnsp-code-2', 124, '2023-01-02 12:01:02');
INSERT INTO public.tariff("tariff_id", "name", "dnsp_code", "currency_code", "changed_time") VALUES (3, 'tariff-3', 'tariff-dnsp-code-3', 840, '2023-01-02 13:01:02');

SELECT pg_catalog.setval('public.tariff_tariff_id_seq', 4, true);

INSERT INTO public.tariff_generated_rate("tariff_generated_rate_id", "tariff_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (1, 1, 1, '2022-03-04 11:22:33', '2022-03-05 01:02+10', 11, 1.1, -1.22, 1.333, -1.4444);
INSERT INTO public.tariff_generated_rate("tariff_generated_rate_id", "tariff_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (2, 1, 1, '2022-03-04 12:22:33', '2022-03-05 03:04+10', 12, 2.1, -2.22, 2.333, -2.4444);
INSERT INTO public.tariff_generated_rate("tariff_generated_rate_id", "tariff_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (3, 1, 2, '2022-03-04 13:22:33', '2022-03-05 01:02+10', 13, 3.1, -3.22, 3.333, -3.4444);
INSERT INTO public.tariff_generated_rate("tariff_generated_rate_id", "tariff_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_active_price", "export_active_price", "import_reactive_price", "export_reactive_price")
VALUES (4, 1, 1, '2022-03-04 14:22:33', '2022-03-06 01:02+10', 14, 4.1, -4.22, 4.333, -4.4444);

SELECT pg_catalog.setval('public.tariff_generated_rate_tariff_generated_rate_id_seq', 5, true);

INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (1, 1, '2022-05-06 11:22:33', '2022-05-07 01:02+10', 11, 1.11, -1.22);
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (2, 1, '2022-05-06 12:22:33', '2022-05-07 03:04+10', 22, 2.11, -2.22);
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (3, 2, '2022-05-06 13:22:33', '2022-05-07 01:02+10', 33, 3.11, -3.22);
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (4, 1, '2022-05-06 14:22:33', '2022-05-08 01:02+10', 44, 4.11, -4.22);

SELECT pg_catalog.setval('public.dynamic_operating_envelope_dynamic_operating_envelope_id_seq', 5, true);

INSERT INTO public.site_reading_type("site_reading_type_id", "aggregator_id", "site_id", "uom", "data_qualifier", "flow_direction", "accumulation_behaviour", "kind", "phase", "power_of_ten_multiplier", "default_interval_seconds", "changed_time")
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
    '2022-05-06 11:22:33' -- changed_time
    );
INSERT INTO public.site_reading_type("site_reading_type_id", "aggregator_id", "site_id", "uom", "data_qualifier", "flow_direction", "accumulation_behaviour", "kind", "phase", "power_of_ten_multiplier", "default_interval_seconds", "changed_time")
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
    '2022-05-06 12:22:33' -- changed_time
    );
INSERT INTO public.site_reading_type("site_reading_type_id", "aggregator_id", "site_id", "uom", "data_qualifier", "flow_direction", "accumulation_behaviour", "kind", "phase", "power_of_ten_multiplier", "default_interval_seconds", "changed_time")
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
    '2022-05-06 13:22:33' -- changed_time
    );
INSERT INTO public.site_reading_type("site_reading_type_id", "aggregator_id", "site_id", "uom", "data_qualifier", "flow_direction", "accumulation_behaviour", "kind", "phase", "power_of_ten_multiplier", "default_interval_seconds", "changed_time")
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
    '2022-05-06 14:22:33' -- changed_time
    );

SELECT pg_catalog.setval('public.site_reading_type_site_reading_type_id_seq', 5, true);


INSERT INTO public.site_reading("site_reading_id", "site_reading_type_id", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (1, -- site_reading_id
    1, -- site_reading_type_id
    '2022-06-07 11:22:33', -- changed_time
    11111, -- local_id
    1, -- quality_flags
    '2022-06-07 01:00:00+10', -- time_period_start
    300, -- time_period_seconds
    11 -- value
    );
INSERT INTO public.site_reading("site_reading_id", "site_reading_type_id", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (2, -- site_reading_id
    1, -- site_reading_type_id
    '2022-06-07 12:22:33', -- changed_time
    22222, -- local_id
    2, -- quality_flags
    '2022-06-07 02:00:00+10', -- time_period_start
    300, -- time_period_seconds
    12 -- value
    );
INSERT INTO public.site_reading("site_reading_id", "site_reading_type_id", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (3, -- site_reading_id
    2, -- site_reading_type_id
    '2022-06-07 13:22:33', -- changed_time
    33333, -- local_id
    3, -- quality_flags
    '2022-06-07 01:00:00+10', -- time_period_start
    300, -- time_period_seconds
    13 -- value
    );
INSERT INTO public.site_reading("site_reading_id", "site_reading_type_id", "changed_time", "local_id", "quality_flags", "time_period_start", "time_period_seconds", "value")
VALUES (4, -- site_reading_id
    4, -- site_reading_type_id
    '2022-06-07 14:22:33', -- changed_time
    44444, -- local_id
    4, -- quality_flags
    '2022-06-07 01:00:00+10', -- time_period_start
    300, -- time_period_seconds
    14 -- value
    );

SELECT pg_catalog.setval('public.site_reading_site_reading_id_seq', 5, true);
