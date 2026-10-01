"""APP-2 (01/10/2026): the plaque of a closed v2 record.

It carries vpi_max, views_max, days_charting, entered_on and left_on, says
what the baseline is, has no gamma, and exists only once the record has
closed with a VPI. Its archive name is tied to the closed state.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import archivio_targhe
import generate_trophy
import main
from tests.pg_client import PgClient


@pytest.fixture
def api(db, monkeypatch, tmp_path):
    monkeypatch.setattr(main, "supabase", PgClient(db))
    names = []
    monkeypatch.setattr(archivio_targhe, "esiste", lambda nome: names.append(nome) or False)
    monkeypatch.setattr(archivio_targhe, "carica", lambda nome, percorso: None)
    monkeypatch.setattr(main, "_cached_render", lambda key: None)
    rendered = []
    png = tmp_path / "plaque.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")

    async def render(**kw):
        rendered.append(kw)
        return png
    monkeypatch.setattr(main, "generate_trophy_png", render)
    return TestClient(main.app), db, rendered, names


def _record(db, token, status, vpi_max=None, left_on=None, days=None, rule="standard"):
    with db.cursor() as cur:
        cur.execute(
            "insert into posts (external_post_id, author_handle, baseline_score, vpi_ratio, "
            "vpi_level, vpi_level_name, vpi_color, method_version, baseline_rule, format, status, "
            "entered_on, left_on, days_charting, vpi_max, views_max, claim_token, content_text) "
            "values (%s, '@c', %s, %s, %s, %s, %s, 'v2', %s, 'LONG', %s, '2026-09-27', %s, "
            "%s, %s, %s, %s, 'a title')",
            (token, 1000 if rule == "standard" else None, 2.5 if rule == "standard" else None,
             1 if rule == "standard" else None, "x" if rule == "standard" else None,
             "#888888" if rule == "standard" else None,
             rule, status, left_on, days, vpi_max, 12345 if vpi_max else None, token))


def test_a_closed_record_renders_its_peak_views_days_and_dates(api):
    client, db, rendered, names = api
    _record(db, "tok_closed", "CLOSED", vpi_max=7.25, left_on="2026-09-30", days=3)
    r = client.get("/api/trophy/preview", params={"claim_token": "tok_closed"})
    assert r.status_code == 200
    kw = rendered[0]
    assert kw["vpi_score"] == "+7.2x" or kw["vpi_score"] == "+7.3x"
    assert float(kw["e_act"]) == 12345 and kw["days_charting"] == 3
    assert (kw["entered_on"], kw["left_on"]) == ("2026-09-27", "2026-09-30")
    assert (kw["recorded_date"], kw["measured_date"]) == ("2026-09-27", "2026-09-30")
    assert kw["record_id"] == "tok_closed"                  # the QR still names the token
    assert kw["file_id"] == "tok_closed_closed_2026-09-30"
    assert names == ["tok_closed_closed_2026-09-30.png"]    # archive key tied to the closed state
    assert "gamma" not in kw
    assert "7-90 days before this one" in kw["method_text"]


def test_no_plaque_while_charting_and_none_without_a_vpi(api):
    client, db, rendered, _ = api
    _record(db, "tok_active", "ACTIVE")
    _record(db, "tok_novpi", "CLOSED", left_on="2026-09-30", days=2, rule="not_computable")
    assert client.get("/api/trophy/preview", params={"claim_token": "tok_active"}).status_code == 409
    assert client.get("/api/trophy/preview", params={"claim_token": "tok_novpi"}).status_code == 404
    assert rendered == []


def test_the_template_has_no_gamma_and_says_what_the_baseline_is():
    html = generate_trophy.TROPHY_HTML_TEMPLATE
    assert "&gamma;" not in html and "{gamma}" not in html
    assert "VPI = E<sub>act</sub> / E<sub>base</sub>" in html
    f = generate_trophy.plaque_fields(days_charting=3, entered_on="2026-09-27", left_on="2026-09-30")
    assert "median of the same channel&#39;s long-form videos published 7-90 days before this one" in f["method_text"]
    assert f["date1_label"] == "FIRST OBSERVED" and f["date2_label"] == "LEFT MOST POPULAR"
    assert "Days in Most Popular" in f["extra_rows"] and ">3<" in f["extra_rows"]
