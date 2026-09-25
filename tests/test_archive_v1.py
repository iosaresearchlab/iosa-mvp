"""The v1 records moved out of posts into posts_v1 (02 section 3.6, 25/09/2026).

conftest seeds two v1 rows plus an outreach row and a claim visit pointing
at one of them, then runs every migration: what is asserted here is the
state after the archive migration.
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
        assert one(cur, "select external_post_id, vpi_ratio::text, baseline_score::text "
                        "from posts_v1 order by 1") == [("v1_old_a", "3.2", "900"),
                                                        ("v1_old_b", "1.1", "400")]
        assert one(cur, "select count(*) from posts_v1 where archived_at is null") == [(0,)]


def test_blanked_links_are_kept_with_the_original_post_id(db):
    with db.cursor() as cur:
        assert one(cur, "select count(*) from outreach where post_id is not null") == [(0,)]
        assert one(cur, "select count(*) from claim_visite where post_id is not null") == [(0,)]
        rows = one(cur, "select l.source_table, v.external_post_id, l.claim_token = v.claim_token "
                        "from posts_v1_links l join posts_v1 v on v.id = l.post_id order by 1")
        assert rows == [("claim_visite", "v1_old_a", True), ("outreach", "v1_old_a", True)]
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
        (token,) = one(cur, "select claim_token from posts_v1 where external_post_id = 'v1_old_a'")[0]
        cur.execute("set local role anon")
        assert one(cur, "select external_post_id from claim_record_v1(%s)", token) == [("v1_old_a",)]
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


def test_the_move_aborts_on_a_checksum_mismatch(db):
    """Re-run on an archive that already holds rows: counts differ, nothing moves."""
    with db.cursor() as cur:
        cur.execute("insert into posts (external_post_id, author_handle, baseline_score, vpi_ratio, "
                    "vpi_level, vpi_level_name, vpi_color, method_version) values "
                    "('v1_late', '@c', 10, 2, 2, 'x', '#000', 'v1')")
        cur.execute("savepoint s")
        with pytest.raises(psycopg.errors.RaiseException, match="archive mismatch"):
            cur.execute(MOVE)
        cur.execute("rollback to savepoint s")
        assert one(cur, "select count(*) from posts where method_version = 'v1'") == [(1,)]
