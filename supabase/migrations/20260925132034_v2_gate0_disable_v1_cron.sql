-- GATE-0 decision (Migert, 25/09/2026): switch off the v1 ingestion trigger.
-- Any row written by the v1 engine would contaminate the v2 population, and
-- day 0 must be the true start of the series. Replaced at T-14.
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-25 as migration
-- 20260925132034 "v2_gate0_disable_v1_cron". Below this header, the exact
-- SQL applied.
-- Rollback: select cron.alter_job((select jobid from cron.job where jobname = 'ingestione-iosa'), active := true);
select cron.alter_job((select jobid from cron.job where jobname = 'ingestione-iosa'), active := false);
