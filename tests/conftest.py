"""Shared pytest configuration for the repository-level test suite.

Tests in this folder import backend modules by their bare names
(``import vpi_core``), the same way the backend imports them at runtime
(Render runs with ``rootDir: backend``). Putting ``backend/`` on the path
here keeps that true when pytest is run from the repository root, locally
and in CI.

No test in this suite may call the real YouTube API: the quota is a daily
production budget. HTTP is mocked (``responses``).

Database tests use the ``db`` fixture below. It needs PostgreSQL in
IOSA_TEST_DATABASE_URL; without it those tests are skipped, unless
IOSA_REQUIRE_DB_TESTS=1 (set in CI), in which case a missing database or a
missing driver is a failure: a skipped test is not a verdict.
"""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

MIGRATIONS = sorted((ROOT / "supabase" / "migrations").glob("*.sql"))

# The pre-v2 posts table, reduced to what the migrations and the tests touch.
# T-05 adds the v2 columns and releases the not-null on vpi_ratio / vpi_level.
POSTS_STUB = """
create table public.posts (
  id               uuid primary key default gen_random_uuid(),
  external_post_id text not null,
  status           text default 'ACTIVE',
  baseline_score   numeric not null,
  vpi_ratio        numeric not null,
  vpi_level        int not null
);
"""

# Supabase-only objects some migrations use: the API roles, and pg_cron,
# which does not exist on a plain PostgreSQL (same call signature for
# alter_job).
SUPABASE_STUB = """
do $r$ begin
  create role anon; create role authenticated; create role service_role;
exception when duplicate_object then null; end $r$;
create schema cron;
create table cron.job (jobid bigint primary key, jobname text, active boolean);
insert into cron.job values (1, 'ingestione-iosa', true);
create function cron.alter_job(job_id bigint, schedule text default null,
  command text default null, database text default null,
  username text default null, active boolean default null)
returns void language sql as
  'update cron.job set active = coalesce($6, active) where jobid = $1';
"""


def _require_db():
    return os.environ.get("IOSA_REQUIRE_DB_TESTS") == "1"


@pytest.fixture
def db():
    """A connection on which the pre-v2 stub and every migration have run.

    Two v1 rows exist before the migrations, as in production. Everything,
    schema included, is rolled back at the end of the test.
    """
    url = os.environ.get("IOSA_TEST_DATABASE_URL")
    if not url:
        if _require_db():
            pytest.fail("IOSA_REQUIRE_DB_TESTS=1 but IOSA_TEST_DATABASE_URL is not set")
        pytest.skip("IOSA_TEST_DATABASE_URL not set")
    try:
        import psycopg
    except ImportError:
        if _require_db():
            raise
        pytest.skip("psycopg not installed")

    conn = psycopg.connect(url, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute(SUPABASE_STUB)
            cur.execute(POSTS_STUB)
            cur.execute(
                "insert into posts (external_post_id, baseline_score, vpi_ratio, vpi_level) "
                "values ('v1_old_a', 900, 3.2, 4), ('v1_old_b', 400, 1.1, 1)"
            )
            for f in MIGRATIONS:
                cur.execute(f.read_text(encoding="utf-8"))
        yield conn
    finally:
        conn.rollback()
        conn.close()
