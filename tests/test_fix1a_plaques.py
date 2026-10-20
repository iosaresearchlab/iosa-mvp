"""FIX-1a (20/10/2026): the backend never starts Chromium.

/api/trophy/preview and /api/trophy/preview-mug answer 307 to the archived
file, or 202 {"status": "preparing"} when it is not archived; the in-process
render stays only behind PLAQUE_RENDER_LOCAL=1. render_plaques.py (run by
.github/workflows/plaques.yml) builds the plaque with the same
plaque_spec.build the endpoint uses, so it uploads the file the endpoint
looks for.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import archivio_targhe
import main
import plaque_spec
import render_plaques
from tests.pg_client import PgClient

ROOT = Path(__file__).resolve().parent.parent


def _record(db, token, status="CLOSED", vpi_max=7.25, left_on="2026-09-30"):
    with db.cursor() as cur:
        cur.execute(
            "insert into posts (external_post_id, author_handle, baseline_score, vpi_ratio, "
            "vpi_level, vpi_level_name, vpi_color, method_version, baseline_rule, format, status, "
            "entered_on, left_on, days_charting, vpi_max, views_max, claim_token, content_text) "
            "values (%s, '@c', 1000, 2.5, 1, 'x', '#888888', 'v2', 'standard', 'LONG', %s, "
            "'2026-09-27', %s, 3, %s, 12345, %s, 'a title')",
            (token, status, left_on, vpi_max, token))


@pytest.fixture
def api(db, monkeypatch):
    monkeypatch.setattr(main, "supabase", PgClient(db))
    archived = set()
    monkeypatch.setattr(archivio_targhe, "esiste", lambda nome: nome in archived)
    monkeypatch.setattr(archivio_targhe, "url_pubblico", lambda nome: f"https://cdn.test/targhe/{nome}")
    rendered = []

    async def render(**kw):
        rendered.append(kw)
        raise AssertionError("Chromium started on the backend")
    monkeypatch.setattr(main, "generate_trophy_png", render)
    monkeypatch.setattr(main, "generate_mug_preview_png", render)
    assert main.PLAQUE_RENDER_LOCAL is False                     # the default
    return TestClient(main.app), db, archived, rendered


def test_not_archived_answers_202_and_renders_nothing(api):
    client, db, archived, rendered = api
    _record(db, "tok_a")
    r = client.get("/api/trophy/preview", params={"claim_token": "tok_a"})
    assert r.status_code == 202 and r.json() == {"status": "preparing"}
    assert r.headers["cache-control"] == "no-store"
    m = client.get("/api/trophy/preview-mug")
    assert m.status_code == 202 and m.json() == {"status": "preparing"}
    assert rendered == []


def test_archived_answers_307_to_the_cdn(api):
    client, db, archived, rendered = api
    _record(db, "tok_b")
    archived.update({"tok_b_closed_2026-09-30.png", plaque_spec.mug_archive_name()})
    r = client.get("/api/trophy/preview", params={"claim_token": "tok_b"}, follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "https://cdn.test/targhe/tok_b_closed_2026-09-30.png"
    m = client.get("/api/trophy/preview-mug", follow_redirects=False)
    assert m.status_code == 307 and m.headers["location"].endswith(plaque_spec.mug_archive_name())
    assert rendered == []


def test_charting_and_no_vpi_are_still_refused(api):
    client, db, _, rendered = api
    _record(db, "tok_c", status="ACTIVE", vpi_max=None, left_on=None)
    assert client.get("/api/trophy/preview", params={"claim_token": "tok_c"}).status_code == 409
    assert rendered == []


def test_the_job_uploads_the_file_the_endpoint_looks_for(db, monkeypatch, tmp_path):
    _record(db, "tok_d")
    client = PgClient(db)
    looked, uploaded, calls = [], [], []
    monkeypatch.setattr(archivio_targhe, "esiste", lambda nome: looked.append(nome) or False)
    monkeypatch.setattr(archivio_targhe, "carica",
                        lambda nome, percorso: uploaded.append(nome) or f"https://cdn.test/{nome}")
    png = tmp_path / "p.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")

    def fake_render(**kw):
        calls.append(kw)
        return str(png)
    assert render_plaques.render_token(client, "tok_d", render=fake_render) == "rendered"
    post = plaque_spec.claim_lookup(client, "tok_d").data[0]
    refused, name, kwargs = plaque_spec.build(post, claim_token="tok_d")
    assert refused is None and looked == uploaded == [name] == ["tok_d_closed_2026-09-30.png"]
    assert calls == [{"output_dir": render_plaques.OUT, **kwargs}]
    assert kwargs["vpi_score"] in ("+7.2x", "+7.3x") and kwargs["left_on"] == "2026-09-30"


def test_the_job_never_renders_twice_and_refuses_what_the_endpoint_refuses(db, monkeypatch):
    _record(db, "tok_e")
    _record(db, "tok_f", status="ACTIVE", vpi_max=None, left_on=None)
    client = PgClient(db)
    monkeypatch.setattr(archivio_targhe, "esiste", lambda nome: True)

    def boom(**kw):
        raise AssertionError("rendered an archived plaque")
    assert render_plaques.render_token(client, "tok_e", render=boom) == "archived"
    assert render_plaques.render_token(client, "tok_f", render=boom) == "refused:charting"
    assert render_plaques.render_token(client, "nope", render=boom) == "missing"


def test_the_claim_page_points_at_the_archived_mug_sample():
    lib = (ROOT / "frontend" / "src" / "lib" / "plaque.ts").read_text(encoding="utf-8")
    assert re.findall(r"MUG_SAMPLE_FILE = '([^']+)'", lib) == [plaque_spec.mug_archive_name()]
    page = (ROOT / "frontend" / "src" / "app" / "claim" / "[token]" / "page.tsx").read_text(encoding="utf-8")
    assert "/api/trophy/preview-mug" not in page
    assert "archivedPlaqueUrl(MUG_SAMPLE_FILE)" in page
    assert "Your plaque is being prepared" in page
