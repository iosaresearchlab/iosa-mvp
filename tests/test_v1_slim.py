"""V1-SLIM (28/09/2026): posts_v1 holds exactly the columns the v1 claim reads.

Owner decision: the v1 claim pages must keep working (226 contacts in
outreach hold those tokens), and everything else goes to the archive file
(Storage, archivio/posts_v1/posts_v1.jsonl.gz, written and verified before
the migration). The list of columns is derived from the code here, not
written down: if the claim page, the plaque or the order flow starts reading
another field of a v1 record, the first test fails.
"""

import ast
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import archivio_targhe
import main
from tests.pg_client import PgClient

ROOT = Path(__file__).resolve().parent.parent
MAIN = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
PAGE = (ROOT / "frontend" / "src" / "app" / "claim" / "[token]" / "page.tsx").read_text(encoding="utf-8")
# Fallback props the page reads when a field is missing; not columns anywhere.
NOT_COLUMNS = {"title", "content_title", "e_act", "e_base"}


def _claim_functions():
    """Bodies of the backend functions that receive a record by claim token."""
    tree = ast.parse(MAIN)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            src = ast.get_source_segment(MAIN, node)
            if node.name in ("claim_window", "_reserve_order", "_record_order") or (
                    "_claim_lookup(" in src and node.name != "_claim_lookup"):
                out.append((node.name, src))
    return out


def fields_read():
    names = set()
    for _, src in _claim_functions():
        names |= set(re.findall(r'\b(?:post|p|record|post_data)\.get\(\s*"(\w+)"', src))
        names |= set(re.findall(r'\(record or \{\}\)\.get\(\s*"(\w+)"', src))
        names |= set(re.findall(r'\brecord\["(\w+)"\]', src))
    names |= set(re.findall(r"\bpost\??\.(\w+)", PAGE))
    return names


def columns(db, table):
    with db.cursor() as cur:
        cur.execute("select column_name from information_schema.columns "
                    "where table_schema = 'public' and table_name = %s", (table,))
        return {r[0] for r in cur.fetchall()}


def test_the_claim_functions_are_found():
    names = {n for n, _ in _claim_functions()}
    assert {"get_trophy_preview", "get_claim_window", "create_checkout_session",
            "stripe_webhook", "claim_window", "_reserve_order", "_record_order"} <= names


def test_posts_v1_holds_exactly_the_columns_the_v1_claim_reads(db):
    read = fields_read()
    # The page reads public_records (APP-4); its derived columns are not posts columns.
    known = columns(db, "posts") | columns(db, "public_records")
    assert read - known <= NOT_COLUMNS, read - known
    assert columns(db, "posts_v1") == (read & columns(db, "posts"))
    assert len(columns(db, "posts_v1")) == 16


def test_the_archive_is_still_not_listable_and_the_token_still_resolves(db):
    with db.cursor() as cur:
        for role in ("anon", "authenticated"):
            cur.execute("select has_table_privilege(%s, 'public.posts_v1', 'SELECT')", (role,))
            assert cur.fetchone() == (False,)
        cur.execute("select relrowsecurity from pg_class where oid = 'public.posts_v1'::regclass")
        assert cur.fetchone() == (True,)
        cur.execute("select claim_token from posts_v1 where author_handle = '@a'")
        (token,) = cur.fetchone()
        cur.execute("savepoint s")
        cur.execute("set local role anon")
        cur.execute("select * from claim_record_v1(%s)", (token,))
        row = cur.fetchall()
        with pytest.raises(Exception, match="permission denied"):
            cur.execute("select * from posts_v1")
        cur.execute("rollback to savepoint s")
    assert len(row) == 1 and len(row[0]) == 16


@pytest.fixture
def api(db, monkeypatch, tmp_path):
    client = PgClient(db)
    monkeypatch.setattr(main, "supabase", client)
    monkeypatch.setattr(archivio_targhe, "esiste", lambda nome: False)
    monkeypatch.setattr(archivio_targhe, "carica", lambda nome, percorso: None)
    monkeypatch.setattr(main, "_cached_render", lambda key: None)
    rendered = []
    png = tmp_path / "plaque.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")

    async def render(**kw):
        rendered.append(kw)
        return png
    monkeypatch.setattr(main, "generate_trophy_png", render)
    return TestClient(main.app), db, rendered


def test_a_v1_plaque_renders_from_the_reduced_row(api):
    client, db, rendered = api
    with db.cursor() as cur:
        cur.execute("select claim_token, to_char(created_at, 'YYYY-MM-DD') from posts_v1 "
                    "where author_handle = '@a'")
        token, created = cur.fetchone()
    r = client.get("/api/trophy/preview", params={"claim_token": token})
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    kw = rendered[0]
    assert (kw["user_handle"], kw["vpi_score"], kw["level_name"]) == ("@a", "+3.2x", "Lvl 4 - Trending")
    assert float(kw["e_base"]) == 900 and kw["recorded_date"] == created
    w = client.get(f"/api/claim/{token}/window")
    assert w.status_code == 200 and w.json()["start"]
