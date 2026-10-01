-- UI-2 (01/10/2026): the home shows "Last reading: <day>, 23:59 UTC" instead
-- of "NODE STATUS: ACTIVE" and a LIVE pulse. <day> is the latest day whose
-- census is complete (ingest_run.census_complete, the one rule that makes a
-- day the reference). ingest_run is readable by the service role only; this
-- returns the one date and nothing else. Granted to the public roles.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-01 as migration
-- 20261001205246 "v2_ui2_last_reading"; below this header, the exact SQL
-- applied. Checked after, as anon: 2026-09-30.
--
-- Rollback: drop function public.last_complete_reading();

create or replace function public.last_complete_reading()
returns date
language sql stable security definer
set search_path = public
as $f$
  select max(day) from public.ingest_run where census_complete
$f$;
revoke all on function public.last_complete_reading() from public;
grant execute on function public.last_complete_reading() to anon, authenticated, service_role;
