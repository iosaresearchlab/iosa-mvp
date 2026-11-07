-- INC-2: the morning pass also finishes a reading that died. On 6/11/2026 a
-- Render restart for memory (00:39 UTC) killed the reading of 5/11 after its
-- census, records, daily views and exits, during retention: the process
-- never wrote its end, so ingest_run kept finished_at and outcome null. The
-- 00:30 second attempt had found it still running; the 08:20 pass only
-- looked at rows with a finish. Now a row with a complete census, no finish
-- and a start more than 2 hours old (the longest finished reading since 7/10
-- took 52 minutes) is a reading that died, and reprocess_day finishes it
-- from its snapshot like a failed one. Owner rule: no night is unrecoverable.

create or replace function public.ripresa_se_serve()
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
     where r.day = giorno and r.census_complete
       and ((r.finished_at is not null
             and (r.outcome = 'failed'
                  or exists (select 1 from posts p
                              where p.entered_on = r.day and p.method_version = 'v2'
                                and p.baseline_rule in ('quota_stop', 'read_failed'))))
            or (r.finished_at is null and r.started_at < now() - interval '2 hours'))) then
    return public.chiedi_ripresa_di_un_giorno(giorno);
  end if;
  return null;
end;
$function$;

revoke all on function public.ripresa_se_serve() from public, anon, authenticated, service_role;
