-- FIX-1b (23/10/2026): the day's snapshot is exported in keyset pages.
-- snapshot_export(d) returns the whole day (26,579 rows, 10 MB of JSON over
-- the API) and PostgREST runs it in full for every page the caller asks: the
-- retention step of the reading made 27 calls of 1,000 rows each night, each
-- turning all 26.5K rows into jsonb and sorting them (22/10: 17 s of calls),
-- and one call for the whole day took 1.4-3.3 s over the API (23/10, network
-- included), over the run's 2,000 ms bound. This one returns the rows after
-- p_after in video_id order, at most p_limit, through the primary key
-- (day, video_id): each page reads only its own rows.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-23 at 11:54 UTC as
-- migration 20261023115400 "v2_fix1b_snapshot_export_after".
--
-- Rollback: drop function public.snapshot_export_after(date, text, int).

create or replace function public.snapshot_export_after(p_day date, p_after text, p_limit int)
returns table(video_id text, line text)
language sql stable security definer
set search_path = public
as $f$
  select s.video_id, to_jsonb(s)::text
    from public.trend_snapshot s
   where s.day = p_day and s.video_id > p_after
   order by s.video_id
   limit p_limit
$f$;
revoke all on function public.snapshot_export_after(date, text, int) from public, anon, authenticated;
grant execute on function public.snapshot_export_after(date, text, int) to service_role;
