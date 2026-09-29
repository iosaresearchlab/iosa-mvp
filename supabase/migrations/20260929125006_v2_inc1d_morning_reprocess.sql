-- INC-1d: the morning pass. At 08:20 UTC, after the YouTube quota has reset
-- (midnight Pacific: 07:00 UTC in summer, 08:00 UTC in winter; 08:20 is
-- after both), reprocess_day finishes yesterday when it needs it: a
-- complete census whose processing failed (and was not resumed at 00:30),
-- or records written without a VPI (quota_stop, read_failed). Nothing to
-- do, nothing called. Owner decision 29/09/2026: no night is unrecoverable.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-29 as migration
-- 20260929125006 "v2_inc1d_morning_reprocess"; below this header, the exact SQL applied.

create function public.ripresa_se_serve()
returns bigint
language plpgsql
security definer
set search_path = public
as $function$
declare
  giorno date := (now() at time zone 'utc')::date - 1;
begin
  if exists (
    select 1 from ingest_run r
     where r.day = giorno and r.census_complete and r.finished_at is not null
       and (r.outcome = 'failed'
            or exists (select 1 from posts p
                        where p.entered_on = r.day and p.method_version = 'v2'
                          and p.baseline_rule in ('quota_stop', 'read_failed')))) then
    return public.chiedi_ripresa_di_un_giorno(giorno);
  end if;
  return null;
end;
$function$;

revoke all on function public.ripresa_se_serve() from public, anon, authenticated, service_role;

select cron.schedule('ripresa-iosa', '20 8 * * *', 'select public.ripresa_se_serve()');
