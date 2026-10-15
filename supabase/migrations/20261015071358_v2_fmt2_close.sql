-- FMT-2 closes (milestone of 15/10/2026): the recovery of 06:00 UTC found
-- nothing left within reach. Every v2 record from INDEX_START_DATE still
-- under format_rule 'duration_180' is in fmt2_left (75 = 75, every one an
-- item no longer returned); every phase-1 day (27/09-03/10) is done in
-- fmt2_run. The pg_cron entry goes; POST /api/recover/run,
-- chiedi_recupero_fmt2(), fmt2_run, fmt2_history and fmt2_left stay (the
-- record of what was done, and the rollback of 02 section 4.10).
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-15 at 07:13 UTC, after
-- the last run (06:00:00-06:11:35), as migration 20261015071358
-- "v2_fmt2_close".
--
-- Rollback: select cron.schedule('recupero-fmt2', '0 6 * * *',
--   'select public.chiedi_recupero_fmt2()');

select cron.unschedule('recupero-fmt2');
