-- Adds a higher density of DynamicOperatingEnvelopes (including archived records) based on time/duration for site1


INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (5, 1, 1, NULL, '2000-01-01 00:00:00Z', '2023-05-06 11:22:33', '2023-05-07 01:00:00+10', 300, '2023-05-07 01:05:00+10', 5.11, -5.22);
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (6, 1, 1, NULL, '2000-01-01 00:00:00Z', '2023-05-06 11:22:33', '2023-05-07 01:05:00+10', 300, '2023-05-07 01:10:00+10', 6.11, -6.22);
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (7, 1, 1, NULL, '2000-01-01 00:00:00Z', '2023-05-06 11:22:33', '2023-05-07 01:10:00+10', 300, '2023-05-07 01:15:00+10', 7.11, -7.22);
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (8, 1, 1, NULL, '2000-01-01 00:00:00Z', '2023-05-06 11:22:33', '2023-05-07 01:15:00+10', 300, '2023-05-07 01:20:00+10', 8.11, -8.22);

-- This will overlap 5/6 (offset by a single second)
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (9, 1, 1, NULL, '2000-01-01 00:00:00Z', '2023-02-03 11:22:33', '2023-05-07 01:00:01+10', 599, '2023-05-07 01:10:00+10', 9.11, -9.22);


INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (10, 1, 2, NULL, '2000-01-01 00:00:00Z', '2023-05-06 11:22:33', '2023-05-07 01:00:00+10', 300, '2023-05-07 01:05:00+10', 10.11, -10.22);
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (11, 1, 2, NULL, '2000-01-01 00:00:00Z', '2023-05-06 11:22:33', '2023-05-07 01:05:00+10', 300, '2023-05-07 01:10:00+10', 11.11, -11.22);
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (12, 1, 2, NULL, '2000-01-01 00:00:00Z', '2023-05-06 11:22:33', '2023-05-07 01:10:00+10', 300, '2023-05-07 01:15:00+10', 12.11, -12.22);
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (13, 1, 2, NULL, '2000-01-01 00:00:00Z', '2023-05-06 11:22:33', '2023-05-07 01:15:00+10', 300, '2023-05-07 01:20:00+10', 13.11, -13.22);


INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (14, 1, 3, NULL, '2000-01-01 00:00:00Z', '2023-05-06 11:22:33', '2023-05-07 01:00:00+10', 300, '2023-05-07 01:05:00+10', 14.11, -14.22);
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (15, 1, 3, NULL, '2000-01-01 00:00:00Z', '2023-05-06 11:22:33', '2023-05-07 01:05:00+10', 300, '2023-05-07 01:10:00+10', 15.11, -15.22);
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (16, 1, 3, NULL, '2000-01-01 00:00:00Z', '2023-05-06 11:22:33', '2023-05-07 01:10:00+10', 300, '2023-05-07 01:15:00+10', 16.11, -16.22);
INSERT INTO public.dynamic_operating_envelope("dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (17, 1, 3, NULL, '2000-01-01 00:00:00Z', '2023-05-06 11:22:33', '2023-05-07 01:15:00+10', 300, '2023-05-07 01:20:00+10', 17.11, -17.22);

SELECT pg_catalog.setval('public.dynamic_operating_envelope_dynamic_operating_envelope_id_seq', 18, true);

INSERT INTO public.archive_dynamic_operating_envelope("archive_id", "archive_time", "deleted_time", "dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (1, '2000-01-01 00:00:00Z', NULL, 18, 1, 1, NULL, '2000-01-01 00:00:00Z', '2023-05-06 11:22:33', '2023-05-07 01:00:00+10', 300, '2023-05-07 01:05:00+10', 1800, -1800);
INSERT INTO public.archive_dynamic_operating_envelope("archive_id", "archive_time", "deleted_time", "dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (2, '2000-01-01 00:00:00Z', '2023-05-06 11:22:33', 18, 1, 1, NULL, '2000-01-01 00:00:00Z', '2010-01-01 00:00:00', '2023-05-07 01:00:00+10', 300, '2023-05-07 01:05:00+10', 18.11, -18.22);
INSERT INTO public.archive_dynamic_operating_envelope("archive_id", "archive_time", "deleted_time", "dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (3, '2000-01-01 00:00:00Z', '2023-05-06 11:22:33', 19, 1, 1, NULL, '2000-01-01 00:00:00Z', '2010-01-01 00:00:00', '2023-05-07 01:05:00+10', 300, '2023-05-07 01:10:00+10', 19.11, -19.22);
INSERT INTO public.archive_dynamic_operating_envelope("archive_id", "archive_time", "deleted_time", "dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (4, '2000-01-01 00:00:00Z', '2023-05-06 11:22:33', 20, 1, 2, NULL, '2000-01-01 00:00:00Z', '2010-01-01 00:00:00', '2023-05-07 01:00:00+10', 300, '2023-05-07 01:05:00+10', 20.11, -20.22);
INSERT INTO public.archive_dynamic_operating_envelope("archive_id", "archive_time", "deleted_time", "dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (5, '2000-01-01 00:00:00Z', NULL, 1, 1, 1, NULL, '2000-01-01 00:00:00Z', '2023-05-06 11:22:33', '2023-05-07 01:00:00+10', 300, '2023-05-07 01:05:00+10', 100, -100);
INSERT INTO public.archive_dynamic_operating_envelope("archive_id", "archive_time", "deleted_time", "dynamic_operating_envelope_id", "site_control_group_id", "site_id", "calculation_log_id", "created_time", "changed_time", "start_time", "duration_seconds", "end_time", "import_limit_active_watts", "export_limit_watts")
VALUES (6, '2000-01-01 00:00:00Z', NULL, 21, 1, 1, NULL, '2000-01-01 00:00:00Z', '2023-05-06 11:22:33', '2023-05-07 01:00:00+10', 300, '2023-05-07 01:05:00+10', 2100, -2100);

SELECT pg_catalog.setval('public.archive_dynamic_operating_envelope_archive_id_seq', 7, true);