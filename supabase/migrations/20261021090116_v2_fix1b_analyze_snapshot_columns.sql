-- FIX-1b, reopened 21/10/2026: analyze_snapshot() was the slowest call of the
-- reading of 20/10 (run notes: "slowest query 5424 ms (rpc analyze_snapshot,
-- 252 calls)"), against the nightly bound of 2,000 ms and the API roles' 8 s
-- statement timeout. It ran a whole-table ANALYZE of trend_snapshot (186K
-- rows, 55 MB heap, 7 days kept): statistics for every column, the three
-- text arrays (countries, categories, slices) included. What it exists for
-- (INC-1, migration 20260929095620) is the plan of the day's entry query,
-- which reads trend_snapshot only by (day, video_id); autoanalyze keeps the
-- other columns.
--
-- Measured 21/10 ~09:00 UTC in SQL, 3 runs each, alternating: whole table
-- 484-5,069 ms (the first, cold, 5,069); (day, video_id) 87-393 ms. Over the
-- API as service_role after the change: 432-739 ms (5 calls, network
-- included). The day's entry query keeps its plan (direct explain analyze of
-- entries_of_day's body for 20/10: index-only scans, 167 ms).
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-21 at 09:01 UTC as
-- migration 20261021090116 "v2_fix1b_analyze_snapshot_columns".
--
-- Rollback: re-create the function with `analyze public.trend_snapshot;`
-- (migration 20260929095620).

create or replace function public.analyze_snapshot()
returns void
language plpgsql security definer
set search_path = public
as $f$
begin
  analyze public.trend_snapshot (day, video_id);
end
$f$;
revoke all on function public.analyze_snapshot() from public, anon, authenticated;
grant execute on function public.analyze_snapshot() to service_role;
