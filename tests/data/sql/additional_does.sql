-- Adds a higher density of DynamicOperatingEnvelopes based on time/duration for site1


INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (5, 1, '2023-05-06 11:22:33', '2023-05-07 01:00:00+10', 300, 5.11, -5.22);
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (6, 1, '2023-05-06 11:22:33', '2023-05-07 01:05:00+10', 300, 6.11, -6.22);
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (7, 1, '2023-05-06 11:22:33', '2023-05-07 01:10:00+10', 300, 7.11, -7.22);
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (8, 1, '2023-05-06 11:22:33', '2023-05-07 01:15:00+10', 300, 8.11, -8.22);

-- This will overlap 5/6 (offset by a single second)
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_id", "changed_time", "start_time", "duration_seconds", "import_limit_active_watts", "export_limit_watts")
VALUES (9, 1, '2023-02-03 11:22:33', '2023-05-07 01:00:01+10', 599, 9.11, -9.22);

SELECT pg_catalog.setval('public.dynamic_operating_envelope_dynamic_operating_envelope_id_seq', 10, true);

