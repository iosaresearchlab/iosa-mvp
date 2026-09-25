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

# Applied migrations first, then the SQL waiting for a decision in
# supabase/pending/: the code is tested against the schema it will need.
MIGRATIONS = (sorted((ROOT / "supabase" / "migrations").glob("*.sql"))
              + sorted((ROOT / "supabase" / "pending").glob("*.sql")))

# The pre-v2 posts table: its production columns and NOT NULLs (read from
# information_schema on 25/09). A few columns carry defaults only so that
# tests can insert partial rows; the level fields and author_handle do not,
# as in production. The engine test writes every column itself. T-05 adds the v2
# columns; the pending T-10 file relaxes three NOT NULLs.
POSTS_STUB = """
create table public.posts (
  id               uuid primary key default gen_random_uuid(),
  window_id        uuid,
  external_post_id text not null,
  platform         varchar not null default 'YOUTUBE',
  author_handle    varchar not null,
  author_name      varchar,
  post_url         text not null default 'https://example.invalid/',
  content_text     text,
  category         varchar default 'General',
  country          text,
  engagement_score numeric not null default 0,
  vpi_level_name   varchar not null,
  vpi_color        varchar not null,
  claim_token      varchar not null default gen_random_uuid()::text unique,
  printify_product_id text,
  comment_sent     boolean,
  channel_id       text,
  channel_handle   text,
  subscribers      integer,
  format           text not null default 'SHORT',
  created_at       timestamptz default now(),
  detected_at      timestamptz default now(),
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
create table cron.job (jobid bigint primary key, jobname text unique,
  schedule text, command text, active boolean);
insert into cron.job values (1, 'ingestione-iosa', '*/20 * * * *',
  'select public.chiedi_un_giro_di_ingestione()', true);
create function cron.alter_job(job_id bigint, schedule text default null,
  command text default null, database text default null,
  username text default null, active boolean default null)
returns void language sql as
  'update cron.job set active = coalesce($6, active),
     schedule = coalesce($2, schedule), command = coalesce($3, command)
   where jobid = $1';
create function cron.schedule(job_name text, schedule text, command text)
returns bigint language sql as
  'insert into cron.job values ((select coalesce(max(jobid), 0) + 1 from cron.job),
     $1, $2, $3, true)
   on conflict (jobname) do update set schedule = excluded.schedule,
     command = excluded.command, active = true
   returning jobid';
"""

# Tables that reference posts in production, with their foreign keys as read
# from pg_constraint on 25/09: claims cascades, the three outreach-side tables
# set null. claims carries the public read policy it had in production.
LINKED_STUB = """
create table public.claims (
  id uuid primary key default gen_random_uuid(),
  post_id uuid references public.posts(id) on delete cascade,
  status varchar, product_selected varchar, stripe_session_id text,
  customer_email varchar, shipping_name varchar, shipping_address jsonb,
  created_at timestamptz default now()
);
alter table public.claims enable row level security;
create policy "Allow public read on claims" on public.claims for select to public using (true);
grant all on public.claims to anon, authenticated, service_role;
create table public.outreach (
  id uuid primary key default gen_random_uuid(),
  round integer not null default 1, channel_id text not null default 'UC',
  fascia_iscritti text not null default 'x', banda_livello text not null default 'x',
  post_id uuid references public.posts(id) on delete set null,
  claim_token text
);
create table public.claim_visite (
  id uuid primary key default gen_random_uuid(), claim_token text not null,
  post_id uuid references public.posts(id) on delete set null,
  vista_il timestamptz not null default now()
);
create table public.claim_eventi (
  id uuid primary key default gen_random_uuid(), claim_token text not null,
  post_id uuid references public.posts(id) on delete set null,
  azione text not null default 'x', avvenuto_il timestamptz not null default now()
);
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
            cur.execute(LINKED_STUB)
            cur.execute(
                "insert into posts (external_post_id, author_handle, baseline_score, vpi_ratio, "
                "vpi_level, vpi_level_name, vpi_color) values "
                "('v1_old_a', '@a', 900, 3.2, 4, 'Lvl 4 - Trending', '#00CC88'), "
                "('v1_old_b', '@b', 400, 1.1, 1, 'Lvl 1 - Standard', '#888888')"
            )
            for f in MIGRATIONS:
                cur.execute(f.read_text(encoding="utf-8"))
        yield conn
    finally:
        conn.rollback()
        conn.close()
