-- tests/check_run.sql replayed, read-only, on 2026-09-30 as the 02:07 UTC
-- check of 01/10 saw it: before the 08:20 UTC morning pass of 01/10, which
-- completed the 1,205 quota_stop records (posts.reprocessed_at >= 08:20) and
-- added its 3,818 units and its notes to the run of 30/09. Two CTEs shadow
-- posts and ingest_run with that earlier state; nothing is written. The rest
-- is tests/check_run.sql as it stands, with the day fixed.
-- Result on production, 01/10/2026: verdict PASS; quota_stop 1205,
-- quota_stop_expected true, stopped_by_google_403 true,
-- same_quota_day_pass_units 5695 + quota_total 4155 = 9850 >= 9000,
-- previous_day_still_waiting 0, read_failed 0, bad_records 0, records 2080,
-- db 110 MB, storage 11 MB.
with d as (select date '2026-09-30' as day),
posts as (select x.method_version, x.entered_on, x.format,
   case when x.reprocessed_at >= '2026-10-01 08:20:00+00' and x.entered_on = '2026-09-30'
        then 'quota_stop' else x.baseline_rule end as baseline_rule,
   case when x.reprocessed_at >= '2026-10-01 08:20:00+00' and x.entered_on = '2026-09-30'
        then null else x.baseline_score end as baseline_score,
   case when x.reprocessed_at >= '2026-10-01 08:20:00+00' and x.entered_on = '2026-09-30'
        then null else x.vpi_ratio end as vpi_ratio
   from public.posts x),
ingest_run as (select i.id, i.day, i.started_at, i.outcome, i.slices_error, i.census_complete,
   case when i.day = '2026-09-30' then i.started_at + interval '17 minutes 18 seconds'
        else i.finished_at end as finished_at,
   case when i.day = '2026-09-30' then null else i.reprocessed_at end as reprocessed_at,
   case when i.day = '2026-09-30'
        then i.quota_total - substring(i.notes from '.*[^0-9]([0-9]+) units in this pass')::int
        else i.quota_total end as quota_total,
   case when i.day = '2026-09-30' then substring(i.notes from '^(.*?); reprocessed at ')
        else i.notes end as notes
   from public.ingest_run i),
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
       and db_bytes < 400 * 1024 * 1024 and storage_bytes < 800 * 1024 * 1024
  then 'PASS' else 'FAIL' end as verdict,
  e.*, pg_size_pretty(db_bytes) as db_size, pg_size_pretty(storage_bytes) as storage_size,
  (select notes from r) as notes
from e;
