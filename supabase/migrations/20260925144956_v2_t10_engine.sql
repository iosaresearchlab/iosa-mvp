-- T-10 + GATE-1 decisions (docs/08-implementation-plan.md; Migert, 25/09):
-- what the v2 daily run needs from the database.
-- Sources: docs/01-methodology-protocol.md sections 2, 4, 7;
-- docs/02-technical-specification.md sections 3.1.1, 3.2, 3.3, 3.5, 4.3.
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-25 as migration
-- 20260925144956 "v2_t10_engine". Below this header, the exact SQL applied.
-- posts before = after: 28,917 rows, md5 of every column
-- b0335510f2e7f258563b7119e60edd64.
-- Rollback:
--   drop function public.tracked_of_day(date);
--   drop function public.apply_daily_views(date, jsonb);
--   re-apply 20260925133027 for close_exits_of_day() and entries_of_day(),
--     after re-creating day0_pending (empty: it never held data);
--   restore the previous posts_baseline_state (20260925132338);
--   the three NOT NULL are restored only if no row has a null in them.

-- 02 §3.1.1: the day-0 exclusion list excluded nothing once the reference
-- became the last complete reading. entries_of_day() without it, then drop.
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
                    where po.external_post_id = s.video_id);
$$;
drop table public.day0_pending;

-- 01 §2: a not_computable record has no VPI, so no level name and no colour.
-- 01 §7: channels without a handle (the "- Topic" Art Tracks) stay in the
-- index, flagged auto_generated_channel.
alter table public.posts alter column vpi_level_name drop not null;
alter table public.posts alter column vpi_color      drop not null;
alter table public.posts alter column author_handle  drop not null;

-- 02 §3.2: the level, its name and its colour exist exactly when the VPI does.
alter table public.posts drop constraint posts_baseline_state;
alter table public.posts add constraint posts_baseline_state check (
  coalesce(method_version = 'v1', false)
  or coalesce(baseline_rule = 'standard'
              and baseline_score is not null and vpi_ratio is not null
              and vpi_level is not null and vpi_level_name is not null
              and vpi_color is not null, false)
  or coalesce(baseline_rule = 'not_computable'
              and baseline_score is null and vpi_ratio is null
              and vpi_level is null and vpi_level_name is null
              and vpi_color is null, false)
);

-- The v2 records charting today: present in today's snapshot.
create or replace function public.tracked_of_day(d date)
returns table (post_id uuid, external_post_id text, entered_on date,
               baseline_score numeric, views numeric)
language sql stable
set search_path = public
as $$
  select po.id, po.external_post_id::text, po.entered_on, po.baseline_score, s.views
  from posts po
  join trend_snapshot s on s.day = d and s.video_id = po.external_post_id
  where po.method_version = 'v2' and po.status = 'ACTIVE';
$$;

-- One day of the series, computed by the engine (the scale lives only in
-- vpi_core.py): rows = [{post_id, views, vpi_ratio, vpi_level,
-- vpi_level_name, vpi_color}]. Writes post_daily with day_index, and on
-- posts the current views and VPI and the peak observed (01 §4.1).
create or replace function public.apply_daily_views(d date, rows jsonb)
returns int
language plpgsql
set search_path = public
as $$
declare
  n int;
begin
  with r as (
    select (x->>'post_id')::uuid as post_id, (x->>'views')::numeric as views,
           (x->>'vpi_ratio')::numeric as vpi_ratio, (x->>'vpi_level')::int as vpi_level,
           x->>'vpi_level_name' as vpi_level_name, x->>'vpi_color' as vpi_color
    from jsonb_array_elements(rows) x
  ), daily as (
    insert into post_daily (post_id, day, day_index, views, vpi_ratio, vpi_level)
    select r.post_id, d, (d - po.entered_on) + 1, r.views, r.vpi_ratio, r.vpi_level
    from r join posts po on po.id = r.post_id
    where po.method_version = 'v2' and po.entered_on <= d
    on conflict (post_id, day) do update
      set views = excluded.views, vpi_ratio = excluded.vpi_ratio,
          vpi_level = excluded.vpi_level
    returning post_id
  )
  update posts po
     set engagement_score = r.views,
         vpi_ratio        = r.vpi_ratio,
         vpi_level        = r.vpi_level,
         vpi_level_name   = r.vpi_level_name,
         vpi_color        = r.vpi_color,
         vpi_max_on       = case when r.vpi_ratio is not null
                                  and (po.vpi_max is null or r.vpi_ratio > po.vpi_max)
                                 then d else po.vpi_max_on end,
         vpi_max          = case when r.vpi_ratio is not null
                                  and (po.vpi_max is null or r.vpi_ratio > po.vpi_max)
                                 then r.vpi_ratio else po.vpi_max end,
         views_max        = greatest(po.views_max, r.views)
    from r
   where po.id = r.post_id and po.id in (select post_id from daily);
  get diagnostics n = row_count;
  return n;
end
$$;

-- 4.3, as applied in 20260925133027, plus views_final: the last views
-- actually observed.
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
                          where pd.post_id = po.id),
         views_final   = (select pd.views from post_daily pd
                          where pd.post_id = po.id
                          order by pd.day desc limit 1)
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
revoke execute on function public.tracked_of_day(date)           from public, anon, authenticated;
revoke execute on function public.apply_daily_views(date, jsonb) from public, anon, authenticated;
grant  execute on function public.tracked_of_day(date)           to service_role;
grant  execute on function public.apply_daily_views(date, jsonb) to service_role;
