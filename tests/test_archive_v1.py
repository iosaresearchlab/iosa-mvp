"""The v1 records moved out of posts into posts_v1 (02 section 3.6, 25/09/2026),
then reduced to the columns the v1 claim reads (28/09/2026, test_v1_slim.py).

conftest seeds two v1 rows plus an outreach row and a claim visit pointing
at one of them, then runs every migration: what is asserted here is the
state after the archive migrations. v1 rows are named by author_handle:
external_post_id is one of the columns the reduction dropped.
"""

import re
from pathlib import Path

import psycopg
import pytest

MIGRATION = next((Path(__file__).resolve().parent.parent / "supabase" / "migrations")
                 .glob("*_v2_archive_v1_records.sql"))
MOVE = re.search(r"do \$m\$.*?\$m\$;", MIGRATION.read_text(encoding="utf-8"), re.S).group(0)


def one(cur, sql, *args):
    cur.execute(sql, args)
    return cur.fetchall()


def test_posts_holds_no_v1_row_and_the_archive_holds_them_all(db):
    with db.cursor() as cur:
        assert one(cur, "select count(*) from posts where method_version = 'v1'") == [(0,)]
        assert one(cur, "select author_handle, vpi_ratio::text, baseline_score::text, method_version "
                        "from posts_v1 order by 1") == [("@a", "3.2", "900", "v1"),
                                                        ("@b", "1.1", "400", "v1")]


def test_blanked_links_are_kept_with_the_original_post_id(db):
    with db.cursor() as cur:
        assert one(cur, "select count(*) from outreach where post_id is not null") == [(0,)]
        # claim_visite got its id back from the token at APP-12 (01/10/2026):
        # the archived id, no longer blank
        assert one(cur, "select count(*) from claim_visite c join posts_v1 v on v.id = c.post_id "
                        "and v.claim_token = c.claim_token") == [(1,)]
        rows = one(cur, "select l.source_table, v.author_handle, l.claim_token = v.claim_token "
                        "from posts_v1_links l join posts_v1 v on v.id = l.post_id order by 1")
        assert rows == [("claim_visite", "@a", True), ("outreach", "@a", True)]
        # every blanked row is in the snapshot, and outreach keeps its token
        assert one(cur, "select count(*) from outreach o left join posts_v1_links l "
                        "on l.source_table = 'outreach' and l.source_id = o.id "
                        "where l.post_id is null") == [(0,)]


def test_the_archive_is_not_readable_by_the_api_roles(db):
    with db.cursor() as cur:
        for role in ("anon", "authenticated"):
            for table in ("public.posts_v1", "public.posts_v1_links"):
                assert one(cur, "select has_table_privilege(%s, %s, 'SELECT')", role, table) == [(False,)]


def test_a_v1_claim_token_resolves_by_token_only(db):
    with db.cursor() as cur:
        (token,) = one(cur, "select claim_token from posts_v1 where author_handle = '@a'")[0]
        cur.execute("set local role anon")
        assert one(cur, "select author_handle from claim_record_v1(%s)", token) == [("@a",)]
        assert one(cur, "select count(*) from claim_record_v1(%s)", "no-such-token") == [(0,)]
        assert one(cur, "select count(*) from claim_record_v1(null)") == [(0,)]


def test_the_move_aborts_if_a_cascading_row_points_at_a_v1_record(db):
    with db.cursor() as cur:
        cur.execute("insert into posts (external_post_id, author_handle, baseline_score, vpi_ratio, "
                    "vpi_level, vpi_level_name, vpi_color, method_version) values "
                    "('v1_late', '@c', 10, 2, 2, 'x', '#000', 'v1') returning id")
        (pid,) = cur.fetchone()
        cur.execute("insert into claims (post_id) values (%s)", (pid,))
        cur.execute("savepoint s")
        with pytest.raises(psycopg.errors.RaiseException, match="cascading"):
            cur.execute(MOVE)
        cur.execute("rollback to savepoint s")
        assert one(cur, "select count(*) from claims") == [(1,)]


def test_the_move_cannot_run_again_on_the_reduced_archive(db):
    """A re-run of the 25/09 move on today's schema fails and moves nothing.

    Its checksum branch ('archive mismatch') ran once, in production, and
    matched (78c8c5fd..., task-log SEC-2); the archive now has 16 columns, so
    the insert itself is refused before any checksum is compared.
    """
    with db.cursor() as cur:
        cur.execute("insert into posts (external_post_id, author_handle, baseline_score, vpi_ratio, "
                    "vpi_level, vpi_level_name, vpi_color, method_version) values "
                    "('v1_late', '@c', 10, 2, 2, 'x', '#000', 'v1')")
        cur.execute("savepoint s")
        with pytest.raises(psycopg.Error):
            cur.execute(MOVE)
        cur.execute("rollback to savepoint s")
        assert one(cur, "select count(*) from posts where method_version = 'v1'") == [(1,)]
        assert one(cur, "select count(*) from posts_v1") == [(2,)]
