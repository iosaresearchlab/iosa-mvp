-- T-17: row counts and bytes per table, for the day-1 audit (tests/audit_day1.py).
-- Read-only, service role only.
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-27 as migration
-- 20260927154303 "v2_t17_audit_sizes"; the SQL below is exactly what ran.
-- Rollback: drop function public.audit_table_sizes();
create function public.audit_table_sizes()
returns table("table" text, rows bigint, bytes bigint)
language plpgsql stable security definer
set search_path = public
as $f$
declare t text;
begin
  foreach t in array array['posts', 'post_daily', 'trend_snapshot', 'channel_inventory',
                           'ingest_run', 'posts_v1'] loop
    "table" := t;
    execute format('select count(*) from public.%I', t) into rows;
    bytes := pg_total_relation_size(format('public.%I', t)::regclass);
    return next;
  end loop;
end
$f$;
revoke all on function public.audit_table_sizes() from public, anon, authenticated;
grant execute on function public.audit_table_sizes() to service_role;
