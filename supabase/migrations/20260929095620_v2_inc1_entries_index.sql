-- INC-1: the reading of 2026-09-28 failed at 00:00:08 UTC. The census was
-- complete (412 slices ok, 30 404, 0 errors, 27,455 videos in the snapshot);
-- the first page of entries_of_day() was then cancelled by the API role's
-- 8 s statement timeout (57014). Postgres auto-analyzed trend_snapshot at
-- 00:00:17, nine seconds later; the same call takes 0.66 s today.
--
-- Cause: the anti-join "not exists (select 1 from posts where
-- external_post_id = s.video_id)" has no index to use. When the planner
-- misestimates the rows left after the first anti-join it picks a nested
-- loop with a sequential scan of posts for every snapshot row: reproduced
-- locally at production sizes (tests/repro_entries_timeout.py), 64 million
-- rows compared, 6 s; the cost grows with posts, which is never trimmed.
--
-- Fix, no data touched:
--   1. an index on posts(external_post_id): the anti-join becomes an index
--      probe whatever the estimate (repro: 0.02-0.05 s in every state);
--   2. analyze_snapshot(): the engine refreshes trend_snapshot's statistics
--      right after writing the day's snapshot, before entries_of_day, so the
--      plan is made on the rows just written. Service role only.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-29 as migration
-- 20260929095620 "v2_inc1_entries_index"; below this header, the exact SQL
-- applied. After: the entry query for 2026-09-28 uses the index (merge anti
-- join), 97 ms.
--
-- Rollback: drop index public.posts_external_post_id_idx;
-- drop function public.analyze_snapshot().

create index if not exists posts_external_post_id_idx on public.posts (external_post_id);

create function public.analyze_snapshot()
returns void
language plpgsql security definer
set search_path = public
as $f$
begin
  analyze public.trend_snapshot;
end
$f$;
revoke all on function public.analyze_snapshot() from public, anon, authenticated;
grant execute on function public.analyze_snapshot() to service_role;
