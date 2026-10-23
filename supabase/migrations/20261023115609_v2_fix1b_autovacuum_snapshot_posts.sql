-- FIX-1b (23/10/2026): vacuum trend_snapshot and posts at 5% dead rows
-- instead of 20%. Every night trend_snapshot gains ~27K rows and loses ~27K
-- (the purge), and the daily views update rewrites ~5-7K posts; at 20%
-- autovacuum ran about once a day, after the reading (last runs 22/10 01:13
-- UTC), so during the reading the visibility map of the new rows is unset
-- and the index-only scans of the entry and exit queries read the heap for
-- every row (explain of 22/10: 26,603 heap fetches on trend_snapshot, 5,350
-- on posts). Dead rows on 23/10: posts 9,567 (14%), trend_snapshot 26,793
-- (12.6%).
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-23 at 11:56 UTC as
-- migration 20261023115609 "v2_fix1b_autovacuum_snapshot_posts".
--
-- Rollback: alter table public.trend_snapshot reset (autovacuum_vacuum_scale_factor,
-- autovacuum_analyze_scale_factor); alter table public.posts reset
-- (autovacuum_vacuum_scale_factor).

alter table public.trend_snapshot set (autovacuum_vacuum_scale_factor = 0.05, autovacuum_analyze_scale_factor = 0.05);
alter table public.posts set (autovacuum_vacuum_scale_factor = 0.05);
