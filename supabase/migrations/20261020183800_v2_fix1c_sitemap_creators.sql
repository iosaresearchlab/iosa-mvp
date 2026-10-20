-- FIX-1c (20/10/2026): measured, not used. The sitemap's creators (two or
-- more records in or out of Most Popular) aggregated in the database instead
-- of reading every record's author_handle (46,739 rows, 1.7 MB over the API).
-- Same set as the page's own count (7,203 = 7,203 handles, 20/10 18:38 UTC),
-- 266 kB instead of 1.7 MB, but no faster as anon: the first call after a
-- pause timed out (500 at 3.7 s), the next four took 0.46-1.2 s, the plain
-- read 0.46 s. The build failures are handled by retrying the read during
-- the build (frontend/src/lib/supabase-server.ts, leggi()); the sitemap
-- keeps its plain read. Kept because it was applied to production; dropping
-- it is the owner's call.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-20 at 18:38 UTC as
-- migration 20261020183800 "v2_fix1c_sitemap_creators".
--
-- Rollback: drop function public.sitemap_creators(date, int).

create or replace function public.sitemap_creators(p_floor date, p_min int)
returns table (author_handle text)
language sql
stable
security invoker
set search_path = public
as $f$
  select r.author_handle
    from public_records r
   where r.method_version = 'v2'
     and r.entered_on >= p_floor
     and r.author_handle is not null
   group by r.author_handle
  having count(*) >= p_min
$f$;
revoke all on function public.sitemap_creators(date, int) from public;
grant execute on function public.sitemap_creators(date, int) to anon, authenticated, service_role;
