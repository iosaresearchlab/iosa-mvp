-- T-06 (docs/08-implementation-plan.md): entries_of_day(), the day-0
-- archive and exclusion list, and the archiving of the v1 records.
-- Source: docs/02-technical-specification.md sections 3.1, 3.1.1, 3.5, 3.6;
-- docs/01-methodology-protocol.md sections 1 and 4.
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-25 as migration
-- 20260925131159 "v2_t06_entries_of_day". Below this header, the exact SQL
-- applied.
-- Rollback:
--   drop function public.entries_of_day(date);
--   drop table public.day0_pending;
--   alter table public.trend_snapshot drop column permanent;
--   update public.posts set method_version = 'v2' where method_version = 'v1';

-- 3.1: day 0's snapshot is a permanent archive, never deleted.
alter table public.trend_snapshot
  add column permanent boolean not null default false;

-- 3.1.1: day-0 IDs not yet observed absent. Drains; never touches the archive.
create table public.day0_pending (
  video_id text primary key
);
alter table public.day0_pending enable row level security;
-- no policy: only the service role writes here

-- 3.5: entries of a day. Compared against the most recent existing snapshot,
-- never "yesterday" by definition. No previous snapshot -> no entries.
create or replace function public.entries_of_day(d date)
returns table (video_id text, gap_days int, entry_certain boolean)
language sql stable
set search_path = public
as $$
  with previous as (
    select max(day) as pd from trend_snapshot where day < d
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

-- 3.6: every record written before v2 is a v1 record.
update public.posts set method_version = 'v1' where entered_on is null;
