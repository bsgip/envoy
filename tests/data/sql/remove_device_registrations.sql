-- Removes the NULL Aggregator and individual device registrations

DELETE FROM public.site WHERE site_id IN (5, 6);
DELETE FROM public.aggregator WHERE aggregator_id = 0;