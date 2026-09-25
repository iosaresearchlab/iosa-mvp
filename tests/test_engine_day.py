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
    "n1": at(-1, 10), "n2": at(0, 8), "x": at(1),
}
CHANNEL = {"a": "UCold", "b": "UCold", "c": "UCold", "n1": "UCnew", "n2": "UCsmall", "x": "UCnew"}


class FakeYouTube:
    def __init__(self):
        self.charts = {}      # (country, cat) -> [(vid, views)] or an int status
        self.calls = []
        # UCnew: 12 Shorts at 1,000 views, one every 5 days from 8 days before n1
        self.uploads = {
            "UCnew": [(f"up{i}", PUB["n1"] - timedelta(days=8 + 5 * i), "PT40S", 1000) for i in range(12)],
            "UCsmall": [(f"sm{i}", PUB["n2"] - timedelta(days=10 + i), "PT40S", 50) for i in range(3)],
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
                      "contentDetails": {"duration": "PT45S"},
                      "statistics": {"viewCount": str(views)}} for v, views in spec]
            return (200, {}, json.dumps({"items": items}))
        if ep == "channels":
            items = [{"id": c, "snippet": self.meta[c], "statistics": {"subscriberCount": "5000"}}
                     for c in qs["id"].split(",") if c in self.meta]
            return (200, {}, json.dumps({"items": items}))
        if ep == "playlistItems":
            ch = "UC" + qs["playlistId"][2:]
            items = [{"contentDetails": {"videoId": v, "videoPublishedAt": iso(p)}}
                     for v, p, _, _ in self.uploads.get(ch, [])]
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
        for ep in ("videos", "channels", "playlistItems"):
            rsps.add_callback(responses.GET, f"https://www.googleapis.com/youtube/v3/{ep}", callback=fake)
        yield fake, PgClient(db), db


def run(client, fake, n, *, snapshot_only=False, limit=None):
    fake.calls = []
    row = eng.run_daily(client, day(n), api_key=KEY, countries=COUNTRIES, categories=CATS,
                        snapshot_only=snapshot_only, quota=q.QuotaCounter(limit=limit or 9500),
                        rng=random.Random(n), sleep=lambda s: None, now=at(n))
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

    # --- day 0: snapshot only, permanent, no records
    fake.charts = {("IT", "24"): [("a", 900), ("b", 800)], ("US", "10"): [("c", 700)]}
    run(client, fake, 0, snapshot_only=True)
    assert one(db, "select count(*), bool_and(permanent) from trend_snapshot where day = %s", day(0)) == [(3, True)]
    assert posts(db) == {}
    r0 = ingest(db, 0)
    assert r0["outcome"] == "ok" and r0["quota_total"] == len(fake.calls) == 4

    # --- day 1: two entries, one standard, one not computable
    fake.charts = {("IT", "24"): [("a", 950), ("n1", 5000)], ("US", "10"): [("c", 720), ("n2", 300)]}
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
    fake.charts = {("IT", "24"): [("a", 990), ("n1", 8000)], ("US", "10"): 503}
    run(client, fake, 2)
    r2 = ingest(db, 2)
    assert r2["outcome"] == "partial" and r2["exits"] == 0
    assert posts(db)["n2"][0] == "ACTIVE"            # unread is not absent
    assert daily(db, "n1")[-1] == (day(2), 2, 8000, 8.0)
    assert posts(db)["n1"][11:13] == (8.0, day(2))   # peak observed

    # --- day 3: complete; reference is day 1 (day 2 was partial)
    fake.charts = {("IT", "24"): [("a", 1000)], ("US", "10"): [("c", 730), ("x", 4000)]}
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
    assert "re-run day 0" in ingest(db, 0)["notes"]
    # had day 1 run anyway: no reference, so no entry is manufactured
    fake.charts = {("IT", "24"): [("a", 2), ("n1", 5000)], ("US", "10"): [("c", 700)]}
    run(client, fake, 1)
    assert posts(db) == {}


def test_the_brake_records_the_entries_it_did_not_reach_without_a_vpi(world):
    # GATE-2 (01 §2): valid records, baseline_rule = quota_stop, counted; the
    # run ends partial, so no exit.
    fake, client, db = world
    fake.charts = {("IT", "24"): [("a", 900)], ("US", "10"): [("c", 700)]}
    run(client, fake, 0, snapshot_only=True)
    fake.charts = {("IT", "24"): [("a", 950), ("n1", 5000)], ("US", "10"): [("c", 720)]}
    run(client, fake, 1, limit=5)                    # 4 chart calls + 1 channels, then the brake
    r = ingest(db, 1)
    assert r["outcome"] == "partial" and r["quota_total"] == 5 == len(fake.calls)
    p = posts(db)
    assert set(p) == {"n1"} and p["n1"][3] == "quota_stop"
    assert p["n1"][4] is None and p["n1"][5] is None             # no baseline, no VPI
    assert daily(db, "n1") == [(day(1), 1, 5000, None)]           # views still observed
    assert "1 entries recorded without a VPI (quota_stop)" in r["notes"]
    assert one(db, "select discards->>'quota_stop' from ingest_run where day = %s", day(1)) == [("1",)]
    assert r["exits"] == 0


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
