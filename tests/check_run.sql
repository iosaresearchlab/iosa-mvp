-- The nightly check, as one SQL statement: the same criteria as
-- tests/check_run.py, for the scheduled task that runs without the device.
-- :day defaults to yesterday (UTC). One row; verdict = 'PASS' or 'FAIL'.
-- Also fails when the database passes 400 MB of the 500 MB free tier.
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
  (select count(*) from p where not ((baseline_rule = 'standard' and baseline_score is not null
                                      and vpi_ratio is not null)
                                     or (baseline_rule = 'not_computable' and vpi_ratio is null))) as bad_records,
  (select count(*) from p where format = 'SHORT')                      as shorts,
  (select coalesce(notes, '') like '%per channel%' from r)             as units_in_notes,
  pg_database_size(current_database())                                 as db_bytes)
select (select day from d) as day,
       case when runs = 1 and finished and quota_total <= 9500 and outcome = 'ok'
                 and slices_error = 0 and records > 0 and quota_stop = 0
                 and bad_records = 0 and shorts = 0 and units_in_notes
                 and db_bytes < 400 * 1024 * 1024
            then 'PASS' else 'FAIL' end as verdict,
       c.*, pg_size_pretty(db_bytes) as db_size,
       (select notes from r) as notes
from c;
