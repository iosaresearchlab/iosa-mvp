-- T-14 (docs/08-implementation-plan.md; docs/02 section 5): the daily
-- reading at 23:59 UTC, and the second attempt at 00:30 UTC.
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-25 as migration
-- 20260925210300 "v2_t14_schedule", after Render was deployed from this
-- branch. The SQL below the comments is the exact SQL applied.
--
-- The second attempt needs no condition here. The backend computes the
-- reading day as (now - 1 h) in UTC, so a call at 00:30 belongs to the day
-- just closed, and it answers 409 when an ingest_run row for that day
-- already exists (backend/main.py, reading_day in backend/vpi_engine.py).
--
-- Rollback:
--   select cron.alter_job((select jobid from cron.job where jobname = 'ingestione-iosa'), active := false);
--   select cron.unschedule('ingestione-iosa-retry');
select cron.alter_job((select jobid from cron.job where jobname = 'ingestione-iosa'),
                      schedule := '59 23 * * *', active := true);
select cron.schedule('ingestione-iosa-retry', '30 0 * * *',
                     'select public.chiedi_un_giro_di_ingestione()');
