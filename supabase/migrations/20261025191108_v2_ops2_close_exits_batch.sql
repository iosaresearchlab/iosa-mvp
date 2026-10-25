-- OPS-2 (25/10/2026): the day's exits are closed in batches.
-- close_exits_of_day(d) closes every exit of the day in one statement: about
-- 1,900-2,100 records a night, each a non-HOT update of posts (status and
-- left_on are indexed; posts has 16 indexes) plus two reads of post_daily.
-- The statement ran 7,172 ms on 21/10 and was cancelled at 8 s on 19/10; on
-- 25/10 the reprocess of 24/10 took 4,402 ms for 1,902 exits, over the
-- nightly check's 2,000 ms bound. The same cut as apply_daily_views (OPS-2,
-- e6c25e8): this function closes at most lim exits per call, the engine
-- calls it until a call closes fewer than lim (census.close_exits, batches of
-- CLOSE_BATCH). Same guards, same exits, same columns: only the size of a
-- statement changes. close_exits_of_day(d) stays, unchanged.
-- Measured on production 25/10 with explain analyze, inside a block that
-- rolls back, after reopening the 1,902 exits of 24/10: whole-day statement
-- 5,750, 964 and 716 ms; one batch of 200: 1,320, 105 and 107 ms (the first
-- run of each set reads cold pages). The whole day through this function in
-- the same block: 10 calls (9 x 200 + 102), 67-603 ms each, 1,902 closed, the
-- same count as the whole-day statement.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-25 at 19:11 UTC as
-- migration 20261025191108 "v2_ops2_close_exits_batch".
--
-- Rollback: drop function public.close_exits_of_day_batch(date, int).

create or replace function public.close_exits_of_day_batch(d date, lim int)
returns integer
language plpgsql
set search_path = public
as $function$
declare
  n int;
begin
  if exists (select 1 from ingest_run
             where day = d and census_complete is not true) then
    return 0;
  end if;
  if not exists (select 1 from trend_snapshot where day = d) then
    return 0;
  end if;
  update posts po
     set status        = 'CLOSED',
         left_on       = d,
         days_charting = (select count(*) from post_daily pd
                          where pd.post_id = po.id),
         views_final   = (select pd.views from post_daily pd
                          where pd.post_id = po.id
                          order by pd.day desc limit 1)
   where po.id in (
           select a.id from posts a
            where a.method_version = 'v2'
              and a.status = 'ACTIVE'
              and a.entered_on < d
              and not exists (select 1 from trend_snapshot s
                              where s.day = d and s.video_id = a.external_post_id)
            limit lim);
  get diagnostics n = row_count;
  return n;
end
$function$;

revoke execute on function public.close_exits_of_day_batch(date, int) from public, anon, authenticated;
grant execute on function public.close_exits_of_day_batch(date, int) to service_role;
