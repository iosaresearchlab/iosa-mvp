-- V1-SLIM, step 1: a service-role-only helper to export posts_v1 and
-- posts_v1_links, every column, one to_jsonb(row)::text line per row, with a
-- sort key. Used once, from the device, to write the archive files before the
-- reduction; dropped by the next migration (v2_v1slim_reduce).
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-28 as migration
-- 20260928133017 "v2_v1slim_export"; below this header, the exact SQL applied.

create function public.v1_archive_export(p_table text)
returns table(k text, line text)
language plpgsql stable security definer
set search_path = public
as $f$
begin
  if p_table = 'posts_v1' then
    return query select v.id::text, to_jsonb(v)::text from public.posts_v1 v;
  elsif p_table = 'posts_v1_links' then
    return query select l.source_table || ':' || l.source_id::text, to_jsonb(l)::text
                 from public.posts_v1_links l;
  else
    raise exception 'unknown table %', p_table;
  end if;
end
$f$;
revoke all on function public.v1_archive_export(text) from public, anon, authenticated;
grant execute on function public.v1_archive_export(text) to service_role;
