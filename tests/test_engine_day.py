"""T-10: the v2 daily procedure end to end, on real SQL and mocked HTTP.

Four simulated days run through vpi_engine.run_daily() against PostgreSQL
(every migration plus supabase/pending/, via the db fixture) and a fake
YouTube API. The assertions are on the rows actually written in posts,
post_daily, trend_snapshot and ingest_run.

docs/01-methodology-protocol.md section 4; docs/02 section 2; 08 T-10.
"""

import json
import random
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
import responses

psycopg = pytest.importorskip("psycopg")

import quota as q  # noqa: E402
import vpi_engine as eng  # noqa: E402
import retention  # noqa: E402
import census  # noqa: E402
from tests.pg_client import PgClient  # noqa: E402

KEY = "test-key-not-real"
D0 = date(2026, 10, 1)
COUNTRIES, CATS = ["IT", "US"], ["24", "10"]


def day(n):
    return D0 + timedelta(days=n)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def at(n, hour=23):
    return datetime(D0.year, D0.month, D0.day, hour, 59, tzinfo=timezone.utc) + timedelta(days=n)


PUB = {  # publication of the charting videos
    "a": at(-30), "b": at(-20), "c": at(-25),
    "n1": at(-1, 10), "n2": at(0, 8), "x": at(1), "s1": at(0, 9), "y": at(2, 6),
}
CHANNEL = {"a": "UCold", "b": "UCold", "c": "UCold", "n1": "UCnew", "n2": "UCsmall", "x": "UCnew",
           "s1": "UCnew", "y": "UCnew"}
# 01 section 1 (27/09/2026): only long-form opens a record. s1 is a Short.
DURATION = {"s1": "PT45S"}
LONG = "PT12M"


class FakeYouTube:
    def __init__(self):
        self.charts = {}      # (country, cat) -> [(vid, views)] or an int status
        self.calls = []
        # UCnew: 12 long-form at 1,000 views, one every 5 days from 8 days before n1
        self.uploads = {
            "UCnew": [(f"up{i}", PUB["n1"] - timedelta(days=8 + 5 * i), LONG, 1000) for i in range(12)],
            "UCsmall": [(f"sm{i}", PUB["n2"] - timedelta(days=10 + i), LONG, 50) for i in range(3)],
            "UCold": [],
        }
        self.meta = {"UCnew": {"customUrl": "@newchan", "title": "New Channel"},
                     "UCsmall": {"title": "Some Artist - Topic"},
                     "UCold": {"customUrl": "@old", "title": "Old"}}

    def __call__(self, request):
        u = urlparse(request.url)
        ep = u.path.rsplit("/", 1)[-1]
        qs = {k: v[0] for k, v in parse_qs(u.query).items()}
        self.calls.append(ep if qs.get("chart") != "mostPopular" else "chart")
        if qs.get("chart") == "mostPopular":
            spec = self.charts.get((qs["regionCode"], qs["videoCategoryId"]), [])
            if isinstance(spec, int):
                return (spec, {}, json.dumps({"error": {"errors": [{"reason": "quotaExceeded"}]}}))
            items = [{"id": v, "snippet": {"channelId": CHANNEL[v], "publishedAt": iso(PUB[v]),
                                           "title": f"title {v}", "channelTitle": CHANNEL[v]},
                      "contentDetails": {"duration": DURATION.get(v, LONG)},
                      "statistics": {"viewCount": str(views)}} for v, views in spec]
            return (200, {}, json.dumps({"items": items}))
        if ep == "channels":
            items = [{"id": c, "snippet": self.meta[c], "statistics": {"subscriberCount": "5000"},
                      "contentDetails": {"relatedPlaylists": {"uploads": "PL" + c}}}
                     for c in qs["id"].split(",") if c in self.meta]
            return (200, {}, json.dumps({"items": items}))
        if ep == "playlists":
            items = [{"id": pl, "contentDetails": {"itemCount": len(self.uploads.get(pl[2:], []))}}
                     for pl in qs["id"].split(",")]
            return (200, {}, json.dumps({"items": items}))
        if ep == "playlistItems":
            ch = qs["playlistId"][2:]
            if ch in getattr(self, "fail_uploads", ()):
                return (503, {}, "{}")
            items = [{"contentDetails": {"videoId": v, "videoPublishedAt": iso(p)}}
                     for v, p, _, _ in self.uploads.get(ch, [])]
            return (200, {}, json.dumps({"items": items}))
        if ep == "videos" and qs.get("part") == "snippet":    # titles, reprocess_day
            items = [{"id": v, "snippet": {"title": f"title {v}", "channelTitle": CHANNEL[v]}}
                     for v in qs["id"].split(",") if v in CHANNEL]
            return (200, {}, json.dumps({"items": items}))
        if ep == "videos":
            allv = {v: (d, n) for ups in self.uploads.values() for v, _, d, n in ups}
            items = [{"id": v, "contentDetails": {"duration": allv[v][0]},
                      "statistics": {"viewCount": str(allv[v][1])}}
                     for v in qs["id"].split(",") if v in allv]
            return (200, {}, json.dumps({"items": items}))
        return (400, {}, "{}")


@pytest.fixture
def world(db):
    fake = FakeYouTube()
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        for ep in ("videos", "channels", "playlists", "playlistItems"):
            rsps.add_callback(responses.GET, f"https://www.googleapis.com/youtube/v3/{ep}", callback=fake)
        yield fake, PgClient(db), db


def run(client, fake, n, *, snapshot_only=False, limit=None, storage=None):
    fake.calls = []
    row = eng.run_daily(client, day(n), api_key=KEY, countries=COUNTRIES, categories=CATS,
                        snapshot_only=snapshot_only, quota=q.QuotaCounter(limit=limit or 9900),
                        rng=random.Random(n), sleep=lambda s: None, now=at(n),
                        storage=storage if storage is not None else retention.MemoryStorage())
    return row


def one(db, query, *args):
    with db.cursor() as cur:
        cur.execute(query, args)
        return cur.fetchall()


def posts(db):
    return {r[0]: r[1:] for r in one(db, """
        select external_post_id, status, method_version, entered_on, baseline_rule,
               baseline_score, vpi_ratio, vpi_level, entry_certain, gap_days, left_on,
               days_charting, vpi_max, vpi_max_on, views_final
        from posts where method_version = 'v2'""")}


def daily(db, vid):
    return one(db, """select pd.day, pd.day_index, pd.views, pd.vpi_ratio from post_daily pd
                      join posts p on p.id = pd.post_id where p.external_post_id = %s
                      order by pd.day""", vid)


def ingest(db, n):
    cols = ["outcome", "quota_total", "quota_charts", "entries", "exits", "updated", "notes"]
    r = one(db, f"select {', '.join(cols)} from ingest_run where day = %s", day(n))
    return dict(zip(cols, r[0])) if r else None


def test_four_days(world):
    fake, client, db = world

    # --- day 0: snapshot only, no records
    fake.charts = {("IT", "24"): [("a", 900), ("b", 800)], ("US", "10"): [("c", 700)]}
    run(client, fake, 0, snapshot_only=True)
    assert one(db, "select count(*) from trend_snapshot where day = %s", day(0)) == [(3,)]
    assert posts(db) == {}
    r0 = ingest(db, 0)
    assert r0["outcome"] == "ok" and r0["quota_total"] == len(fake.calls) == 4

    # --- day 1: two entries, one standard, one not computable; a Short enters
    # too and opens no record (the census still stores it)
    fake.charts = {("IT", "24"): [("a", 950), ("n1", 5000), ("s1", 9000)],
                   ("US", "10"): [("c", 720), ("n2", 300)]}
    run(client, fake, 1)
    p = posts(db)
    assert set(p) == {"n1", "n2"}
    assert p["n1"][:9] == ("ACTIVE", "v2", day(1), "standard", 1000, 5.0, 2, True, 0) or \
        p["n1"][:9] == ("ACTIVE", "v2", day(1), "standard", 1000.0, 5.0, 2, True, 0)
    assert p["n2"][3] == "not_computable" and p["n2"][4] is None and p["n2"][5] is None
    assert daily(db, "n1") == [(day(1), 1, 5000, 5.0)]
    assert daily(db, "n2") == [(day(1), 1, 300, None)]
    r1 = ingest(db, 1)
    assert r1["outcome"] == "ok" and r1["entries"] == 2 and r1["exits"] == 0
    assert one(db, "select format from trend_snapshot where day = %s and video_id = 's1'", day(1)) == [("SHORT",)]
    assert one(db, "select discards->>'out_of_perimeter_short', entering_channels, entering_long_channels, "
                   "baselines_complete from ingest_run where day = %s", day(1)) == [("1", 2, 2, True)]
    assert r1["quota_total"] == len(fake.calls)
    row = one(db, """select platform, author_handle, auto_generated_channel, post_url, category,
                            country, countries, categories, age_at_first_obs_days, baseline_samples,
                            array_length(baseline_video_ids, 1), vpi_level_name, claim_token like 'iosa_%%'
                     from posts where external_post_id = 'n1'""")[0]
    assert row == ("YOUTUBE", "@newchan", False, "https://www.youtube.com/watch?v=n1", "Entertainment",
                   "IT", ["IT"], ["Entertainment"], 2, 12, 12, "Lvl 2 - Moderate", True)
    assert one(db, "select author_handle, auto_generated_channel, vpi_level_name, vpi_color "
                   "from posts where external_post_id = 'n2'") == [(None, True, None, None)]

    # --- day 2: partial (US/10 unread: 503 after the retries): views where we
    # read, no exits. (A 403 stops the whole run, so with parallel
    # reads which slices got read first is not deterministic; the 403 path is
    # covered in test_census.py and test_quota.py.)
    fake.charts = {("IT", "24"): [("a", 990), ("n1", 8000), ("s1", 9500)], ("US", "10"): 503}
    run(client, fake, 2)
    r2 = ingest(db, 2)
    assert r2["outcome"] == "partial" and r2["exits"] == 0
    assert posts(db)["n2"][0] == "ACTIVE"            # unread is not absent
    assert daily(db, "n1")[-1] == (day(2), 2, 8000, 8.0)
    assert posts(db)["n1"][11:13] == (8.0, day(2))   # peak observed

    # --- day 3: complete; reference is day 1 (day 2 was partial)
    fake.charts = {("IT", "24"): [("a", 1000), ("s1", 9900)], ("US", "10"): [("c", 730), ("x", 4000)]}
    run(client, fake, 3)
    p = posts(db)
    assert p["x"][7:9] == (False, 2)                 # entry after a partial day: uncertain
    assert p["n1"][0] == "CLOSED" and p["n1"][9] == day(3) and p["n1"][10] == 2
    assert float(p["n1"][13]) == 8000               # views_final = last observed
    assert p["n2"][0] == "CLOSED" and p["n2"][10] == 1
    assert ingest(db, 3)["outcome"] == "ok" and ingest(db, 3)["exits"] == 2
    # nothing written by any day outside v2
    assert one(db, "select count(*) from posts where method_version = 'v2' and baseline_rule is null") == [(0,)]


def test_one_reading_a_day(world):
    fake, client, db = world
    fake.charts = {("IT", "24"): [("a", 1)]}
    run(client, fake, 0, snapshot_only=True)
    with pytest.raises(eng.RunAlreadyExists):
        run(client, fake, 0, snapshot_only=True)
    assert fake.calls == []                          # refused before any API call


def test_an_incomplete_day0_is_no_reference_and_says_to_rerun(world):
    fake, client, db = world
    fake.charts = {("IT", "24"): [("a", 1)], ("US", "10"): 403}
    run(client, fake, 0, snapshot_only=True)
    assert ingest(db, 0)["outcome"] == "partial"
    assert "the next reading is day 0 again" in ingest(db, 0)["notes"]
    # had day 1 run anyway: no reference, so no entry is manufactured
    fake.charts = {("IT", "24"): [("a", 2), ("n1", 5000)], ("US", "10"): [("c", 700)]}
    run(client, fake, 1)
    assert posts(db) == {}


def test_the_brake_records_the_entries_it_did_not_reach_without_a_vpi(world):
    # GATE-2 (01 §2): valid records, baseline_rule = quota_stop, counted. Since
    # 27/09/2026 the brake is an incident, and the census alone decides the
    # outcome: this census was complete.
    fake, client, db = world
    fake.charts = {("IT", "24"): [("a", 900)], ("US", "10"): [("c", 700)]}
    run(client, fake, 0, snapshot_only=True)
    fake.charts = {("IT", "24"): [("a", 950), ("n1", 5000)], ("US", "10"): [("c", 720)]}
    run(client, fake, 1, limit=5)                    # 4 chart calls + 1 channels, then the brake
    r = ingest(db, 1)
    assert r["outcome"] == "ok" and r["quota_total"] == 5 == len(fake.calls)
    assert one(db, "select baselines_complete from ingest_run where day = %s", day(1)) == [(False,)]
    p = posts(db)
    assert set(p) == {"n1"} and p["n1"][3] == "quota_stop"
    assert p["n1"][4] is None and p["n1"][5] is None             # no baseline, no VPI
    assert daily(db, "n1") == [(day(1), 1, 5000, None)]           # views still observed
    assert "INCIDENT: 1 entries recorded without a VPI (quota_stop)" in r["notes"]
    assert one(db, "select discards->>'quota_stop' from ingest_run where day = %s", day(1)) == [("1",)]


def test_complete_census_incomplete_baselines_is_the_reference_and_closes_exits(world):
    """02 section 4.6 (27/09/2026): census completeness and baseline
    completeness are two states. A brake during the baselines leaves the
    census complete: the day is the next reference, exits are closed, the
    next day's entries are certain."""
    fake, client, db = world
    fake.charts = {("IT", "24"): [("a", 900)], ("US", "10"): [("c", 700)]}
    run(client, fake, 0, snapshot_only=True)
    fake.charts = {("IT", "24"): [("a", 950), ("n1", 5000)], ("US", "10"): [("c", 720), ("n2", 300)]}
    run(client, fake, 1)
    assert set(posts(db)) == {"n1", "n2"}
    # day 2: n2 leaves every chart, x enters; the brake stops the baselines
    fake.charts = {("IT", "24"): [("a", 960), ("n1", 6000)], ("US", "10"): [("c", 725), ("x", 4000)]}
    run(client, fake, 2, limit=5)
    r2 = ingest(db, 2)
    assert r2["outcome"] == "ok" and r2["exits"] == 1
    assert one(db, "select baselines_complete from ingest_run where day = %s", day(2)) == [(False,)]
    p = posts(db)
    assert p["n2"][0] == "CLOSED" and p["n2"][9] == day(2)       # exit observed
    assert p["x"][3] == "quota_stop" and p["x"][7:9] == (True, 0)
    # day 3: the reference is day 2, so y is certain, no gap
    fake.charts = {("IT", "24"): [("a", 970), ("n1", 6500), ("y", 3000)], ("US", "10"): [("c", 726), ("x", 4100)]}
    run(client, fake, 3)
    p = posts(db)
    assert p["y"][7:9] == (True, 0)                   # gap_days 0: the day before was the reference
    assert "x" in p and p["x"][0] == "ACTIVE"                    # not re-entered, still charting


def test_an_entry_whose_reads_fail_is_a_record_without_a_vpi_and_the_day_stays_the_reference(world):
    fake, client, db = world
    fake.charts = {("IT", "24"): [("a", 900)], ("US", "10"): [("c", 700)]}
    run(client, fake, 0, snapshot_only=True)
    fake.fail_uploads = {"UCnew"}
    fake.charts = {("IT", "24"): [("a", 950), ("n1", 5000)], ("US", "10"): [("c", 720)]}
    run(client, fake, 1)
    r = ingest(db, 1)
    assert r["outcome"] == "ok" and "1 entries recorded without a VPI after failed reads" in r["notes"]
    p = posts(db)
    assert p["n1"][3] == "read_failed" and p["n1"][4] is None and p["n1"][5] is None
    assert one(db, "select baselines_complete from ingest_run where day = %s", day(1)) == [(False,)]


def test_the_inventory_is_persisted_and_reused_the_next_day(world):
    fake, client, db = world
    fake.charts = {("IT", "24"): [("a", 900)], ("US", "10"): [("c", 700)]}
    run(client, fake, 0, snapshot_only=True)
    fake.charts = {("IT", "24"): [("a", 950), ("n1", 5000)], ("US", "10"): [("c", 720)]}
    run(client, fake, 1)
    rows = one(db, "select channel_id, jsonb_object_keys(items) from channel_inventory order by 2")
    assert {r[0] for r in rows} == {"UCnew"} and len(rows) == 12
    assert one(db, "select refreshed_on from channel_inventory") == [(day(1),)]


def test_every_posts_row_carries_method_version_v2_explicitly(world, monkeypatch):
    fake, client, db = world
    fake.charts = {("IT", "24"): [("a", 900)]}
    run(client, fake, 0, snapshot_only=True)
    written = []
    real_table = client.table

    def spy(name):
        t = real_table(name)
        if name == "posts":
            orig = t.insert

            def insert(rows):
                written.extend(rows)
                return orig(rows)
            t.insert = insert
        return t
    monkeypatch.setattr(client, "table", spy)
    fake.charts = {("IT", "24"): [("a", 900), ("n1", 5000), ("n2", 10)]}
    run(client, fake, 1)
    assert len(written) == 2 and all(r["method_version"] == "v2" for r in written)


def test_the_retention_runs_after_a_complete_census_only(world, monkeypatch):
    # 02 §3.1 (28/09/2026): the purge follows a complete census, day 0
    # included, so the day it runs on is the next reference; a partial
    # census purges nothing.
    fake, client, db = world
    calls = []
    monkeypatch.setattr(eng, "_retention", lambda c, d, notes, s=None: calls.append(d))
    fake.charts = {("IT", "24"): [("a", 900)], ("US", "10"): [("c", 700)]}
    run(client, fake, 0, snapshot_only=True)
    assert calls == [day(0)]
    fake.charts = {("IT", "24"): [("a", 950)], ("US", "10"): 403}
    run(client, fake, 1)
    assert ingest(db, 1)["outcome"] == "partial" and calls == [day(0)]
    fake.charts = {("IT", "24"): [("a", 990)], ("US", "10"): [("c", 800)]}
    run(client, fake, 2)
    assert ingest(db, 2)["outcome"] == "ok" and calls == [day(0), day(2)]


def test_the_snapshot_statistics_are_refreshed_before_the_entries_are_read(world, monkeypatch):
    # INC-1 (reading of 2026-09-28): entries_of_day planned on stale
    # statistics hit the 8 s statement timeout.
    fake, client, db = world
    calls = []
    real_rpc = client.rpc

    def rpc(fn, params):
        calls.append(fn)
        return real_rpc(fn, params)
    monkeypatch.setattr(client, "rpc", rpc)
    fake.charts = {("IT", "24"): [("a", 900)], ("US", "10"): [("c", 700)]}
    run(client, fake, 0, snapshot_only=True)
    assert calls[0] == "analyze_snapshot"
    calls.clear()
    fake.charts = {("IT", "24"): [("a", 950), ("n1", 5000)], ("US", "10"): [("c", 800)]}
    run(client, fake, 1)
    assert calls.index("analyze_snapshot") < calls.index("entries_of_day")
    assert ingest(db, 1)["outcome"] == "ok"


def test_the_entry_query_has_its_index_and_the_analyze_is_service_role_only(db):
    with db.cursor() as cur:
        cur.execute("select indexdef from pg_indexes where indexname = 'posts_external_post_id_idx'")
        assert "(external_post_id)" in cur.fetchone()[0]
        cur.execute("select has_function_privilege('anon', 'public.analyze_snapshot()', 'execute'), "
                    "has_function_privilege('authenticated', 'public.analyze_snapshot()', 'execute'), "
                    "has_function_privilege('service_role', 'public.analyze_snapshot()', 'execute')")
        assert cur.fetchone() == (False, False, True)


# --- INC-1b: reprocess_day ---------------------------------------------------


def _crash_after_census(monkeypatch):
    """The 28/09 failure: the census completes, the entry query then breaks."""
    real = census.entries
    state = {"n": 0}

    def boom(client, d):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("canceling statement due to statement timeout")
        return real(client, d)
    monkeypatch.setattr(census, "entries", boom)


DAY1 = {("IT", "24"): [("a", 950), ("n1", 5000), ("s1", 9000)], ("US", "10"): [("c", 720), ("n2", 300)]}


def _day0(client, fake):
    fake.charts = {("IT", "24"): [("a", 900), ("b", 800)], ("US", "10"): [("c", 700)]}
    run(client, fake, 0, snapshot_only=True)


def reprocess(client, fake, n, **kw):
    fake.calls = []
    return eng.reprocess_day(client, day(n), api_key=KEY, sleep=lambda s: None,
                             storage=retention.MemoryStorage(), **kw)


def test_a_crash_after_a_complete_census_is_reprocessed_from_the_snapshot(world, monkeypatch):
    fake, client, db = world
    _day0(client, fake)
    fake.charts = DAY1
    _crash_after_census(monkeypatch)
    with pytest.raises(RuntimeError):
        run(client, fake, 1)
    r = one(db, "select outcome, census_complete, quota_charts, videos_seen from ingest_run where day = %s", day(1))[0]
    assert r[0] == "failed" and r[1] is True and posts(db) == {}          # the census stays on record
    started = one(db, "select started_at from ingest_run where day = %s", day(1))[0][0]
    charts_before = r[2]

    out = reprocess(client, fake, 1)
    assert "chart" not in fake.calls                                       # the charts are not read again
    p = posts(db)
    assert set(p) == {"n1", "n2"}                                          # same records as a night without the crash
    assert p["n1"][3:9] == ("standard", 1000, 5.0, 2, True, 0) or p["n1"][3:9] == ("standard", 1000.0, 5.0, 2, True, 0)
    assert p["n2"][3] == "not_computable"
    assert daily(db, "n1") == [(day(1), 1, 5000, 5.0)]                     # the numerator is the 23:59 snapshot
    # detected_at: when the census saw it; baseline_computed_at: when the
    # baseline was actually read (the test clock puts the census in the future)
    rows = one(db, "select content_text, detected_at = %s, reprocessed_at is not null, "
                   "baseline_computed_at is not null, country, category from posts "
                   "where external_post_id = 'n1'", started)
    assert rows == [("title n1", True, True, True, "IT", "Entertainment")]
    run_row = one(db, "select outcome, census_complete, reprocessed_at is not null, entries, "
                      "quota_charts, quota_total > quota_charts, notes from ingest_run where day = %s", day(1))[0]
    assert run_row[:6] == ("ok", True, True, 2, charts_before, True)
    assert "processing failed at" in run_row[6] and "reprocessed at" in run_row[6]
    assert out["outcome"] == "ok"


def test_a_complete_census_is_the_reference_even_when_its_processing_failed(world, monkeypatch):
    fake, client, db = world
    _day0(client, fake)
    fake.charts = DAY1
    _crash_after_census(monkeypatch)
    with pytest.raises(RuntimeError):
        run(client, fake, 1)
    reprocess(client, fake, 1)
    fake.charts = {("IT", "24"): [("a", 990), ("n1", 8000), ("s1", 9500)],
                   ("US", "10"): [("c", 730), ("n2", 320), ("x", 4000)]}
    run(client, fake, 2)
    p = posts(db)
    assert p["x"][7:9] == (True, 0)            # reference is day 1: certain, no gap


def test_reprocess_refuses_what_it_cannot_prove(world, monkeypatch):
    fake, client, db = world
    _day0(client, fake)
    fake.charts = {("IT", "24"): [("a", 950)], ("US", "10"): 503}          # incomplete census
    run(client, fake, 1)
    with pytest.raises(eng.ReprocessRefused, match="census is not complete"):
        reprocess(client, fake, 1)
    fake.charts = DAY1
    _crash_after_census(monkeypatch)
    with pytest.raises(RuntimeError):
        run(client, fake, 2)
    with db.cursor() as cur:                                               # a snapshot not the one counted
        cur.execute("delete from trend_snapshot where day = %s and video_id = 'a'", (day(2),))
    with pytest.raises(eng.ReprocessRefused, match="the census counted"):
        reprocess(client, fake, 2)
    with pytest.raises(eng.ReprocessRefused, match="no reading"):
        reprocess(client, fake, 5)
    with pytest.raises(eng.ReprocessRefused, match="later reading of"):
        reprocess(client, fake, 0)            # a later day (1) is not a complete census


def test_a_crashed_day_left_until_after_the_next_night_is_still_recovered(world, monkeypatch):
    # day 1 crashes after its census and is not resumed; day 2 runs with day 1
    # as its reference; day 1 is reprocessed afterwards and caught up
    fake, client, db = world
    _day0(client, fake)
    fake.charts = DAY1
    _crash_after_census(monkeypatch)
    with pytest.raises(RuntimeError):
        run(client, fake, 1)
    fake.charts = {("IT", "24"): [("a", 990), ("n1", 8000), ("s1", 9500)],
                   ("US", "10"): [("c", 730), ("x", 4000)]}          # n2 has left
    run(client, fake, 2)
    p = posts(db)
    assert set(p) == {"x"} and p["x"][7:9] == (True, 0)   # day 1 is the reference: no false entry
    reprocess(client, fake, 1)
    p = posts(db)
    assert set(p) == {"n1", "n2", "x"} and p["n1"][2] == day(1) and p["n1"][7:9] == (True, 0)
    assert daily(db, "n1") == [(day(1), 1, 5000, 5.0), (day(2), 2, 8000, 8.0)]
    assert p["n1"][11:13] == (8.0, day(2))                # peak observed across the catch-up
    assert p["n2"][0] == "CLOSED" and p["n2"][9] == day(2) and p["n2"][10] == 1


def test_the_records_the_brake_left_without_a_vpi_get_one_the_next_day(world):
    fake, client, db = world
    _day0(client, fake)
    fake.charts = DAY1
    run(client, fake, 1, limit=5)             # 4 chart calls + 1 channels, then the brake
    assert {v[3] for v in posts(db).values()} == {"quota_stop"}
    reprocess(client, fake, 1)
    p = posts(db)
    assert p["n1"][3:6] == ("standard", 1000, 5.0) or p["n1"][3:6] == ("standard", 1000.0, 5.0)
    assert p["n2"][3] == "not_computable"
    assert daily(db, "n1") == [(day(1), 1, 5000, 5.0)]
    assert one(db, "select count(*) from posts where reprocessed_at is not null "
                   "and baseline_computed_at is not null") == [(2,)]
    assert one(db, "select baselines_complete, outcome from ingest_run where day = %s", day(1)) == [(True, "ok")]


def test_a_record_with_a_baseline_is_never_touched_by_reprocess(world):
    fake, client, db = world
    _day0(client, fake)
    fake.charts = DAY1
    run(client, fake, 1)
    before = one(db, "select external_post_id, baseline_score, baseline_computed_at, reprocessed_at "
                     "from posts order by 1")
    reprocess(client, fake, 1)
    assert one(db, "select external_post_id, baseline_score, baseline_computed_at, reprocessed_at "
                   "from posts order by 1") == before



# --- the second attempt on an incomplete census (owner rule 29/09/2026) -------


def test_a_second_attempt_reads_an_incomplete_census_again_and_keeps_both(world):
    fake, client, db = world
    _day0(client, fake)
    fake.charts = {("IT", "24"): [("a", 950), ("n1", 5000), ("b", 100)], ("US", "10"): 503}
    run(client, fake, 1)                                   # incomplete: US/10 unread
    first = one(db, "select census_complete, quota_total from ingest_run where day = %s", day(1))[0]
    assert first[0] is False
    fake.charts = DAY1                                     # b has left by the second read
    fake.calls = []
    eng.run_daily(client, day(1), api_key=KEY, countries=COUNTRIES, categories=CATS,
                  quota=q.QuotaCounter(limit=9900), rng=random.Random(11), sleep=lambda s: None,
                  now=at(1, 0), storage=retention.MemoryStorage(), rerun=True)
    r = one(db, "select outcome, census_complete, videos_seen, quota_total, notes from ingest_run "
                "where day = %s", day(1))[0]
    assert r[:2] == ("ok", True)
    assert one(db, "select count(*) from trend_snapshot where day = %s", day(1))[0][0] == r[2]
    assert one(db, "select count(*) from trend_snapshot where day = %s and video_id = 'b'", day(1)) == [(1,)]
    assert r[3] == first[1] + len(fake.calls)              # both attempts counted, one day
    assert "second attempt" in r[4] and "seen only by the first attempt" in r[4]
    p = posts(db)
    assert {"n1", "n2"} <= set(p)                          # n2 was in the unread slice
    assert one(db, "select count(*) from posts where external_post_id = 'n1'") == [(1,)]   # not repeated


def test_a_second_attempt_never_reads_a_complete_census_again(world, monkeypatch):
    fake, client, db = world
    _day0(client, fake)
    fake.charts = DAY1
    _crash_after_census(monkeypatch)
    with pytest.raises(RuntimeError):
        run(client, fake, 1)
    fake.calls = []
    with pytest.raises(eng.ReprocessRefused, match="never read again"):
        eng.run_daily(client, day(1), api_key=KEY, countries=COUNTRIES, categories=CATS,
                      quota=q.QuotaCounter(limit=9900), sleep=lambda s: None, now=at(1, 0), rerun=True)
    assert fake.calls == []                                # not one chart read
