-- RET-1: rolling 7-day retention of trend_snapshot (02 section 3.1).
-- Owner decision 28/09/2026: keep the last 7 reading days, drop the rest, no
-- exception for day 0. Snapshots are working data, not an archive: once the
-- first day has been analysed and the system is in steady state, day 0 is a
-- day like any other.
--
-- 1. permanent existed only to exempt day 0 from the retention delete
--    (read by nothing else: census.save_snapshot wrote it, the retention SQL
--    in 02 section 3.1 filtered on it, tests asserted it). Dropped.
-- 2. A private bucket, 'archivio', for the files written before a delete.
--    Not public: nothing public reads trend_snapshot, nothing public reads
--    its archive. 50 MB per file, the free-tier upload ceiling.
-- 3. Three functions for the service role only:
--      snapshot_days_before(d)   the snapshot days older than d;
--      snapshot_export(d)        one day's rows, one jsonb text line each;
--      purge_snapshot_day(...)   deletes one day, and only when the caller
--                                shows the row count and the md5 of the
--                                file it read back from Storage, and they
--                                match the rows in the table.
--    The order is fixed by these signatures: export, read the file back,
--    verify, delete. purge_snapshot_day refuses a day inside the window
--    (checked against the caller's window and against the database clock)
--    and refuses the reference, the last complete reading, whatever its age.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-28 as migration
-- 20260928131932 "v2_ret1_snapshot_retention"; below this header, the exact
-- SQL applied.
--
-- Rollback: alter table public.trend_snapshot add column permanent boolean
-- not null default false; drop the three functions; the bucket may stay.

alter table public.trend_snapshot drop column permanent;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('archivio', 'archivio', false, 52428800, array['application/gzip'])
on conflict (id) do nothing;

create function public.snapshot_days_before(p_day date)
returns table(day date)
language sql stable security definer
set search_path = public
as $f$
  select distinct s.day from public.trend_snapshot s where s.day < p_day order by 1
$f$;

create function public.snapshot_export(p_day date)
returns table(video_id text, line text)
language sql stable security definer
set search_path = public
as $f$
  select s.video_id, to_jsonb(s)::text from public.trend_snapshot s where s.day = p_day
$f$;

create function public.purge_snapshot_day(p_day date, p_keep_from date,
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
  select max(r.day) into ref from public.ingest_run r where r.outcome = 'ok';
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

revoke all on function public.snapshot_days_before(date) from public, anon, authenticated;
revoke all on function public.snapshot_export(date) from public, anon, authenticated;
revoke all on function public.purge_snapshot_day(date, date, bigint, text) from public, anon, authenticated;
grant execute on function public.snapshot_days_before(date) to service_role;
grant execute on function public.snapshot_export(date) to service_role;
grant execute on function public.purge_snapshot_day(date, date, bigint, text) to service_role;
