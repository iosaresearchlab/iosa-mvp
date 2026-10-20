-- The nightly check, as one SQL statement. The scheduled task "IOSA check_run
-- notturno" (02:07 UTC) runs exactly this query, without the comments: keep
-- the two identical (owner decision 01/10/2026). tests/check_run.py applies
-- the same criteria to any day; tests/test_check_run.py holds the two to
-- the same verdicts. One row; verdict = 'PASS' or 'FAIL'. The day checked is
-- the UTC day that has just closed; to replay another day, replace the first
-- line (the d CTE) with: with d as (select date '<day>' as day),
--
-- A quota_stop is EXPECTED, and the verdict can be PASS, when all hold:
--   the census is complete; the run notes carry Google's 403; and the units
--   of the previous day's morning reprocess that fell in the same Pacific
--   quota day as this reading, plus this run's quota_total, reach 9,000.
--   While there is a backlog the 08:20 UTC reprocess spends quota of the same
--   Google day as the 23:59 UTC reading, so the reading can stop well below
--   the 9,900 brake; ripresa-iosa completes the records at 08:20 UTC.
-- FAIL only on: a quota_stop not expected; the previous day still waiting
--   (quota_stop or read_failed records left); read_failed > 0; an incomplete
--   census or a failed outcome; no run or more than one; slice errors; no
--   records; a Short record; malformed records (bad_records: a standard
--   record needs a baseline and a VPI, a not_computable, quota_stop or
--   read_failed one has no VPI); no units per channel in the notes; the
--   snapshot retention not run clean (02 section 3.1: no retention line, a
--   RETENTION FAILED line, or a snapshot day older than the 7-day window);
--   the database over 400 MB of the 500 MB free tier, Storage over 800 MB
--   of its 1 GB. After a missed reading the old reference stays one extra
--   night by design; that night fails here, which is the point.
-- Three corrections to the query first scheduled on 01/10, all toward the
-- owner's rule: an incomplete census fails the day by itself (it was read
-- only inside quota_stop_expected); a run with no previous-day pass in the
-- same quota day counts 0 units for it (the scalar subquery returned NULL,
-- which made the verdict FAIL however many units the run itself had spent:
-- a false FAIL); and Google's 403 is matched as the engine writes it
-- ("baselines stopped: 403 on ..."), not as any "403" in the notes, which a
-- slice seed or a count can contain.
-- Measured on 2026-09-30 as of the 02:07 UTC check of 01/10
-- (tests/check_run_replay_20260930.sql, read-only): 1,205 quota_stop, the
-- 403 in the notes, 5,695 units of the 29/09 morning pass + 4,155 of the
-- reading = 9,850 >= 9,000: quota_stop_expected, verdict PASS.
with d as (select (now() at time zone 'utc')::date - 1 as day),
r as (select i.* from ingest_run i, d where i.day = d.day),
r1 as (select i.* from ingest_run i, d where i.day = d.day - 1),
p as (select format, baseline_rule, baseline_score, vpi_ratio
        from posts, d where entered_on = d.day and method_version = 'v2'),
c as (select
  (select count(*) from r) as runs, (select quota_total from r) as quota_total,
  (select outcome from r) as outcome, (select slices_error from r) as slices_error,
  (select finished_at is not null from r) as finished, (select count(*) from p) as records,
  (select count(*) from p where baseline_rule = 'quota_stop') as quota_stop,
  (select count(*) from p where baseline_rule = 'read_failed') as read_failed,
  (select count(*) from p where baseline_rule in ('quota_stop', 'read_failed')) as waiting_for_reprocess,
  (select census_complete from r) as census_complete,
  (select coalesce(notes, '') like '%baselines stopped: 403 on %' from r) as stopped_by_google_403,
  coalesce((select substring(r1.notes from '.*[^0-9]([0-9]+) units in this pass')::int
     from r1, r
    where r1.reprocessed_at is not null
      and (r1.reprocessed_at at time zone 'America/Los_Angeles')::date
        = (r.started_at at time zone 'America/Los_Angeles')::date), 0) as same_quota_day_pass_units,
  (select count(*) from posts, d where entered_on = d.day - 1 and method_version = 'v2'
      and baseline_rule in ('quota_stop', 'read_failed')) as previous_day_still_waiting,
  (select count(*) from p where not (
      (baseline_rule = 'standard' and baseline_score is not null and vpi_ratio is not null)
      or (baseline_rule in ('not_computable', 'quota_stop', 'read_failed') and vpi_ratio is null))) as bad_records,
  (select count(*) from p where format = 'SHORT') as shorts,
  (select coalesce(notes, '') like '%per channel%' from r) as units_in_notes,
  (select coalesce(notes, '') like '%retention: kept from%' from r) as retention_ran,
  (select coalesce(notes, '') like '%RETENTION FAILED%' from r) as retention_failed,
  (select substring(notes from '.*slowest query ([0-9]+) ms')::int from r) as slowest_query_ms,
  (select count(distinct s.day) from trend_snapshot s, d where s.day < d.day - 6) as stale_snapshot_days,
  (select coalesce(sum((metadata->>'size')::bigint), 0) from storage.objects) as storage_bytes,
  pg_database_size(current_database()) as db_bytes),
e as (select c.*,
  (quota_stop > 0 and census_complete and stopped_by_google_403
     and same_quota_day_pass_units + coalesce(quota_total, 0) >= 9000) as quota_stop_expected
  from c)
select (select day from d) as day,
  case when runs = 1 and finished and quota_total <= 9900 and outcome = 'ok'
       and census_complete and slices_error = 0 and records > 0 and read_failed = 0
       and (quota_stop = 0 or quota_stop_expected)
       and previous_day_still_waiting = 0
       and bad_records = 0 and shorts = 0 and units_in_notes
       and retention_ran and not retention_failed and stale_snapshot_days = 0
       and coalesce(slowest_query_ms, 0) < 2000
       and db_bytes < 400 * 1024 * 1024 and storage_bytes < 800 * 1024 * 1024
  then 'PASS' else 'FAIL' end as verdict,
  e.*, pg_size_pretty(db_bytes) as db_size, pg_size_pretty(storage_bytes) as storage_size,
  (select notes from r) as notes
from e;
