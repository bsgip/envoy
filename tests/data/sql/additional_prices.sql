

-- Rate #3 has been modified a few times
INSERT INTO public.archive_tariff_generated_rate("archive_id", "archive_time", "deleted_time", "tariff_generated_rate_id", "tariff_id", "tariff_component_id", "site_id", "calculation_log_id", "start_time", "duration_seconds", "end_time", "price_pow10_encoded", "block_1_start_pow10_encoded", "price_pow10_encoded_block_1", "created_time", "changed_time")
VALUES (1, '2000-01-01 00:00:00Z', NULL, 3, 1, 1, 1, 2, '2022-03-05 01:00:33+10', 33, '2022-03-05 01:01:06+10', 3001, NULL, NULL, '2000-01-01 00:00:00Z', '2022-03-04 13:22:33.500');
INSERT INTO public.archive_tariff_generated_rate("archive_id", "archive_time", "deleted_time", "tariff_generated_rate_id", "tariff_id", "tariff_component_id", "site_id", "calculation_log_id", "start_time", "duration_seconds", "end_time", "price_pow10_encoded", "block_1_start_pow10_encoded", "price_pow10_encoded_block_1", "created_time", "changed_time")
VALUES (2, '2000-01-01 00:00:00Z', NULL, 3, 1, 1, 1, 2, '2022-03-05 01:00:33+10', 33, '2022-03-05 01:01:06+10', 3002, 3003, 3004, '2000-01-01 00:00:00Z', '2022-03-04 13:22:33.500');

-- Rate #8 has been deleted
INSERT INTO public.archive_tariff_generated_rate("archive_id", "archive_time", "deleted_time", "tariff_generated_rate_id", "tariff_id", "tariff_component_id", "site_id", "calculation_log_id", "start_time", "duration_seconds", "end_time", "price_pow10_encoded", "block_1_start_pow10_encoded", "price_pow10_encoded_block_1", "created_time", "changed_time")
VALUES (3, '2000-01-01 00:00:00Z', '2022-03-05 01:30:00Z', 8, 1, 1, 1, NULL, '2022-03-05 01:01:06+10', 88, '2022-03-05 01:02:34+10', 8888, 8000, 8001, '2000-01-01 00:00:00Z', '2022-03-04 13:22:33.500');

-- Rate #9 has been modified and deleted
INSERT INTO public.archive_tariff_generated_rate("archive_id", "archive_time", "deleted_time", "tariff_generated_rate_id", "tariff_id", "tariff_component_id", "site_id", "calculation_log_id", "start_time", "duration_seconds", "end_time", "price_pow10_encoded", "block_1_start_pow10_encoded", "price_pow10_encoded_block_1", "created_time", "changed_time")
VALUES (4, '2000-01-01 00:00:00Z', NULL, 9, 1, 1, 1, NULL, '2022-03-05 01:02:34+10', 99, '2022-03-05 01:04:13+10', 9001, 9008, 9009, '2000-01-01 00:00:00Z', '2022-03-04 13:22:33.500');
INSERT INTO public.archive_tariff_generated_rate("archive_id", "archive_time", "deleted_time", "tariff_generated_rate_id", "tariff_id", "tariff_component_id", "site_id", "calculation_log_id", "start_time", "duration_seconds", "end_time", "price_pow10_encoded", "block_1_start_pow10_encoded", "price_pow10_encoded_block_1", "created_time", "changed_time")
VALUES (5, '2000-01-01 00:00:00Z', '2022-03-05 01:35:00Z', 9, 1, 1, 1, NULL, '2022-03-05 01:02:34+10', 99, '2022-03-05 01:04:13+10', 9999, 9000, 9001, '2000-01-01 00:00:00Z', '2022-03-04 13:22:33.500');

SELECT pg_catalog.setval('public.archive_tariff_generated_rate_archive_id_seq', 6, true);