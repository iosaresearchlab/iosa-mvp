-- INC-1b: a reading whose chart census is complete is a valid reference and
-- a valid starting point for reprocessing, whatever happened after it
-- (owner decision 29/09/2026). The same split made on 27/09 for the quota
-- brake (census completeness vs baseline completeness), extended to a
-- crash: outcome no longer decides the reference, census_complete does.
--
--   ingest_run.census_complete  true once the census of the day is complete
--                               and its snapshot written; written by the
--                               engine right after the snapshot, before any
--                               processing, so a crash cannot erase it.
--   ingest_run.reprocessed_at   when reprocess_day finished the day.
--   posts.reprocessed_at        set on records written or completed by
--                               reprocess_day: their baseline was read late,
--                               baseline_computed_at says exactly when.
--
-- Backfill: every 'ok' day; and 2026-09-28, whose census was complete
-- (412 slices ok + 30 at 404 = 442, 0 errors, 27,455 videos = the rows of
-- its snapshot) and whose processing failed (INC-1). The condition is
-- checked here, not assumed.
--
-- Functions:
--   entries_of_day, purge_snapshot_day  reference = last complete census;
--   close_exits_of_day  refuses a day whose census is not complete (was:
--                       refuses a partial or failed outcome);
--   records_of_day(d)   the day's v2 records, for reprocess_day;
--   complete_baselines(d, rows)  a baseline for a record written without
--                       one (quota_stop, read_failed), never for any other.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-29 as migration
-- 20260929123856 "v2_inc1b_census_reference"; below this header, the exact
-- SQL applied. After: 25, 26, 27/09 census_complete (ok); 28/09
-- census_complete with outcome failed, the condition met.

alter table public.ingest_run add column census_complete boolean;
alter table public.ingest_run add column reprocessed_at timestamptz;
alter table public.posts add column reprocessed_at timestamptz;

update public.ingest_run set census_complete = true where outcome = 'ok';
update public.ingest_run r set census_complete = true
 where r.day = date '2026-09-28' and r.outcome = 'failed'
   and r.slices_error = 0 and r.slices_ok + r.slices_404 = 442
   and r.videos_seen = (select count(*) from public.trend_snapshot s where s.day = r.day);
update public.ingest_run set census_complete = false where census_complete is null and finished_at is not null;

create or replace function public.entries_of_day(d date)
returns table(video_id text, gap_days integer, entry_certain boolean)
language sql stable
set search_path = public
as $function$
  with previous as (
    select max(r.day) as pd from ingest_run r
    where r.day < d and r.census_complete
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
$function$;

create or replace function public.close_exits_of_day(d date)
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
   where po.method_version = 'v2'
     and po.status = 'ACTIVE'
     and po.entered_on < d
     and not exists (select 1 from trend_snapshot s
                     where s.day = d and s.video_id = po.external_post_id);
  get diagnostics n = row_count;
  return n;
end
$function$;

create or replace function public.purge_snapshot_day(p_day date, p_keep_from date,
                                                     p_rows bigint, p_md5 text)
returns bigint
language plpgsql security definer
set search_path = public
as $f$
declare
  n bigint; h text; ref date;
begin
  if p_day >= p_keep_from
     or p_day >= (now() at time zone 'utc')::date - 6 then
    raise exception 'purge refused: % is inside the 7-day window', p_day;
  end if;
  select max(r.day) into ref from public.ingest_run r where r.census_complete;
  if ref is null or p_day >= ref then
    raise exception 'purge refused: % is not older than the reference (%)', p_day, ref;
  end if;
  select count(*), md5(string_agg(to_jsonb(s)::text, '|' order by s.video_id))
    into n, h from public.trend_snapshot s where s.day = p_day;
  if n = 0 or n <> p_rows or h is distinct from p_md5 then
    raise exception 'purge refused: % has % rows md5 %, the archive % rows md5 %',
      p_day, n, h, p_rows, p_md5;
  end if;
  delete from public.trend_snapshot where day = p_day;
  return n;
end
$f$;

create function public.records_of_day(d date)
returns table(post_id uuid, external_post_id text, channel_id text, format text,
              created_at timestamptz, baseline_rule text)
language sql stable
set search_path = public
as $f$
  select po.id, po.external_post_id::text, po.channel_id, po.format, po.created_at, po.baseline_rule
  from posts po where po.method_version = 'v2' and po.entered_on = d
$f$;

create function public.complete_baselines(d date, rows jsonb)
returns integer
language plpgsql
set search_path = public
as $f$
declare
  n int;
begin
  update posts po
     set baseline_score       = (x->>'baseline_score')::numeric,
         baseline_rule        = x->>'baseline_rule',
         baseline_samples     = (x->>'baseline_samples')::int,
         baseline_span_days   = (x->>'baseline_span_days')::numeric,
         baseline_video_ids   = array(select jsonb_array_elements_text(coalesce(x->'baseline_video_ids', '[]'))),
         baseline_computed_at = (x->>'baseline_computed_at')::timestamptz,
         reprocessed_at       = (x->>'reprocessed_at')::timestamptz,
         vpi_ratio            = (x->>'vpi_ratio')::numeric,
         vpi_level            = (x->>'vpi_level')::int,
         vpi_level_name       = x->>'vpi_level_name',
         vpi_color            = x->>'vpi_color'
    from jsonb_array_elements(rows) x
   where po.id = (x->>'post_id')::uuid
     and po.method_version = 'v2' and po.entered_on = d
     and po.baseline_rule in ('quota_stop', 'read_failed');
  get diagnostics n = row_count;
  return n;
end
$f$;

revoke all on function public.records_of_day(date) from public, anon, authenticated;
revoke all on function public.complete_baselines(date, jsonb) from public, anon, authenticated;
grant execute on function public.records_of_day(date) to service_role;
grant execute on function public.complete_baselines(date, jsonb) to service_role;
