"""FIX-1i (20/10/2026): CI fails a migration that creates a table without the
GRANTs it needs (Supabase, from 30/10/2026: no default grants on new tables)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("check_grants", ROOT / "tests" / "check_grants.py")
check_grants = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_grants)


def test_the_real_migrations_pass():
    files = check_grants.migrations()
    assert files, "no migration from the cutoff on"
    assert check_grants.main([str(f) for f in files]) == 0


def test_a_table_without_grant_fails():
    assert check_grants.problems("create table public.x (id int);") == [("x", "no GRANT to service_role")]


def test_a_table_with_service_role_grant_passes():
    sql = ("create table if not exists public.x (id int);\n"
           "alter table public.x enable row level security;\n"
           "grant select, insert on public.x to service_role;")
    assert check_grants.problems(sql) == []


def test_anon_grant_needs_rls_and_a_policy():
    sql = "create table x (id int); grant select on x to service_role, anon;"
    assert ("x", "GRANT to anon without row level security and a policy for it") in check_grants.problems(sql)
    sql += " alter table x enable row level security; create policy p on x for select to anon using (true);"
    assert check_grants.problems(sql) == []


def test_comments_do_not_count():
    assert check_grants.problems("create table x (id int); -- grant all on x to service_role") != []


def test_a_new_migration_file_without_grant_fails(tmp_path):
    f = tmp_path / "20261101000000_new.sql"
    f.write_text("create table public.later (id int);")
    assert check_grants.main([str(f)]) == 1
