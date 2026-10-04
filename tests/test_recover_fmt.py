"""FMT-2: backend/recover_fmt.py on PostgreSQL (every migration) and a fake
YouTube API. 0 units. docs/02 section 4.10; 08 FMT-2, closing check.

Days: D0 26/09 (reference only), D1 27/09 = INDEX_START_DATE, D2 28/09, D3
29/09, the first reading under FMT-1. The recovery runs at 06:00 UTC on 30/09.
D0 and D1 have left the retention window: their snapshots are read from the
archive; D2 and D3 from the table.
"""

import json
import random
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
import responses

psycopg = pytest.importorskip("psycopg")

import baseline as bl  # noqa: E402
import recover_fmt as rf  # noqa: E402
import retention  # noqa: E402
import vpi_core as core  # noqa: E402
import vpi_engine as eng  # noqa: E402
from tests.pg_client import PgClient  # noqa: E402

KEY = "test-key-not-real"
D0, D1, D2, D3 = date(2026, 9, 26), date(2026, 9, 27), date(2026, 9, 28), date(2026, 9, 29)
NOW = datetime(2026, 9, 30, 6, 0, tzinfo=timezone.utc)
EMBED = {"vertical": ("563", "1000"), "square": ("1000", "1000"), "wide": ("1000", "563")}


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def at(d, h=12):
    return datetime(d.year, d.month, d.day, h, tzinfo=timezone.utc)


# chart videos: channel, publication, duration, shape (None: not returned)
CHART = {
    "W": ("UCw", at(D1, 6) - timedelta(days=1), "PT2M", "wide"),
    "V": ("UCw", at(D1, 6) - timedelta(days=1), "PT1M40S", "vertical"),
    "U": ("UCw", at(D1, 6) - timedelta(days=1), "PT50S", None),
    "Z": ("UCz", at(D2, 6) - timedelta(days=1), "PT1M30S", "wide"),
    "Y": ("UCy", at(D1, 6) - timedelta(days=1), "PT2M", "wide"),
    "a": ("UCold", at(D0) - timedelta(days=30), "PT12M", "wide"),
    "s0": ("UCold", at(D0) - timedelta(days=3), "PT40S", "vertical"),
}
# uploads for the baselines: (id, publication, duration, views, shape)
UPLOADS = {
    "UCw": [(f"w{i}", CHART["W"][1] - timedelta(days=10 + 8 * i), "PT12M", 1000, "wide") for i in range(6)],
    "UCz": [(f"z{i}", CHART["Z"][1] - timedelta(days=10 + 8 * i), "PT12M", 500, "wide") for i in range(6)],
}
# phase 2: the records opened by the nights under the duration-only rule
R_PUB = at(date(2026, 9, 25))
ITEMS = {}          # video id -> (duration, views, shape) for the inventory items phase 2 reads


def _snap(d, vid, fmt, views):
    ch, pub, _, _ = CHART[vid]
    return (d, vid, ch, fmt, pub, views, ["IT", "US"], ["24"])


SNAPSHOTS = {
    D0: [_snap(D0, "a", "LONG", 100), _snap(D0, "s0", "SHORT", 10)],
    D1: [_snap(D1, "a", "LONG", 110), _snap(D1, "s0", "SHORT", 11), _snap(D1, "W", "SHORT", 5000),
         _snap(D1, "V", "SHORT", 7000), _snap(D1, "U", "SHORT", 900), _snap(D1, "Y", "SHORT", 100)],
    D2: [_snap(D2, "a", "LONG", 120), _snap(D2, "W", "SHORT", 8000), _snap(D2, "Z", "SHORT", 3000)],
    D3: [_snap(D3, "a", "LONG", 130), _snap(D3, "Z", "LONG", 4000)],
}


class FakeYouTube:
    def __init__(self):
        self.calls = []

    def __call__(self, request):
        u = urlparse(request.url)
        ep = u.path.rsplit("/", 1)[-1]
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        self.calls.append((ep, q))
        if ep == "channels":
            items = [{"id": c, "snippet": {"customUrl": f"@{c}", "title": c},
                      "statistics": {"subscriberCount": "1000"},
                      "contentDetails": {"relatedPlaylists": {"uploads": "UU" + c[2:]}}}
                     for c in q["id"].split(",")]
            return (200, {}, json.dumps({"items": items}))
        if ep == "playlistItems":
            ups = UPLOADS.get("UC" + q["playlistId"][2:], [])
            page = int(q.get("pageToken", "0"))
            body = {"items": [{"contentDetails": {"videoId": v, "videoPublishedAt": iso(p)}}
                              for v, p, *_ in ups[page * 50:(page + 1) * 50]]}
            if (page + 1) * 50 < len(ups):
                body["nextPageToken"] = str(page + 1)
            return (200, {}, json.dumps(body))
        if ep == "videos":
            assert q["maxHeight"] == "1000" and "player" in q["part"].split(",")
            items = []
            for vid in q["id"].split(","):
                if vid in CHART:
                    ch, pub, dur, shape, views = *CHART[vid], 1
                    snippet = {"title": f"title {vid}", "channelTitle": ch, "publishedAt": iso(pub)}
                else:
                    up = next((u for ups in UPLOADS.values() for u in ups if u[0] == vid), None)
                    if up is not None:
                        _, _, dur, views, shape = up
                        if views is None:                      # deleted since: not returned
                            continue
                    elif vid in ITEMS:
                        dur, views, shape = ITEMS[vid]
                    else:
                        continue
                    snippet = {}
                player = {"embedHtml": "<iframe></iframe>"}
                if shape:
                    player["embedWidth"], player["embedHeight"] = EMBED[shape]
                items.append({"id": vid, "snippet": snippet, "contentDetails": {"duration": dur},
                              "statistics": {"viewCount": str(views)}, "status": {"privacyStatus": "public"},
                              "player": player})
            return (200, {}, json.dumps({"items": items}))
        return (400, {}, "{}")

    def of(self, ep):
        return [q for e, q in self.calls if e == ep]

    def units(self):
        return len(self.calls)


@pytest.fixture
def world(db):
    fake = FakeYouTube()
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        for ep in ("videos", "channels", "playlists", "playlistItems"):
            rsps.add_callback(responses.GET, f"https://www.googleapis.com/youtube/v3/{ep}", callback=fake)
        client = PgClient(db)
        storage = retention.MemoryStorage()
        _days(db, client, storage)
        yield fake, client, db, storage


def _days(db, client, storage, snapshots=SNAPSHOTS, archived=(D0, D1)):
    with db.cursor() as cur:
        for d, rows in snapshots.items():
            cur.executemany("insert into trend_snapshot (day, video_id, channel_id, format, published_at, "
                            "views, countries, categories) values (%s, %s, %s, %s, %s, %s, %s, %s)", rows)
            disc = {"no_duration": 0, "no_channel": 0}
            if d >= D3:
                disc["unknown_shape"] = 0
            cur.execute("insert into ingest_run (day, started_at, finished_at, outcome, census_complete, "
                        "videos_seen, discards) values (%s, %s, %s, 'ok', true, %s, %s)",
                        (d, at(d, 23), at(d, 23) + timedelta(minutes=40), len(rows), json.dumps(disc)))
    for d in archived:
        retention.export_day(client, storage, d)
        with db.cursor() as cur:
            cur.execute("delete from trend_snapshot where day = %s", (d,))


def recover(client, storage, fake=None, now=NOW, **kw):
    return rf.run(client, api_key=KEY, now=now, storage=storage, sleep=lambda s: None, **kw)


def one(db, q, *a):
    with db.cursor() as cur:
        cur.execute(q, a)
        return cur.fetchall()


def record(db, vid):
    cols = ["entered_on", "status", "left_on", "days_charting", "views_final", "format", "format_rule",
            "duration_s", "shape", "baseline_rule", "baseline_score", "vpi_max", "vpi_max_on",
            "entry_certain", "gap_days", "reprocessed_at is not null", "content_text", "detected_at"]
    r = one(db, f"select {', '.join(cols)} from posts where external_post_id = %s", vid)
    return dict(zip(cols, r[0])) if r else None


def daily(db, vid):
    return [(d, float(v), float(r) if r is not None else None) for d, v, r in one(db, """
        select pd.day, pd.views, pd.vpi_ratio from post_daily pd join posts p on p.id = pd.post_id
        where p.external_post_id = %s order by pd.day""", vid)]


# --- phase 1 ------------------------------------------------------------------------


def _night_record(client, vid, day, entry_certain=True, **over):
    ch, pub, _, _ = CHART[vid]
    v = {"channel_id": ch, "format": "LONG", "published_at": iso(pub), "views": 1,
         "countries": {"IT"}, "categories": {"24"}, "duration_s": 120, "shape": "wide", "live": False}
    res = {"baseline": None, "samples": 0, "rule": "not_computable", "span_days": None, "video_ids": []}
    rec = eng._record(vid, v, {"gap_days": 0, "entry_certain": entry_certain}, res, {}, day,
                      iso(at(day, 23)))
    rec.update(over)
    return client.table("posts").insert(rec).execute().data[0]


def test_phase1_a_wide_entry_of_a_past_day_opens_the_record_that_night_would_have_opened(world):
    fake, client, db, storage = world
    _night_record(client, "Y", D3)                  # opened later by a night under FMT-1
    out = recover(client, storage)
    w = record(db, "W")
    assert w["entered_on"] == D1 and w["format"] == "LONG" and w["format_rule"] == "youtube_shape"
    assert (w["duration_s"], w["shape"]) == (120, "wide")
    assert w["baseline_rule"] == "standard" and float(w["baseline_score"]) == 1000
    assert w["entry_certain"] is True and w["gap_days"] == 0
    assert w["reprocessed_at is not null"] is True and w["content_text"] == "title W"
    assert w["detected_at"] == at(D1, 23)                       # when the census of D1 saw it
    # the numerators are the stored views of each night: D1 from the archive, D2 from the table
    assert daily(db, "W") == [(D1, 5000.0, 5.0), (D2, 8000.0, 8.0)]
    assert (w["status"], w["left_on"], w["days_charting"], float(w["views_final"])) == ("CLOSED", D3, 2, 8000)
    assert float(w["vpi_max"]) == 8.0 and w["vpi_max_on"] == D2
    # Z entered on D2, still charting on D3: open, two days
    z = record(db, "Z")
    assert z["entered_on"] == D2 and z["status"] == "ACTIVE" and z["shape"] == "wide"
    assert daily(db, "Z") == [(D2, 3000.0, 6.0), (D3, 4000.0, 8.0)]
    # a vertical one, a shape not returned, a video already seen the day before: nothing
    assert record(db, "V") is None and record(db, "U") is None and record(db, "s0") is None
    assert record(db, "Y")["entered_on"] == D3                  # the night's record stays
    run_row = one(db, "select days_done, records_opened, units, finished_at is not null, notes from fmt2_run")[0]
    assert run_row[:4] == ([D1, D2], 2, fake.units(), True)
    assert "1 entries already have a record of another day" in run_row[4]
    assert out["records_opened"] == 2


def test_phase1_reads_only_the_old_shorts_that_have_no_record(world):
    fake, client, db, storage = world
    recover(client, storage)
    asked = {i for q in fake.of("videos") if "snippet" in q["part"] for i in q["id"].split(",")}
    assert asked == {"W", "V", "U", "Y", "Z"}                   # not a or s0: not entries


def test_phase1_is_not_repeated_and_resumes_a_record_left_half_written(world, monkeypatch):
    fake, client, db, storage = world
    real = rf._replay
    state = {"n": 0}

    def crash_once(*a, **k):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("the service was restarted")
        return real(*a, **k)
    monkeypatch.setattr(rf, "_replay", crash_once)
    with pytest.raises(RuntimeError):
        recover(client, storage)
    assert record(db, "W")["entered_on"] == D1 and daily(db, "W") == []       # opened, not replayed
    assert one(db, "select count(*) from quota_ledger where source = 'recovery'") == [(1,)]
    fake.calls = []
    recover(client, storage)                         # the same morning, run again
    assert daily(db, "W") == [(D1, 5000.0, 5.0), (D2, 8000.0, 8.0)] and record(db, "W")["status"] == "CLOSED"
    assert one(db, "select count(*) from posts where external_post_id = 'W'") == [(1,)]
    assert not [q for q in fake.of("videos") if "W" in q["id"].split(",")]  # its shape not read again


# --- phase 2 ------------------------------------------------------------------------


def _phase2_world(client, db, uncovered=True):
    """Night records under the duration-only rule, their inventories and the
    items unknown when FMT-1 started. With `uncovered`, two more records whose
    window the inventory does not fully hold: UCk is capped and its 150 held
    uploads start 20 days before the record (the window starts 90 days
    before); UCu was read back only 30 days."""
    ITEMS.clear()
    store = bl.SupabaseInventory(client)
    specs = {   # channel: (long samples' views, unknown item: (duration, views, shape, in nulls, stored))
        "UCp": ([100, 200, 300, 400, 500], [("PT1M40S", 9999, "vertical", True, None),
                                            ("PT6M", 600, "wide", True, "LONG")]),     # unchanged
        "UCq": ([100, 200, 300, 400, 500], [("PT2M", 600, "wide", True, None)]),       # changed
        "UCr": ([100, 200, 300, 400, 500], [("PT2M30S", 600, "wide", True, "LONG")]), # changed, night-read
    }
    invs, nulls = {}, {}
    for ch, (longs, extra) in specs.items():
        items = {}
        for i, views in enumerate(longs):
            vid = f"{ch}_l{i}"
            items[vid] = [int((R_PUB - timedelta(days=10 + 5 * i)).timestamp()), "LONG"]
            ITEMS[vid] = ("PT10M", views, "wide")
        for j, (dur, views, shape, in_nulls, stored) in enumerate(extra):
            vid = f"{ch}_x{j}"
            items[vid] = [int((R_PUB - timedelta(days=12 + 5 * j)).timestamp()), stored]
            ITEMS[vid] = (dur, views, shape)
            if in_nulls:
                nulls.setdefault(ch, {})[vid] = items[vid][0]
        invs[ch] = {"items": items, "covered_back_to": None, "capped": False, "ended": True,
                    "refreshed_on": "2026-09-27"}
    if uncovered:
        def ep(dt):
            return int(dt.timestamp())
        base = {f"n{i}": [ep(R_PUB - timedelta(days=8 + i)), "LONG"] for i in range(12)}
        x0 = ep(R_PUB - timedelta(days=9, hours=12))
        later = ep(at(D2))                                   # published after the baseline read
        worlds = {
            # capped, an upload newer than the read, window start not reached:
            # phase 3 lists the uploads again and finds what the cap dropped
            "UCk": ({**base, "x0": [x0, None], "new": [later, "LONG"]}, True, {"x0": x0}),
            # the same, and a dropped upload that videos.list no longer returns
            "UCj": ({**base, "new": [later, "LONG"]}, True, {}),
            # capped, nothing newer than the read: holds exactly the read's candidates
            "UCm": ({**base, "x0": [x0, None]}, True, {"x0": x0}),
            # an item unknown at FMT-1 that videos.list no longer returns
            "UCg": ({**base, "x0": [x0, None]}, False, {"x0": x0}),
            # an item unknown at FMT-1 that a night has already removed
            "UCh": (dict(base), False, {"x0": x0}),
        }
        for ch, (its, capped, nl) in worlds.items():
            items = {f"{ch}_{k}": v for k, v in its.items()}
            for vid in items:
                if not (ch == "UCg" and vid.endswith("_x0")):     # UCg_x0: not returned
                    ITEMS[vid] = ("PT2M", 600, "wide")
            nulls[ch] = {f"{ch}_{k}": e for k, e in nl.items()}
            invs[ch] = {"items": items, "refreshed_on": "2026-09-27", "capped": capped,
                        "ended": not capped, "covered_back_to": None}
        # what the uploads playlists list now, newest first: for UCk and UCj
        # the held items plus the ones the cap dropped (30 to 70 days back)
        for ch in ("UCk", "UCj"):
            held = [(v, datetime.fromtimestamp(e, tz=timezone.utc), "PT2M", 600, "wide")
                    for v, (e, _) in invs[ch]["items"].items()]
            dropped = [(f"{ch}_d{i}", R_PUB - timedelta(days=30 + 10 * i), "PT10M", 600, "wide")
                       for i in range(5)]
            dropped.append((f"{ch}_dw", R_PUB - timedelta(days=45), "PT2M",
                            None if ch == "UCj" else 600, "wide"))
            UPLOADS[ch] = sorted(held + dropped, key=lambda u: u[1], reverse=True)
    store.save(invs)
    with db.cursor() as cur:
        for ch, m in nulls.items():
            ids = sorted(m)
            cur.execute("insert into fmt2_null_items (channel_id, ids, epochs) values (%s, %s, %s)",
                        (ch, ids, [m[i] for i in ids]))
    old = core.baseline_v2([{"video_id": f"UCp_l{i}", "published_at": iso(R_PUB - timedelta(days=10 + 5 * i)),
                             "views": v} for i, v in enumerate([100, 200, 300, 400, 500])], "x", iso(R_PUB))
    assert old["baseline"] == 300
    recs = [("r1", "UCp", D1), ("r2", "UCq", D1), ("r4", "UCr", D1), ("r3", "UCq", D1),
            ("n1x", "UCq", D0)]                                   # night 1: out of FMT-2
    if uncovered:
        recs += [("rk", "UCk", D1), ("rj", "UCj", D1), ("rm", "UCm", D1), ("rg", "UCg", D1),
                 ("rh", "UCh", D1)]
    for vid, ch, entered in recs:
        CHART[vid] = (ch, R_PUB, "PT20M", "wide")
        rule = "quota_stop" if vid == "r3" else "standard"
        res = (old if rule == "standard" else
               {"baseline": None, "samples": 0, "rule": "quota_stop", "span_days": None, "video_ids": []})
        v = {"channel_id": ch, "format": "LONG", "published_at": iso(R_PUB), "views": 700,
             "countries": {"IT"}, "categories": {"24"}}
        rec = eng._record(vid, v, {"gap_days": 0, "entry_certain": True}, res, {}, entered,
                          iso(at(entered, 23)), iso(at(entered, 23)))
        rec.update({"format_rule": "duration_180", "duration_s": None, "shape": None, "was_live": None})
        pid = client.table("posts").insert(rec).execute().data[0]["id"]
        if rule == "standard":
            for d, views in ((entered, 700), (entered + timedelta(days=1), 900)):
                client.rpc("apply_daily_views", {"d": d.isoformat(), "rows": [
                    {"post_id": pid, "views": float(views), **eng._vpi_fields(float(views), 300.0)}]}).execute()


ALL = "select * from posts where external_post_id = %s"


def _row(db, vid):
    with db.cursor() as cur:
        cur.execute(ALL, (vid,))
        cols = [c.name for c in cur.description]
        return dict(zip(cols, cur.fetchone()))


def test_phase2_a_record_whose_window_gains_no_long_form_item_keeps_every_value(world):
    fake, client, db, storage = world
    _phase2_world(client, db)
    before = _row(db, "r1")
    daily_before = daily(db, "r1")
    recover(client, storage)
    after = _row(db, "r1")
    assert after.pop("format_rule") == "youtube_shape" and before.pop("format_rule") == "duration_180"
    assert after == before                              # every other column, to the bit
    assert daily(db, "r1") == daily_before
    assert one(db, "select count(*) from fmt2_history h join posts p on p.id = h.post_id "
                   "where p.external_post_id = 'r1'") == [(0,)]
    # the unknown item and the night-read long-form one were read for their duration
    asked = {i for q in fake.of("videos") for i in q["id"].split(",")}
    assert {"UCp_x0", "UCp_x1"} <= asked
    inv = bl.SupabaseInventory(client).load(["UCp"])["UCp"]["items"]
    assert inv["UCp_x0"][1] == "SHORT" and inv["UCp_x1"][1] == "LONG"


@pytest.mark.parametrize("vid, ch", [("r2", "UCq"), ("r4", "UCr")])
def test_phase2_a_record_that_gains_a_long_form_item_gets_the_baseline_of_the_new_set(world, vid, ch):
    fake, client, db, storage = world
    _phase2_world(client, db)
    before = _row(db, vid)
    recover(client, storage)
    after = _row(db, vid)
    new = core.baseline_v2(
        [{"video_id": f"{ch}_l{i}", "published_at": iso(R_PUB - timedelta(days=10 + 5 * i)), "views": v}
         for i, v in enumerate([100, 200, 300, 400, 500])] +
        [{"video_id": f"{ch}_x0", "published_at": iso(R_PUB - timedelta(days=12)), "views": 600}],
        vid, iso(R_PUB))
    assert new["baseline"] == 350.0
    assert after["format_rule"] == "youtube_shape" and float(after["baseline_score"]) == 350.0
    assert after["baseline_samples"] == 6 and after["baseline_video_ids"] == new["video_ids"]
    assert after["baseline_computed_at"] > before["baseline_computed_at"]
    assert daily(db, vid) == [(D1, 700.0, 2.0), (D2, 900.0, 900 / 350)]
    assert float(after["vpi_ratio"]) == pytest.approx(900 / 350) and after["vpi_max_on"] == D2
    assert after["vpi_level"] == core.get_vpi_metadata(900 / 350)[0]
    h = one(db, "select h.baseline_score, h.baseline_samples, h.vpi_max, h.vpi_max_on, h.post_daily "
                "from fmt2_history h join posts p on p.id = h.post_id where p.external_post_id = %s", vid)
    assert len(h) == 1 and float(h[0][0]) == 300 and h[0][1] == 5 and float(h[0][2]) == 3.0
    assert h[0][3] == D2 and [x["day"] for x in h[0][4]] == ["2026-09-27", "2026-09-28"]
    assert [float(x["vpi_ratio"]) for x in h[0][4]] == [700 / 300, 3.0]
    assert one(db, "select baselines_changed from fmt2_run")[0][0] == 4      # r2, r4, rm, rk


def test_phase2_a_record_without_a_baseline_only_changes_its_rule(world):
    fake, client, db, storage = world
    _phase2_world(client, db)
    before = _row(db, "r3")
    recover(client, storage)
    after = _row(db, "r3")
    assert (before.pop("format_rule"), after.pop("format_rule")) == ("duration_180", "youtube_shape")
    assert after == before


def test_done_when_nothing_is_left(world):
    fake, client, db, storage = world
    _phase2_world(client, db, uncovered=False)
    recover(client, storage)
    assert one(db, "select count(*) from posts where method_version = 'v2' and entered_on >= %s "
                   "and format_rule = 'duration_180'", D1) == [(0,)]
    assert record(db, "n1x")["format_rule"] == "duration_180"      # night 1 stays out
    fake.calls = []
    out = recover(client, storage)
    assert out == {"skipped": "nothing to do: every day of phase 1 done, no record under the old rule"}
    assert fake.calls == []


# --- the gate and the budget ----------------------------------------------------------


def test_nothing_when_the_night_is_not_finished(world):
    fake, client, db, storage = world
    with db.cursor() as cur:
        cur.execute("update ingest_run set finished_at = null where day = %s", (D3,))
    assert recover(client, storage) == {"skipped": "the reading of 2026-09-29 is not finished"}
    assert fake.calls == [] and one(db, "select count(*) from fmt2_run") == [(0,)]


def test_nothing_when_the_census_is_not_complete_or_the_day_is_missing(world):
    fake, client, db, storage = world
    with db.cursor() as cur:
        cur.execute("update ingest_run set census_complete = false where day = %s", (D3,))
    assert recover(client, storage)["skipped"] == "the census of 2026-09-29 is not complete"
    assert recover(client, storage, now=NOW + timedelta(days=1))["skipped"] == "no reading of 2026-09-30"
    assert fake.calls == []


def test_nothing_while_a_record_of_the_night_waits_for_the_morning_pass(world):
    fake, client, db, storage = world
    _night_record(client, "Y", D3, baseline_rule="quota_stop")
    assert recover(client, storage) == {"skipped": "1 records of 2026-09-29 wait for the morning pass"}
    assert fake.calls == []


def _ledger(db, units, at_):
    with db.cursor() as cur:
        cur.execute("insert into quota_ledger (at, source, units) values (%s, 'reading', %s)", (at_, units))


def test_the_budget_is_what_the_pacific_quota_day_has_left():
    class C:
        def __init__(self, rows):
            self.rows = rows

        def table(self, name):
            rows = self.rows

            class T:
                def select(self, *_):
                    return self

                def execute(self):
                    return type("R", (), {"data": rows})()
            return T()
    # 30/09 06:00 UTC = 29/09 23:00 in Los Angeles: the quota day of 29/09 (Pacific)
    rows = [{"at": "2026-09-29T07:30:00+00:00", "units": 1000},    # 29/09 00:30 PDT: counted
            {"at": "2026-09-30T00:10:00+00:00", "units": 7000},    # the night, 17:10 PDT: counted
            {"at": "2026-09-29T06:59:00+00:00", "units": 900}]     # 28/09 23:59 PDT: another day
    assert rf.budget(C(rows), NOW) == 9900 - 8000 - 200


def test_with_the_ledger_at_9000_the_run_stops_at_700_and_resumes_inside_the_day(world, monkeypatch):
    fake, client, db, storage = world
    monkeypatch.setattr(rf, "BLOCK", 1)                 # one unit per entry
    extra = [(D2, f"q{i:04d}", "UCw", "SHORT", CHART["V"][1], 10, ["IT"], ["24"]) for i in range(800)]
    for i in range(800):
        monkeypatch.setitem(CHART, f"q{i:04d}", ("UCw", CHART["V"][1], "PT40S", "vertical"))
    with db.cursor() as cur:
        cur.executemany("insert into trend_snapshot (day, video_id, channel_id, format, published_at, "
                        "views, countries, categories) values (%s, %s, %s, %s, %s, %s, %s, %s)", extra)
        cur.execute("update ingest_run set videos_seen = videos_seen + 800 where day = %s", (D2,))
    _ledger(db, 9000, NOW - timedelta(hours=6))
    out = recover(client, storage)
    assert out["units"] == 700 == fake.units()
    r = one(db, "select units, days_done, cursor, notes from fmt2_run")[0]
    assert r[0] == 700 and r[1] == [D1]                 # D1 done, D2 stopped inside
    assert r[2]["day"] == "2026-09-28" and r[2]["after"] == sorted(
        ["Z"] + [f"q{i:04d}" for i in range(800)])[499]  # the first group of 500, whole
    assert "stopped: quota brake at 700 units" in r[3]
    assert one(db, "select source, units from quota_ledger where source = 'recovery'") == [("recovery", 700)]
    assert record(db, "Z")["entered_on"] == D2          # opened in the first group
    # the next run: only what the first group did not reach is read again
    with db.cursor() as cur:
        cur.execute("delete from quota_ledger")
    fake.calls = []
    recover(client, storage)
    assert fake.units() == 301
    assert one(db, "select days_done from fmt2_run order by id")[-1][0] == [D2]


def test_the_ledger_counts_every_unit_of_a_run_that_fails(world, monkeypatch):
    fake, client, db, storage = world
    monkeypatch.setattr(rf, "_open", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        recover(client, storage)
    units = one(db, "select units from quota_ledger where source = 'recovery'")
    assert units == [(fake.units(),)] and fake.units() > 0
    assert "failed: RuntimeError: boom" in one(db, "select notes from fmt2_run")[0][0]


def test_only_the_service_role_writes_the_recovery_tables(db):
    with db.cursor() as cur:
        for t in ("quota_ledger", "fmt2_run", "fmt2_history", "fmt2_null_items", "fmt2_left"):
            cur.execute("select relrowsecurity from pg_class where oid = %s::regclass", (f"public.{t}",))
            assert cur.fetchone() == (True,), t
            cur.execute("select count(*) from pg_policies where tablename = %s", (t,))
            assert cur.fetchone() == (0,), t
        cur.execute("select has_function_privilege('anon', 'public.fmt2_replace_baseline(uuid, jsonb)', "
                    "'execute'), has_function_privilege('service_role', "
                    "'public.fmt2_replace_baseline(uuid, jsonb)', 'execute')")
        assert cur.fetchone() == (False, True)
        cur.execute("select schedule, command from cron.job where jobname = 'recupero-fmt2'")
        assert cur.fetchone() == ("0 6 * * *", "select public.chiedi_recupero_fmt2()")


def test_the_run_stops_before_the_quota_day_ends(world):
    """06:00 UTC is 23:00 in Los Angeles: Google's reset is at 07:00 UTC. A unit
    spent after it would count against the day of the next reading."""
    fake, client, db, storage = world
    assert rf.quota_day_end(NOW) == datetime(2026, 9, 30, 7, 0, tzinfo=timezone.utc)
    ticks = iter([NOW + timedelta(minutes=10)] + [NOW + timedelta(minutes=56)] * 100)
    out = recover(client, storage, clock=lambda: next(ticks))
    assert out["units"] == 1                                     # the first call, then the deadline
    assert any(n.startswith("stopped:") and n.endswith("the quota day ends at 2026-09-30T06:55:00+00:00")
               for n in out["notes"])
    assert recover(client, storage, now=datetime(2026, 9, 30, 6, 56, tzinfo=timezone.utc)) == \
        {"skipped": "too close to the end of the quota day (2026-09-30T06:55:00+00:00)"}


def test_phase2_and_3_leave_out_night_1_and_only_the_records_they_cannot_check(world):
    fake, client, db, storage = world
    _phase2_world(client, db)
    before = {v: _row(db, v) for v in ("n1x", "rj", "rg", "rh")}
    out = recover(client, storage)
    for v in ("n1x", "rj", "rg", "rh"):
        assert _row(db, v) == before[v], v                      # untouched, 'duration_180'
    assert one(db, "select p.external_post_id, l.reason from fmt2_left l join posts p on p.id = l.post_id "
                   "order by 1") == [("rg", "gone"), ("rh", "gone"), ("rj", "gone")]
    asked = {i for q in fake.of("videos") for i in q["id"].split(",")}
    assert "UCg_x0" in asked                                    # read, not returned
    assert "UCg_x0" not in bl.SupabaseInventory(client).load(["UCg"])["UCg"]["items"]
    # capped but nothing newer than its read: checked with the inventory alone
    assert record(db, "rm")["format_rule"] == "youtube_shape"
    # phase 3: UCk's uploads listed again, the dropped ones classified in memory;
    # its dropped wide 120 s upload makes the record change
    k = _row(db, "rk")
    assert k["format_rule"] == "youtube_shape" and float(k["baseline_score"]) == 600.0
    assert "UCk_dw" in k["baseline_video_ids"] and "UCk_d0" in k["baseline_video_ids"]
    inv = bl.SupabaseInventory(client).load(["UCk", "UCj"])
    assert not [v for v in inv["UCk"]["items"] if "_d" in v]    # never stored beyond the cap
    assert len(inv["UCk"]["items"]) == 14 and len(inv["UCj"]["items"]) == 13
    assert sorted(q["playlistId"] for q in fake.of("playlistItems") if q["playlistId"] in ("UUk", "UUj")) \
        == ["UUj", "UUk"]
    r = one(db, "select records_uncovered, phase3_pages, phase3_videos, notes from fmt2_run")[0]
    assert r[:2] == (3, 2) and r[2] >= 2
    assert "phase 3: 2 playlist pages" in r[3]
    assert out["records_uncovered"] == 3
    # the next run: nothing left within reach, nothing read
    fake.calls = []
    out = recover(client, storage)
    assert out == {"skipped": "nothing to do: every day of phase 1 done, no record under the old rule"}
    assert fake.calls == []
    assert one(db, "select count(*) from posts where method_version = 'v2' and entered_on >= %s "
                   "and format_rule = 'duration_180'", D1) == [(3,)]


def test_nothing_newer():
    inv = {"items": {"a": [100, "LONG"], "b": [200, None]}}
    assert rf.nothing_newer(inv, 200) and not rf.nothing_newer(inv, 199)
    assert not rf.nothing_newer(None, 10)
    assert rf.baseline_read_epoch({"baseline_computed_at": "2026-09-27T23:59:30+00:00"}) == \
        int(datetime(2026, 9, 27, 23, 59, 30, tzinfo=timezone.utc).timestamp())
    assert rf.baseline_read_epoch({"baseline_computed_at": None, "entered_on": "2026-09-27"}) == \
        int(datetime(2026, 9, 27, 23, 59, tzinfo=timezone.utc).timestamp())


def test_covers():
    lo = 1_000_000
    assert rf.covers({"capped": True, "items": {"a": [lo, "LONG"], "b": [lo + 5, None]}}, lo)
    assert not rf.covers({"capped": True, "items": {"a": [lo + 1, "LONG"]}}, lo)
    assert rf.covers({"capped": False, "ended": True, "covered_back_to": None, "items": {}}, lo)
    assert rf.covers({"capped": False, "ended": False, "covered_back_to": lo, "items": {}}, lo)
    assert not rf.covers({"capped": False, "ended": False, "covered_back_to": lo + 1, "items": {}}, lo)
    assert not rf.covers(None, lo)


def test_phase3_lists_down_to_the_150_of_the_read_and_no_further(world, monkeypatch):
    """Two uploads a day. The read of 27/09 23:00 saw the 150 most recent
    uploads published by then; the inventory now holds the 150 most recent
    published by 03/10, so it dropped 12. Phase 3 lists ceil((12 + 150) / 50)
    = 4 pages, classifies the 12 dropped uploads in memory, and the record,
    whose candidates did not change, only gets its rule."""
    fake, client, db, storage = world
    newest = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    ups = [(f"p{i:03d}", newest - timedelta(hours=12 * i), "PT10M", 1000 + i, "wide") for i in range(300)]
    monkeypatch.setitem(UPLOADS, "UCp3", ups)
    for v, p_, dur, views, shape in ups:
        ITEMS[v] = (dur, views, shape)
    inv = {"items": {v: [int(p_.timestamp()), "LONG"] for v, p_, *_ in ups[:150]},
           "covered_back_to": None, "capped": True, "ended": False, "refreshed_on": "2026-10-03"}
    bl.SupabaseInventory(client).save({"UCp3": inv})
    read_at = at(D1, 23)
    pool = [u for u in ups if u[1] <= read_at][:150]
    dropped = {u[0] for u in pool} - set(inv["items"])
    assert len([u for u in ups if u[1] > read_at]) == 12 and len(dropped) == 12
    monkeypatch.setitem(CHART, "rp3", ("UCp3", R_PUB, "PT20M", "wide"))
    old = core.baseline_v2([{"video_id": v, "published_at": iso(p_), "views": n} for v, p_, _, n, _ in pool],
                           "rp3", iso(R_PUB))
    assert old["rule"] == "standard"
    v = {"channel_id": "UCp3", "format": "LONG", "published_at": iso(R_PUB), "views": 9000,
         "countries": {"IT"}, "categories": {"24"}}
    rec = eng._record("rp3", v, {"gap_days": 0, "entry_certain": True}, old, {}, D1, iso(read_at), iso(read_at))
    rec.update({"format_rule": "duration_180", "duration_s": None, "shape": None, "was_live": None})
    client.table("posts").insert(rec).execute()
    before = _row(db, "rp3")
    out = recover(client, storage)
    assert [q for q in fake.of("playlistItems") if q["playlistId"] == "UUp3"].__len__() == 4
    after = _row(db, "rp3")
    assert (before.pop("format_rule"), after.pop("format_rule")) == ("duration_180", "youtube_shape")
    assert after == before
    asked = {i for q in fake.of("videos") for i in q["id"].split(",")}
    assert dropped <= asked
    assert set(bl.SupabaseInventory(client).load(["UCp3"])["UCp3"]["items"]) == set(inv["items"])
    assert out["records_uncovered"] == 0
