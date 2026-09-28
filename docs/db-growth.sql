-- Database growth and runway against the free tier (02 section 3.8).
-- Measured, not estimated: bytes per row = pg_total_relation_size / rows
-- (heap, toast and indexes); rows per day from the reading of :day.
--   posts              records opened that day (entered_on)
--   post_daily         rows written that day (one per active record)
--   channel_inventory  entering long-form channels not already in it
--   trend_snapshot     rows of that day; capped at 7 days by the retention
-- Runway: to 400 MiB (the nightly check's alarm) and 500 MiB (the limit),
-- snapshot growth counted only until the table holds 7 days.
-- Run with the reading day in the first line (2026-09-27 for the figures in 02).
with d as (select date '2026-09-27' as day),
t as (
  select 'posts' tbl, pg_total_relation_size('posts') bytes, (select count(*) from posts) n,
         (select count(*) from posts, d where entered_on = d.day) per_day
  union all select 'post_daily', pg_total_relation_size('post_daily'), (select count(*) from post_daily),
         (select count(*) from post_daily, d where post_daily.day = d.day)
  union all select 'channel_inventory', pg_total_relation_size('channel_inventory'),
         (select count(*) from channel_inventory),
         (select entering_long_channels - entering_long_in_inventory from ingest_run, d where ingest_run.day = d.day)
  union all select 'trend_snapshot', pg_total_relation_size('trend_snapshot'), (select count(*) from trend_snapshot),
         (select count(*) from trend_snapshot, d where trend_snapshot.day = d.day)
),
g as (select tbl, bytes, n, per_day, bytes::numeric / n as bpr, bytes::numeric / n * per_day / 1048576 as mib_day from t),
s as (select
  pg_database_size(current_database()) / 1048576.0 as db_mib,
  (select sum(mib_day) from g) as mib_day_now,
  (select sum(mib_day) from g where tbl <> 'trend_snapshot') as mib_day_capped,
  (select mib_day from g where tbl = 'posts') as mib_day_posts,
  greatest(0, 7 - (select count(distinct day) from trend_snapshot)) as snapshot_days_to_cap)
select g.tbl, g.n, g.per_day, round(g.bpr) as bytes_per_row, round(g.mib_day, 2) as mib_per_day,
       round(s.db_mib, 1) as db_mib, round(s.mib_day_now, 2) as mib_day_now,
       round(s.mib_day_capped, 2) as mib_day_after_cap, s.snapshot_days_to_cap,
       round((400 - s.db_mib - s.snapshot_days_to_cap * s.mib_day_now) / s.mib_day_capped
             + s.snapshot_days_to_cap, 0) as days_to_400,
       round((500 - s.db_mib - s.snapshot_days_to_cap * s.mib_day_now) / s.mib_day_capped
             + s.snapshot_days_to_cap, 0) as days_to_500,
       round((500 - s.db_mib) / s.mib_day_posts, 0) as days_to_500_posts_only,
       round(s.mib_day_posts * 365 / 1024, 2) as posts_gib_per_year
from g, s order by g.tbl;
