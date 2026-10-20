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
    monkeypatch.setattr(main, "supabase_service", PgClient(db))
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
    assert "/api/trophy/preview-mug" not in page and "/api/trophy/preview?" not in page
    assert "archivedPlaqueUrl(MUG_SAMPLE_FILE)" in page
    # the owner, 20/10: the plaque at once, every time, never "come back later"
    assert "/api/trophy/live?claim_token=" in page and "<LivePlaque" in page
    assert "come back" not in page.lower() and "being prepared" not in page
    live = (ROOT / "frontend" / "src" / "components" / "LivePlaque.tsx").read_text(encoding="utf-8")
    assert 'sandbox="allow-same-origin"' in live and "srcDoc={data.html}" in live
    assert "data.png_url" in live and "toPng(doc.documentElement" in live


# --- the live plaque (owner, 20/10/2026) -------------------------------------------

import generate_trophy  # noqa: E402


def test_the_live_plaque_is_the_html_the_png_is_made_from(api):
    client, db, archived, rendered = api
    _record(db, "tok_l")
    r = client.get("/api/trophy/live", params={"claim_token": "tok_l"})
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    d = r.json()
    post = plaque_spec.claim_lookup(main.supabase, "tok_l").data[0]
    _, name, kwargs = plaque_spec.build(post, claim_token="tok_l")
    assert d["html"] == generate_trophy.trophy_html(**kwargs)          # one page, two uses
    assert (d["width"], d["height"], d["file"], d["png_url"]) == (2700, 1120, name, None)
    assert len(d["html"]) < 40_000 and rendered == []
    with db.cursor() as cur:                                            # the workflow will render it
        cur.execute("select source from plaque_request where claim_token = 'tok_l'")
        assert cur.fetchall() == [("claim_page",)]
    archived.add(name)
    assert client.get("/api/trophy/live", params={"claim_token": "tok_l"}).json()["png_url"] \
        == f"https://cdn.test/targhe/{name}"


def test_the_live_plaque_refuses_what_the_png_refuses(api):
    client, db, _, _ = api
    _record(db, "tok_m", status="ACTIVE", vpi_max=None, left_on=None)
    assert client.get("/api/trophy/live", params={"claim_token": "tok_m"}).status_code == 409
    assert client.get("/api/trophy/live", params={"claim_token": "nope"}).status_code == 404


def test_the_plaque_runs_no_script_escapes_its_text_and_has_a_stable_hash():
    kw = dict(record_id="iosa_x", file_id="iosa_x_closed_2026-10-14", vpi_score="+2.0x",
              user_handle="@a<script>alert(1)</script>", content_title='"t" & <b>x</b>',
              e_act="100", e_base="50")
    html = generate_trophy.trophy_html(**kw)
    assert "<script" not in html and "cdn.tailwindcss.com" not in html
    assert "&lt;script&gt;" in html and "&lt;b&gt;x&lt;/b&gt;" in html
    assert html == generate_trophy.trophy_html(**kw)                    # no random hash
    assert generate_trophy.TROPHY_TAILWIND_CSS in html and len(generate_trophy.TROPHY_TAILWIND_CSS) > 5000


# --- orders: never sent to Printify without the print file ------------------------

def _paid(db, monkeypatch, token, archived_names):
    from tests.pg_client import PgClient as _P
    c = _P(db)
    monkeypatch.setattr(main, "supabase", c)
    monkeypatch.setattr(main, "supabase_service", c)
    monkeypatch.setattr(main, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(archivio_targhe, "esiste", lambda nome: nome in archived_names)
    monkeypatch.setattr(archivio_targhe, "scarica", lambda nome, percorso: Path(f"/tmp/{nome}"))
    session = {"id": "cs_fix1a", "metadata": {"claim_token": token},
               "customer_details": {"name": "A B", "email": "a@example.invalid", "address": {"country": "IT"}}}
    monkeypatch.setattr(main.stripe.Webhook, "construct_event",
                        lambda payload, sig, secret: {"type": "checkout.session.completed",
                                                      "data": {"object": session}})
    monkeypatch.setattr(main.stripe.checkout.Session, "retrieve", lambda sid: session)
    orders = []
    monkeypatch.setattr(main, "fulfill_trophy_order",
                        lambda **kw: orders.append(kw) or {"product_id": "prod-1", "order_id": "o-1"})
    monkeypatch.setattr(main, "ADMIN_API_KEY", "adm")
    return TestClient(main.app), orders


def test_a_paid_order_waits_for_its_print_file_then_is_placed(db, monkeypatch):
    _record(db, "tok_o")
    archived = set()
    client, orders = _paid(db, monkeypatch, "tok_o", archived)
    hook = lambda: client.post("/api/webhooks/stripe", content=b"{}", headers={"stripe-signature": "t"}).json()  # noqa: E731
    assert hook() == {"status": "awaiting_print_file"} and orders == []
    with db.cursor() as cur:
        cur.execute("select status from claims")
        assert cur.fetchall() == [("AWAITING_PRINT_FILE",)]
        cur.execute("select source from plaque_request where claim_token = 'tok_o'")
        assert cur.fetchall() == [("order",)]
    pending = lambda: client.post("/api/orders/fulfill-pending", headers={"x-iosa-admin-key": "adm"}).json()  # noqa: E731
    assert pending() == {"orders": {"cs_fix1a": "awaiting_print_file"}} and orders == []
    archived.add("tok_o_closed_2026-09-30.png")                        # the workflow rendered it
    assert pending() == {"orders": {"cs_fix1a": "success"}}
    assert [o["print_file"] for o in orders] == ["/tmp/tok_o_closed_2026-09-30.png"]
    assert pending() == {"orders": {}}                                  # placed once
    assert hook() == {"status": "already_fulfilled"} and len(orders) == 1
    assert client.post("/api/orders/fulfill-pending").status_code == 401


def test_the_job_renders_what_someone_needs(db, monkeypatch):
    _record(db, "tok_n1")
    _record(db, "tok_n2")
    with db.cursor() as cur:
        cur.execute("insert into plaque_request (claim_token, source) values ('tok_n1', 'social')")
        cur.execute("insert into claim_visite (claim_token, automatico) values ('tok_n2', false), "
                    "('tok_bot', true)")
    needed = set(render_plaques.needed_tokens(PgClient(db)))
    assert {"tok_n1", "tok_n2"} <= needed and "tok_bot" not in needed


def test_the_workflow_renders_with_the_shared_module():
    wf = (ROOT / ".github" / "workflows" / "plaques.yml").read_text(encoding="utf-8")
    assert 'cron: "30 3 * * *"' in wf and 'cron: "0 9 * * *"' in wf and "workflow_dispatch" in wf
    assert "python render_plaques.py --mug --needed --token $TOKENS" in wf
    assert "/api/orders/fulfill-pending" in wf and "secrets.IOSA_ADMIN_KEY" in wf
    assert "secrets.SUPABASE_SERVICE_KEY" in wf and "playwright install --with-deps chromium" in wf
