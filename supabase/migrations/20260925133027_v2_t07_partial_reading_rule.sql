-- T-07 (docs/08-implementation-plan.md): the partial-reading rule.
-- Source: docs/01-methodology-protocol.md section 4 ("a partial reading
-- observes presence but not absence"); docs/02-technical-specification.md
-- sections 3.5 and 4.3.
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-25 as migration
-- 20260925133027 "v2_t07_partial_reading_rule". Below this header, the exact
-- SQL applied.
-- Rollback: re-apply 20260925131159 for entries_of_day();
--   drop function public.close_exits_of_day(date);

-- 3.5: the reference is the most recent day whose run completed. A partial
-- reading cannot be the reference for the following day.
create or replace function public.entries_of_day(d date)
returns table (video_id text, gap_days int, entry_certain boolean)
language sql stable
set search_path = public
as $$
  with previous as (
    select max(r.day) as pd from ingest_run r
    where r.day < d and r.outcome = 'ok'
  )
  select s.video_id,
         case when previous.pd = d - 1 then 0 else d - previous.pd end,
         previous.pd = d - 1
  from trend_snapshot s, previous
  where s.day = d
    and previous.pd is not null
    and not exists (select 1 from trend_snapshot p
                    where p.day = previous.pd and p.video_id = s.video_id)
    and not exists (select 1 from posts po
                    where po.external_post_id = s.video_id)
    and not exists (select 1 from day0_pending z
                    where z.video_id = s.video_id);
$$;

-- 4.3: close the v2 records absent from day d's snapshot. The caller runs
-- it only after a complete reading; the function refuses on its own when
-- the day's run is already known to be partial or failed, or when there is
-- no snapshot for the day (nothing was read, so nothing was observed
-- absent). left_on = the first complete reading in which the video was
-- absent; days_charting = the days it was actually observed (post_daily).
create or replace function public.close_exits_of_day(d date)
returns int
language plpgsql
set search_path = public
as $$
declare
  n int;
begin
  if exists (select 1 from ingest_run
             where day = d and outcome in ('partial', 'failed')) then
    return 0;
  end if;
  if not exists (select 1 from trend_snapshot where day = d) then
    return 0;
  end if;
  update posts po
     set status        = 'CLOSED',
         left_on       = d,
         days_charting = (select count(*) from post_daily pd
                          where pd.post_id = po.id)
   where po.method_version = 'v2'
     and po.status = 'ACTIVE'
     and po.entered_on < d
     and not exists (select 1 from trend_snapshot s
                     where s.day = d and s.video_id = po.external_post_id);
  get diagnostics n = row_count;
  return n;
end
$$;

-- Written by the backend with the service role only.
revoke execute on function public.close_exits_of_day(date) from public, anon, authenticated;
grant execute on function public.close_exits_of_day(date) to service_role;
