"""SOC-W2 (24/10/2026): GET /api/posts/{id}/baseline-sample, on PostgreSQL with every migration.

One fixture record with a standard baseline of five sample videos covers the three states:
- in the snapshot window -> true;  - with a v2 record -> true;
- published after the first complete census, never seen, no census missing -> false;
- published before the first census -> unknown;  - publication date unknown -> unknown.
A census missing after a video's publication turns its false into unknown. No HTTP leaves
the process: the endpoint reads the database only (no YouTube call is even possible here).
"""
import json
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

import baseline_sample
import main
from tests.pg_client import PgClient

DAYS = [date(2026, 9, 25) + timedelta(days=i) for i in range(10)]     # 25/09 .. 04/10
CH = "UCchannel0000000000000001"


def ep(y, m, d):
    return int(datetime(y, m, d, 12, tzinfo=timezone.utc).timestamp())


def _world(db, missing_day=None):
    with db.cursor() as cur:
        for d in DAYS:
            cur.execute("insert into ingest_run (day, started_at, finished_at, outcome, census_complete) "
                        "values (%s, %s, %s, 'ok', %s)",
                        (d, f"{d} 23:59:00+00", f"{d + timedelta(days=1)} 00:40:00+00", d != missing_day))

        def post(vid, rule="standard", ids=None, entered=date(2026, 10, 3), hidden=False):
            cur.execute(
                "insert into posts (external_post_id, content_text, channel_id, author_name, author_handle, "
                "baseline_score, baseline_rule, baseline_samples, baseline_video_ids, vpi_ratio, method_version, "
                "format, status, entered_on, entry_certain, hidden, claim_token) values (%s, %s, %s, 'n', '@h', "
                "%s, %s, %s, %s, %s, 'v2', 'LONG', 'ACTIVE', %s, true, %s, %s) returning id",
                (vid, f"title {vid}", CH, 1000 if rule == "standard" else None, rule,
                 len(ids) if ids else None, ids, 2.0 if rule == "standard" else None, entered, hidden, f"tok_{vid}"))
            return str(cur.fetchone()[0])

        ids = ["inSnapshot1", "hasRecord01", "neverSeen01", "oldVideo001", "noDate00001"]
        rid = post("measured001", ids=ids)
        post("hasRecord01", entered=date(2026, 9, 28))                 # a v2 record of a sample video
        nc = post("noBaseline1", rule="not_computable")
        hid = post("hiddenRec01", ids=ids, hidden=True)
        cur.execute("insert into trend_snapshot (day, video_id, channel_id, format, published_at, views, countries, "
                    "categories) values ('2026-10-02', 'inSnapshot1', %s, 'LONG', '2026-09-30T08:00:00Z', 5000, "
                    "array['IT'], array['20'])", (CH,))
        items = {"inSnapshot1": [ep(2026, 9, 30), "LONG"], "hasRecord01": [ep(2026, 9, 27), "LONG"],
                 "neverSeen01": [ep(2026, 9, 29), "LONG"], "oldVideo001": [ep(2026, 9, 1), "LONG"]}
        cur.execute("insert into channel_inventory (channel_id, items) values (%s, %s)", (CH, json.dumps(items)))
    return rid, nc, hid


def _client(db, monkeypatch):
    monkeypatch.setattr(main, "supabase_service", PgClient(db))
    return TestClient(main.app)


def test_the_three_states(db, monkeypatch):
    rid, _, _ = _world(db)
    r = _client(db, monkeypatch).get(f"/api/posts/{rid}/baseline-sample")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=21600"
    d = r.json()
    assert d["n_baseline"] == len(d["samples"]) == 5
    assert (d["window_from"], d["window_to"]) == ("2026-09-25", "2026-10-04")
    assert d["not_stored"] == ["title", "views_at_baseline"]
    got = {s["video_id"]: s["in_most_popular"] for s in d["samples"]}
    assert got == {"inSnapshot1": True, "hasRecord01": True, "neverSeen01": False,
                   "oldVideo001": "unknown", "noDate00001": "unknown"}
    assert [s["video_id"] for s in d["samples"]] == ["inSnapshot1", "hasRecord01", "neverSeen01",
                                                     "oldVideo001", "noDate00001"]   # the stored order
    first = {s["video_id"]: s["first_observed"] for s in d["samples"]}
    assert first["inSnapshot1"] == "2026-10-02" and first["hasRecord01"] == "2026-09-28"
    assert all(s["title"] is None and s["views_at_baseline"] is None for s in d["samples"])
    assert {s["video_id"]: s["published_at"] for s in d["samples"]}["neverSeen01"] == "2026-09-29T12:00:00Z"


def test_a_missing_census_after_publication_makes_false_unknown(db, monkeypatch):
    rid, _, _ = _world(db, missing_day=date(2026, 10, 1))
    d = _client(db, monkeypatch).get(f"/api/posts/{rid}/baseline-sample").json()
    assert {s["video_id"]: s["in_most_popular"] for s in d["samples"]}["neverSeen01"] == "unknown"


def test_no_standard_baseline_hidden_or_unknown_is_404(db, monkeypatch):
    _, nc, hid = _world(db)
    c = _client(db, monkeypatch)
    r = c.get(f"/api/posts/{nc}/baseline-sample")
    assert r.status_code == 404 and "not_computable" in r.json()["detail"]
    assert c.get(f"/api/posts/{hid}/baseline-sample").status_code == 404
    assert c.get("/api/posts/00000000-0000-0000-0000-000000000000/baseline-sample").status_code == 404
    assert c.get("/api/posts/not-a-uuid/baseline-sample").status_code == 404


def test_classify_edges():
    complete = [date(2026, 9, 25) + timedelta(days=i) for i in range(5)]
    f, last = complete[0], complete[-1]
    assert baseline_sample.classify(None, True, complete, f, last) is True
    assert baseline_sample.classify(datetime(2026, 9, 25, 3, tzinfo=timezone.utc), False, complete, f, last) == "unknown"
    assert baseline_sample.classify(datetime(2026, 9, 26, 3, tzinfo=timezone.utc), False, complete, f, last) is False
    assert baseline_sample.classify(None, False, complete, f, last) == "unknown"


def test_the_module_never_reaches_youtube():
    src = open(baseline_sample.__file__, encoding="utf-8").read()
    assert "googleapis" not in src and "requests" not in src and "youtube.com" not in src
