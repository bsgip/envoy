-- "reference" dataset that all database specific tests will build upon
-- designed to be the "minimum useful configuration" that most tests will utilise

SET row_security = off;

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

INSERT INTO public.site("site_id", "nmi", "aggregator_id", "changed_time", "lfdi", "sfdi", "device_category") VALUES (1, '1111111111', 1, '2022-02-03 04:05:06', 'site1-lfdi', 1111, 0);
INSERT INTO public.site("site_id", "nmi", "aggregator_id", "changed_time", "lfdi", "sfdi", "device_category") VALUES (2, '2222222222', 1, '2022-02-03 05:06:07', 'site2-lfdi', 2222, 1);
INSERT INTO public.site("site_id", "nmi", "aggregator_id", "changed_time", "lfdi", "sfdi", "device_category") VALUES (3, '3333333333', 2, '2022-02-03 08:09:10', 'site3-lfdi', 3333, 2);
INSERT INTO public.site("site_id", "nmi", "aggregator_id", "changed_time", "lfdi", "sfdi", "device_category") VALUES (4, '4444444444', 1, '2022-02-03 11:12:13', 'site4-lfdi', 4444, 3);

SELECT pg_catalog.setval('public.site_site_id_seq', 5, true);