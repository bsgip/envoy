-- "reference" dataset that all database specific tests will build upon
-- designed to be the "minimum useful configuration" that most tests will utilise

SET row_security = off;

INSERT INTO public.aggregator("aggregator_id", "name") VALUES (1, 'Aggregator 1');
INSERT INTO public.aggregator("aggregator_id", "name") VALUES (2, 'Aggregator 2');
INSERT INTO public.aggregator("aggregator_id", "name") VALUES (3, 'Aggregator 3');

INSERT INTO public.certificate("certificate_id", "created", "lfdi", "expiry") VALUES (1, '2023-01-01 01:02:03', 'active-lfdi-agg1-1', '2037-01-01 01:02:03');
INSERT INTO public.certificate("certificate_id", "created", "lfdi", "expiry") VALUES (2, '2023-01-01 02:03:04', 'active-lfdi-agg1-2', '2037-01-01 02:03:04');
INSERT INTO public.certificate("certificate_id", "created", "lfdi", "expiry") VALUES (3, '2023-01-01 01:02:03', 'expired-lfdi-agg1-1', '2023-01-01 01:02:04'); -- expired
INSERT INTO public.certificate("certificate_id", "created", "lfdi", "expiry") VALUES (4, '2023-01-01 01:02:03', 'active-lfdi-agg2-1', '2037-01-01 01:02:03');

INSERT INTO public.aggregator_certificate_assignment("assignment_id", "certificate_id", "aggregator_id") VALUES (1, 1, 1);
INSERT INTO public.aggregator_certificate_assignment("assignment_id", "certificate_id", "aggregator_id") VALUES (2, 2, 1);
INSERT INTO public.aggregator_certificate_assignment("assignment_id", "certificate_id", "aggregator_id") VALUES (3, 3, 1);
INSERT INTO public.aggregator_certificate_assignment("assignment_id", "certificate_id", "aggregator_id") VALUES (4, 4, 2);
