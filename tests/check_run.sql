-- The nightly check, as one SQL statement: the same criteria as
-- tests/check_run.py, for the scheduled task that runs without the device.
-- :day defaults to yesterday (UTC). One row; verdict = 'PASS' or 'FAIL'.
-- waiting_for_reprocess: the day's records without a VPI that reprocess_day
-- completes after the quota resets (the ripresa-iosa job, 08:20 UTC).
-- Also fails when the database passes 400 MB of the 500 MB free tier, when
-- Storage passes 800 MB of its 1 GB, and when the snapshot retention did not
-- run clean (02 section 3.1): no retention line in the notes, a RETENTION
-- FAILED line, or a snapshot day older than the 7-day window still in the
-- table. After a missed reading the old reference stays one extra night by
-- design; that night fails here, which is the point: a gap is reported.
with d as (select (now() at time zone 'utc')::date - 1 as day),
r as (select i.* from ingest_run i, d where i.day = d.day),
p as (select format, baseline_rule, baseline_score, vpi_ratio
        from posts, d where entered_on = d.day and method_version = 'v2'),
c as (select
  (select count(*) from r)                                             as runs,
  (select quota_total from r)                                          as quota_total,
  (select outcome from r)                                              as outcome,
  (select slices_error from r)                                         as slices_error,
  (select finished_at is not null from r)                              as finished,
  (select count(*) from p)                                             as records,
  (select count(*) from p where baseline_rule = 'quota_stop')          as quota_stop,
  (select count(*) from p where baseline_rule = 'read_failed')         as read_failed,
  (select count(*) from p where baseline_rule in ('quota_stop', 'read_failed')) as waiting_for_reprocess,
  (select census_complete from r)                                      as census_complete,
  (select count(*) from p where not ((baseline_rule = 'standard' and baseline_score is not null
                                      and vpi_ratio is not null)
                                     or (baseline_rule = 'not_computable' and vpi_ratio is null))) as bad_records,
  (select count(*) from p where format = 'SHORT')                      as shorts,
  (select coalesce(notes, '') like '%per channel%' from r)             as units_in_notes,
  (select coalesce(notes, '') like '%retention: kept from%' from r)    as retention_ran,
  (select coalesce(notes, '') like '%RETENTION FAILED%' from r)        as retention_failed,
  (select count(distinct s.day) from trend_snapshot s, d where s.day < d.day - 6) as stale_snapshot_days,
  (select coalesce(sum((metadata->>'size')::bigint), 0) from storage.objects) as storage_bytes,
  pg_database_size(current_database())                                 as db_bytes)
select (select day from d) as day,
       case when runs = 1 and finished and quota_total <= 9900 and outcome = 'ok'
                 and slices_error = 0 and records > 0 and quota_stop = 0
                 and bad_records = 0 and shorts = 0 and units_in_notes
                 and retention_ran and not retention_failed and stale_snapshot_days = 0
                 and db_bytes < 400 * 1024 * 1024 and storage_bytes < 800 * 1024 * 1024
            then 'PASS' else 'FAIL' end as verdict,
       c.*, pg_size_pretty(db_bytes) as db_size, pg_size_pretty(storage_bytes) as storage_size,
       (select notes from r) as notes
from c;
