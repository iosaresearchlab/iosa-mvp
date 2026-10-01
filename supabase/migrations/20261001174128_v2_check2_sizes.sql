-- CHECK-2 (01/10/2026): the database and Storage sizes for tests/check_run.py,
-- which reads production through the REST API and cannot run the SQL of
-- tests/check_run.sql. Same figures as that query: pg_database_size and the
-- sum of storage.objects metadata sizes. Service role only.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-01 as migration
-- 20261001174128 "v2_check2_sizes"; below this header, the exact SQL applied.
-- Checked after: anon cannot execute it, service_role can; 114,855,059 and
-- 11,589,405 bytes.
--
-- Rollback: drop function public.check_run_sizes();

create or replace function public.check_run_sizes()
returns table(db_bytes bigint, storage_bytes bigint)
language sql stable security definer
set search_path = public, storage
as $f$
  select pg_database_size(current_database())::bigint,
         (select coalesce(sum((o.metadata->>'size')::bigint), 0) from storage.objects o)::bigint
$f$;
revoke all on function public.check_run_sizes() from public, anon, authenticated;
grant execute on function public.check_run_sizes() to service_role;
