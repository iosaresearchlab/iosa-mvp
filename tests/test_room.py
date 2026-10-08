"""ROOM-1 (owner decision 08/10/2026): the Breakout Room's data.

GET /api/room/latest and GET /api/room?from=YYYY-MM-DD answer one week of
measured records as compact arrays (02 section 6). Run on PostgreSQL with
every migration, through the real room_records() function: the counts per
band are checked against an independent SQL count on the same filters, one
known video round-trips, and the band edges come from the backend's band
function, never from literals in the endpoint code.
"""

import inspect
import random
import re
from datetime import date, timedelta

from fastapi.testclient import TestClient

import main
from tests.pg_client import PgClient

DAYS = [date(2026, 10, 1) + timedelta(days=i) for i in range(9)]   # 01/10 .. 09/10
INCOMPLETE = date(2026, 10, 5)
COMPLETE = [d for d in DAYS if d != INCOMPLETE]                      # 8 days
KNOWN = "knownVid001"


def _world(db, n=400, seed=7):
    rnd = random.Random(seed)
    with db.cursor() as cur:
        for d in DAYS:
            cur.execute("insert into ingest_run (day, started_at, finished_at, outcome, census_complete) "
                        "values (%s, %s, %s, 'ok', %s)",
                        (d, f"{d} 23:59:00+00", f"{d + timedelta(days=1)} 00:40:00+00", d != INCOMPLETE))

        def post(vid, ch, fmt, day, rule, baseline, v1, views1, **kw):
            cur.execute(
                "insert into posts (external_post_id, content_text, channel_id, author_name, channel_handle, "
                "author_handle, baseline_score, baseline_rule, vpi_ratio, method_version, format, status, "
                "entered_on, entry_certain, hidden, left_on, days_charting, countries, was_live, vpi_max, "
                "views_max, claim_token) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'v2', %s, %s, %s, %s, "
                "%s, %s, %s, %s, %s, %s, %s, %s) returning id",
                (vid, kw.get("title", f"title {vid}"), ch, f"name {ch}", f"@{ch}", f"@{ch}", baseline, rule,
                 v1 if v1 is not None or rule != "standard" else 1.0, fmt, "CLOSED" if kw.get("left_on") else "ACTIVE", day, kw.get("certain", True),
                 kw.get("hidden", False), kw.get("left_on"), kw.get("days", 1), kw.get("countries", ["IT"]),
                 kw.get("live"), kw.get("vmax", v1), kw.get("views_max", views1), f"tok_{vid}"))
            pid = cur.fetchone()[0]
            if views1 is not None:
                cur.execute("insert into post_daily (post_id, day, day_index, views, vpi_ratio) "
                            "values (%s, %s, 1, %s, %s)", (pid, day, views1, v1))
                cur.execute("insert into post_daily (post_id, day, day_index, views, vpi_ratio) "
                            "values (%s, %s, 2, %s, %s)", (pid, day + timedelta(days=1), views1 * 2,
                                                            None if v1 is None else v1 * 2))

        for i in range(n):
            day = rnd.choice(DAYS)
            rule = rnd.choice(["standard"] * 6 + ["not_computable", "quota_stop", "read_failed"])
            baseline = rnd.choice([5, 99.9, 100, 999, 1000, 54321, 99999.99, 100000, 2.5e6]) \
                if rule == "standard" else None
            day1 = rnd.random() > 0.08
            views1 = rnd.randint(1000, 5_000_000) if day1 else None
            v1 = round(views1 / baseline, 4) if (day1 and baseline) else None
            post(f"v{i:04d}", f"UC{rnd.randint(0, 120):03d}", rnd.choice(["LONG"] * 4 + ["SHORT"]), day,
                 rule, baseline, v1, views1, certain=rnd.random() > 0.1, hidden=rnd.random() < 0.05,
                 live=rnd.choice([None, True, False]),
                 left_on=day + timedelta(days=2) if rnd.random() < 0.5 else None)
        # the known video: band 100-1k, left after three days, two countries, live
        post(KNOWN, "UCknown", "LONG", date(2026, 10, 4), "standard", 512.6, 49.9987, 25_592.7,
             title="A " + "very long title " * 10, left_on=date(2026, 10, 7), days=3,
             countries=["US", "GB"], live=True, vmax=61.256, views_max=31_400)


def _client(db, monkeypatch):
    monkeypatch.setattr(main, "supabase_service", PgClient(db))
    main._ROOM_CACHE.clear()
    return TestClient(main.app)


def _sql_counts(db, days):
    """Independent of the endpoint: the same filters, the band edges of 01
    section 8 (100 and 100,000, powers of ten between), written out here."""
    with db.cursor() as cur:
        cur.execute("""
            select case when p.baseline_rule <> 'standard' or d.vpi_ratio is null then 5
                        when p.baseline_score < 100 then 0
                        when p.baseline_score < 1000 then 1
                        when p.baseline_score < 10000 then 2
                        when p.baseline_score < 100000 then 3
                        else 4 end b, count(*)
              from posts p left join post_daily d on d.post_id = p.id and d.day_index = 1
             where p.format = 'LONG' and p.entry_certain and p.hidden is not true
               and p.entered_on = any(%s) and p.entered_on >= '2026-09-27'
             group by 1""", (days,))
        return dict(cur.fetchall())


def _bands(payload):
    out = {}
    for row in payload["v"]:
        out[row[3]] = out.get(row[3], 0) + 1
    return out


def test_latest_counts_per_band_equal_the_sql_count(db, monkeypatch):
    _world(db)
    r = _client(db, monkeypatch).get("/api/room/latest")
    assert r.status_code == 200
    d = r.json()
    last7 = COMPLETE[-7:]                                        # 02/10 .. 09/10 without 05/10
    assert (d["from"], d["to"]) == (last7[0].isoformat(), last7[-1].isoformat())
    assert _bands(d) == _sql_counts(db, last7)
    assert len(d["v"]) > 150
    assert 5 in _bands(d)                                        # no computable baseline: kept


def test_from_counts_per_band_equal_the_sql_count(db, monkeypatch):
    _world(db)
    d = _client(db, monkeypatch).get("/api/room?from=2026-10-01").json()
    first7 = COMPLETE[:7]                                        # 01/10 .. 08/10 without 05/10
    assert (d["from"], d["to"]) == ("2026-10-01", "2026-10-08")
    assert _bands(d) == _sql_counts(db, first7)
    assert not [v for v in d["v"] if v[7] == (INCOMPLETE - DAYS[0]).days]   # a day without a census


def test_the_known_video_round_trips(db, monkeypatch):
    _world(db)
    d = _client(db, monkeypatch).get("/api/room?from=2026-10-01").json()
    row = next(v for v in d["v"] if v[0] == KNOWN)
    assert len(row) == 14
    assert len(row[1]) == 95 and row[1].endswith("…") and row[1].startswith("A very long title")
    assert d["c"][row[2]] == ["name UCknown", "@UCknown"]
    assert row[3] == 1                                           # 100-1k
    assert row[4] == 49.99                                       # rounded down, not up to 50.00
    assert row[5:7] == [25_593, 513]
    assert row[7:10] == [3, 3, 6]                                # entered 04/10, 3 days, left 07/10
    assert row[10:14] == [61.25, 31_400, "US GB", 1]
    still = [v for v in d["v"] if v[9] == -99]
    assert still and all(v[9] == -99 for v in still)


def test_one_channel_one_entry(db, monkeypatch):
    _world(db)
    d = _client(db, monkeypatch).get("/api/room/latest").json()
    assert len(d["c"]) == len({tuple(c) for c in d["c"]})
    assert {v[2] for v in d["v"]} == set(range(len(d["c"])))


def test_gzip_and_cache_headers(db, monkeypatch):
    _world(db, n=50)
    client = _client(db, monkeypatch)
    r = client.get("/api/room/latest", headers={"Accept-Encoding": "gzip"})
    assert r.headers["content-encoding"] == "gzip"
    assert r.headers["cache-control"] == "public, max-age=3600"
    assert r.json()["v"]
    assert len(main._ROOM_CACHE) == 1
    client.get("/api/room/latest")
    assert len(main._ROOM_CACHE) == 1                            # computed once for this state
    assert client.get("/api/room?from=10-2026").status_code == 400


def test_the_band_edges_come_from_the_band_function():
    src = "".join(inspect.getsource(f) for f in (main._room_band, main.room_payload, main._room_window,
                                                 main._room_response, main._room_floor2))
    assert not re.search(r"(?<![\d.])(100|1_?000|10_?000|100_?000)(?![\d.])", src)
    assert "baseline_band(" in src and "BASELINE_BANDS" in src
    assert main.ROOM_NO_BASELINE == len(main.BASELINE_BANDS) == 5


def test_the_page_reads_the_cached_route_and_the_route_caches_an_hour():
    """ROOM-1b: the page reads its data through Vercel's cache, never the
    backend directly, and an error is never cached."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    page = (root / "frontend" / "public" / "room" / "index.html").read_text(encoding="utf-8")
    assert re.findall(r'window\.ROOM_DATA_URL = "([^"]+)"', page) == ["/api/room/latest"]
    assert page.count('rel="canonical"') == 1 and " 2026" not in page.split("<script type=\"module\">")[1]
    route = (root / "frontend" / "src" / "app" / "api" / "room" / "latest" / "route.ts").read_text(encoding="utf-8")
    assert "'public, s-maxage=3600, stale-while-revalidate=86400'" in route
    assert route.count("'Cache-Control': 'no-store'") == 2 and "/api/room/latest" in route
