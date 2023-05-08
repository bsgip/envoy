-- Mutates all sites to be in "America/Los_Angeles" time
-- Doesn't change any timestamps

UPDATE public.site SET "timezone_id" = 'America/Los_Angeles';
