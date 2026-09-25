"""T-12: the API endpoints, with the database replaced by a recording fake.

The fake records every query-builder call, so the filters are asserted
(method_version = 'v2', day_index = 1, ...) rather than read in the code.
docs/02-technical-specification.md section 4.5; docs/01 section 4.2.
"""

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

import main


class _Res:
    def __init__(self, data):
        self.data, self.count = data, len(data)


class _Query:
    def __init__(self, store, table):
        self.store, self.table, self.calls = store, table, []
        store.queries.append(self)

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self
        return call

    def execute(self):
        rows = self.store.data.get(self.table, [])
        for name, args, _ in self.calls:            # claim lookups by token
            if name == "eq" and args[0] == "claim_token":
                rows = [r for r in rows if r.get("claim_token") == args[1]]
            if name == "rpc":
                rows = [r for r in rows if r.get("claim_token") == args[1]["p_token"]]
        for name, args, _ in self.calls:            # the one filter the lock needs
            if self.table == "ingest_run" and name == "eq" and args[0] == "day":
                rows = [r for r in rows if r["day"] == args[1]]
        return _Res(list(rows))

    def has(self, name, *args):
        return any(n == name and a[:len(args)] == args for n, a, _ in self.calls)


class FakeDB:
    def __init__(self, **data):
        self.data, self.queries = data, []

    def table(self, name):
        return _Query(self, name)

    def rpc(self, name, params):
        q = _Query(self, "rpc:" + name)
        q.calls.append(("rpc", (name, params), {}))
        return q

    def last(self, table):
        return [q for q in self.queries if q.table == table][-1]


def post(pid, fmt, base, vpi, countries=("IT",), cats=("Entertainment",), age=3,
         title="funny cat video", certain=True):
    return {"day": "2026-10-01", "day_index": 1, "views": 1000, "vpi_ratio": vpi,
            "posts": {"id": pid, "external_post_id": pid, "format": fmt, "baseline_score": base,
                      "baseline_rule": "standard" if base is not None else "not_computable",
                      "countries": list(countries), "categories": list(cats),
                      "country": countries[0], "category": cats[0], "entered_on": "2026-10-01",
                      "age_at_first_obs_days": age, "entry_certain": certain,
                      "method_version": "v2", "content_text": title}}


ROWS = [
    post("s1", "SHORT", 50, 40.0), post("s2", "SHORT", 80, 60.0),           # <100 SHORT
    post("s3", "SHORT", 50_000, 2.0, countries=("IT", "DE")),               # 10k-100k SHORT
    post("l1", "LONG", 50_000, 1.2, age=9), post("l2", "LONG", 60_000, 1.6),  # 10k-100k LONG
    post("nc", "SHORT", None, None),                                        # not computable
]


@pytest.fixture
def api(monkeypatch):
    db = FakeDB(post_daily=ROWS, posts=[{"id": "p"}], ingest_run=[])
    monkeypatch.setattr(main, "supabase", db)
    monkeypatch.setattr(main, "supabase_service", db)
    monkeypatch.setattr(main, "INGEST_TRIGGER_TOKEN", "secret-token")
    main._STATISTICHE_CACHE.clear()
    return TestClient(main.app), db


# --- /api/posts ---------------------------------------------------------------


def test_posts_v2_only_and_no_vpi_floor_by_default(api):
    client, db = api
    r = client.get("/api/posts")
    assert r.status_code == 200 and set(r.json()) == {"posts", "total"}
    q = db.last("posts")
    assert q.has("eq", "method_version", "v2")
    assert not q.has("gte"), "min_vpi defaults to 0: no floor, not_computable records included"


def test_posts_filters(api):
    client, db = api
    client.get("/api/posts?min_vpi=2&country=it&category=Comedy&status=closed&format=long")
    q = db.last("posts")
    assert q.has("gte", "vpi_ratio", 2.0)
    assert q.has("contains", "countries", ["IT"]) and q.has("contains", "categories", ["Comedy"])
    assert q.has("eq", "status", "CLOSED") and q.has("eq", "format", "LONG")


def test_posts_selects_the_claim_token_but_no_internal_column(api):
    """claim_token is the plaque's public identifier (25/09/2026); the two
    Printify/outreach bookkeeping columns stay out."""
    client, db = api
    client.get("/api/posts")
    (cols,) = [a[0] for n, a, _ in db.last("posts").calls if n == "select"]
    assert cols != "*"
    selected = set(cols.split(","))
    assert "claim_token" in selected
    assert not selected & {"printify_product_id", "comment_sent"}


def test_the_lock_uses_the_reading_day(api, monkeypatch):
    """A second attempt at 00:30 UTC finds the row of the day just closed."""
    client, db = api
    db.data["ingest_run"] = [{"day": "2026-10-01", "outcome": "ok"}]
    monkeypatch.setattr(main, "reading_day", lambda: date(2026, 10, 1))
    monkeypatch.setattr(main, "_giro_di_ingestione", lambda: pytest.fail("must not run"))
    r = client.post("/api/ingest/run", headers=AUTH)
    assert r.status_code == 409 and r.json()["detail"]["day"] == "2026-10-01"


# --- /api/analytics/top10 -----------------------------------------------------


def test_top10_reads_day_index_1_of_certain_v2_records(api):
    client, db = api
    body = client.get("/api/analytics/top10?timeframe=7d").json()
    q = db.last("post_daily")
    assert q.has("eq", "day_index", 1)
    assert q.has("eq", "posts.method_version", "v2")
    assert q.has("eq", "posts.entry_certain", True)
    assert q.has("gte", "posts.entered_on")
    assert body["day_index"] == 1 and "Not age-adjusted" in body["label"]


def test_top10_ranks_by_day1_vpi_and_discloses_n_and_age(api):
    client, _ = api
    body = client.get("/api/analytics/top10?timeframe=all").json()
    assert [t["external_post_id"] for t in body["top10"]] == ["s2", "s1", "s3", "l2", "l1"]
    assert body["n"] == 5                                   # the not computable one has no VPI
    assert body["age_at_first_obs_days"] == {"min": 3, "median": 3.0, "max": 9}
    assert all("claim_token" not in t for t in body["top10"])


def test_top10_timeframe_all_has_no_date_filter_and_unknown_is_400(api):
    client, db = api
    client.get("/api/analytics/top10?timeframe=all")
    assert not db.last("post_daily").has("gte")
    assert client.get("/api/analytics/top10?timeframe=15d").status_code == 400


# --- /api/analytics/insights and keywords: never pooled ----------------------


def _walk(obj, band=None, fmt=None, path="$"):
    """Yield (path, dict, band, format) for every dict, band/format inherited."""
    if isinstance(obj, dict):
        band = obj.get("baseline_band", band)
        fmt = obj.get("format", fmt)
        yield path, obj, band, fmt
        for k, v in obj.items():
            yield from _walk(v, band, fmt, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, band, fmt, f"{path}[{i}]")


STATS = {"median_vpi", "avg_vpi", "viral_velocity", "mean_vpi"}


def _assert_never_pooled(body):
    for path, d, band, fmt in _walk(body):
        for k in STATS & set(d):
            assert band is not None and fmt is not None, f"{path}.{k} pools baseline bands or formats"
    assert not any({"avg_vpi", "viral_velocity"} & set(d) for _, d, _, _ in _walk(body))


def test_no_segment_response_pools_baseline_bands_or_formats(api):
    client, _ = api
    for url in ("/api/analytics/insights", "/api/analytics/keywords?min_vpi=0"):
        r = client.get(url)
        assert r.status_code == 200
        _assert_never_pooled(r.json())


def test_insights_cells_are_per_band_and_format_with_n(api):
    client, db = api
    body = client.get("/api/analytics/insights").json()
    assert db.last("post_daily").has("eq", "day_index", 1)
    assert body["by_country"]["IT"] == [
        {"baseline_band": "<100", "format": "SHORT", "n": 2, "median_vpi": 50.0},
        {"baseline_band": "10k-100k", "format": "LONG", "n": 2, "median_vpi": 1.4},
        {"baseline_band": "10k-100k", "format": "SHORT", "n": 1, "median_vpi": 2.0},
    ]
    # the pooled median of IT (1.2, 1.6, 2, 40, 60 -> 2.0) happens to equal a
    # cell here; the 10k-100k band pooled across formats (1.2, 1.6, 2.0) is
    # 1.6 and must appear in no cell
    assert all(c["median_vpi"] != 1.6 for c in body["by_country"]["IT"])
    assert body["by_country"]["DE"] == [{"baseline_band": "10k-100k", "format": "SHORT", "n": 1, "median_vpi": 2.0}]
    assert body["macro_regions"]["Europe"][0]["n"] == 2       # s3 counted once, not per country


def test_keywords_segments_per_band_and_format(api):
    client, _ = api
    body = client.get("/api/analytics/keywords?min_vpi=5").json()
    assert [(s["baseline_band"], s["format"], s["n"]) for s in body["segments"]] == [("<100", "SHORT", 2)]
    assert body["segments"][0]["keywords"][0]["frequency"] == 2


def test_baseline_bands():
    assert [main.baseline_band(b) for b in (0, 99.9, 100, 999, 1000, 99_999, 100_000, 10**9)] == \
        ["<100", "<100", "100-1k", "100-1k", "1k-10k", "10k-100k", ">=100k", ">=100k"]
    assert main.baseline_band(None) is None


# --- /api/ingest ---------------------------------------------------------------


AUTH = {"Authorization": "Bearer secret-token"}


def test_ingest_run_requires_the_token(api):
    client, _ = api
    assert client.post("/api/ingest/run").status_code == 401


def test_a_second_run_for_the_same_day_is_409(api, monkeypatch):
    client, db = api
    today = main.reading_day().isoformat()
    ran = []

    def fake_reading():
        ran.append(today)
        db.data["ingest_run"].append({"day": today, "outcome": "ok"})
        main._ingestione_in_corso = False
    monkeypatch.setattr(main, "_giro_di_ingestione", fake_reading)
    first = client.post("/api/ingest/run", headers=AUTH)
    assert first.status_code == 200 and first.json()["stato"] == "avviato"
    second = client.post("/api/ingest/run", headers=AUTH)
    assert second.status_code == 409 and second.json()["detail"]["outcome"] == "ok"
    assert ran == [today]


@pytest.mark.parametrize("outcome", ["partial", "failed", None])
def test_any_existing_row_for_today_is_409(api, monkeypatch, outcome):
    client, db = api
    db.data["ingest_run"] = [{"day": main.reading_day().isoformat(), "outcome": outcome}]
    monkeypatch.setattr(main, "_giro_di_ingestione", lambda: pytest.fail("must not run"))
    assert client.post("/api/ingest/run", headers=AUTH).status_code == 409


def test_without_the_service_key_the_lock_fails_closed(api, monkeypatch):
    client, _ = api
    monkeypatch.setattr(main, "supabase_service", None)
    monkeypatch.setattr(main, "_giro_di_ingestione", lambda: pytest.fail("must not run"))
    assert client.post("/api/ingest/run", headers=AUTH).status_code == 503
    assert client.get("/api/ingest/status").status_code == 503


def test_ingest_status_returns_the_latest_run(api):
    client, db = api
    db.data["ingest_run"] = [{"day": "2026-10-02", "outcome": "partial", "quota_total": 1350}]
    body = client.get("/api/ingest/status").json()
    assert body["latest"]["quota_total"] == 1350
    q = db.last("ingest_run")
    assert q.has("order", "day") and q.has("limit", 1)


# --- claim tokens after the v1 archive (02 section 3.6) -------------------------


def test_a_v2_token_resolves_in_posts_without_touching_the_archive(api):
    _, db = api
    db.data["posts"] = [{"id": "p2", "claim_token": "tok-v2"}]
    assert main._claim_lookup("tok-v2").data == [{"id": "p2", "claim_token": "tok-v2"}]
    assert not [q for q in db.queries if q.table.startswith("rpc:")]


def test_a_v1_token_resolves_in_the_archive(api):
    client, db = api
    db.data["posts"] = []
    db.data["rpc:claim_record_v1"] = [{"id": "p1", "claim_token": "tok-v1"}]
    assert main._claim_lookup("tok-v1").data == [{"id": "p1", "claim_token": "tok-v1"}]
    assert client.post("/api/claim/initialize/tok-v1").json() == {"status": "ready", "token": "tok-v1"}
    assert main._claim_lookup("unknown").data == []


# --- claim window (02 section 6.4) ---------------------------------------------


def test_the_claim_window_counts_from_first_observation():
    from datetime import date
    w = main.claim_window({"entered_on": "2026-09-26", "created_at": "2026-09-01T00:00:00+00:00"},
                          today=date(2026, 10, 1))
    assert w == {"start": "2026-09-26", "expires_on": "2026-10-11", "claim_days": 15, "expired": False}
    assert main.claim_window({"entered_on": "2026-09-26"}, today=date(2026, 10, 11))["expired"] is True


def test_a_v1_record_uses_its_detection_day():
    from datetime import date
    w = main.claim_window({"detected_at": "2026-09-21T10:00:00+00:00"}, today=date(2026, 9, 25))
    assert (w["start"], w["expires_on"]) == ("2026-09-21", "2026-10-06")


def test_claim_window_endpoint(api):
    client, db = api
    db.data["posts"] = [{"id": "p", "claim_token": "tok", "entered_on": "2026-09-26"}]
    body = client.get("/api/claim/tok/window").json()
    assert body["start"] == "2026-09-26" and body["claim_days"] == 15
    assert client.get("/api/claim/none/window").status_code == 404


def test_the_trigger_runs_with_the_engine_mode_off(api, monkeypatch):
    """IOSA_ENGINE_MODE=off (Render) stops only an in-process scheduler, which
    v2 does not have; the HTTP trigger is the one path and it is not gated."""
    client, db = api
    monkeypatch.setenv("IOSA_ENGINE_MODE", "off")
    ran = []
    monkeypatch.setattr(main, "_giro_di_ingestione", lambda: ran.append(1))
    r = client.post("/api/ingest/run", headers=AUTH)
    assert r.status_code == 200 and r.json()["stato"] == "avviato" and ran == [1]
    main._ingestione_in_corso = False
