"""OPTOUT-1 (01/10/2026): a removal request hides a record, never deletes it.

posts.hidden is the flag. Public reads (anon, authenticated: every page of
the site, which reads with the public key) never see a hidden record or its
daily series (RLS); the backend's public endpoints filter it too, whatever
key they run with. The record stays in the table and the engine keeps
measuring it (the service role bypasses RLS).
"""

import pytest
from fastapi.testclient import TestClient

import main
from tests.pg_client import PgClient


def _two_records(db):
    with db.cursor() as cur:
        cur.execute("grant select on public.posts, public.post_daily to anon, authenticated")
        ids = {}
        for vid, hidden in (("shown", False), ("gone", True)):
            cur.execute(
                "insert into posts (external_post_id, author_handle, baseline_score, vpi_ratio, "
                "vpi_level, vpi_level_name, vpi_color, method_version, baseline_rule, format, status, "
                "entered_on, hidden, claim_token) values (%s, '@c', 100, 3.0, 1, 'x', '#888888', "
                "'v2', 'standard', 'LONG', 'ACTIVE', '2026-09-30', %s, %s) returning id",
                (vid, hidden, f"tok_{vid}"))
            ids[vid] = cur.fetchone()[0]
            cur.execute("insert into post_daily (post_id, day, day_index, views, vpi_ratio) "
                        "values (%s, '2026-09-30', 1, 300, 3.0)", (ids[vid],))
    return ids


def _as(db, role, query):
    with db.cursor() as cur:
        cur.execute("savepoint s")
        cur.execute(f"set local role {role}")
        cur.execute(query)
        rows = cur.fetchall()
        cur.execute("rollback to savepoint s")
    return rows


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_a_hidden_record_is_invisible_to_public_reads(db, role):
    _two_records(db)
    assert _as(db, role, "select external_post_id from posts where method_version = 'v2'") == [("shown",)]
    assert len(_as(db, role, "select * from post_daily")) == 1


def test_a_hidden_record_is_never_deleted(db):
    ids = _two_records(db)
    with db.cursor() as cur:
        cur.execute("select hidden from posts where id = %s", (ids["gone"],))
        assert cur.fetchone() == (True,)
        cur.execute("select count(*) from post_daily where post_id = %s", (ids["gone"],))
        assert cur.fetchone() == (1,)


def test_the_claim_lookup_does_not_resolve_a_hidden_record(db, monkeypatch):
    _two_records(db)
    monkeypatch.setattr(main, "supabase", PgClient(db))
    client = TestClient(main.app)
    assert client.get("/api/claim/tok_shown/window").status_code == 200
    assert client.get("/api/claim/tok_gone/window").status_code == 404


def test_the_public_endpoints_filter_hidden(monkeypatch):
    from tests.test_api import FakeDB
    db = FakeDB(post_daily=[], posts=[], ingest_run=[])
    monkeypatch.setattr(main, "supabase", db)
    main._STATISTICHE_CACHE.clear()
    client = TestClient(main.app)
    client.get("/api/posts")
    assert db.last("posts").has("eq", "hidden", False)
    client.get("/api/analytics/top10?timeframe=all")
    assert db.last("post_daily").has("eq", "posts.hidden", False)
