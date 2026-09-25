"""GATE-2: the channel inventory and the per-run read, on mocked HTTP.

The claim under test (02 section 4.4): the inventory changes the cost, never
the baseline. The same measured video computed on a warm inventory and on a
fresh read gives the same baseline and the same sample ids - after new
uploads, removed videos, changed views, hidden views, more than 150 uploads,
and a measured video that needs a deeper window than the inventory holds.
"""

from datetime import datetime, timedelta, timezone

import pytest
import responses

import baseline as bl
from tests.test_baseline import FakeYouTube, KEY, iso

NOW = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
DAY = timedelta(days=1)


def uploads(prefix, n, start, every=1.0, dur="PT40S", views=lambda i: 1000 + 7 * i):
    return [(f"{prefix}{i:03d}", start - timedelta(days=i * every), dur, views(i)) for i in range(n)]


def m(vid, ch, pub, fmt="SHORT"):
    return {"video_id": vid, "channel_id": ch, "format": fmt, "published_at": iso(pub)}


def run(channels, measured, store, run_state=None, today=None, **kw):
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        fake = FakeYouTube(channels, **kw)
        for ep in ("channels", "playlistItems", "videos"):
            rsps.add_callback(responses.GET, f"{bl.BASE}/{ep}", callback=fake)
        res, rep = bl.baselines_for_videos(measured, KEY, sleep=lambda s: None, inventory=store,
                                           run_state=run_state, today=today)
    return res, rep, fake


def warm_and_cold(day_a, measured_a, day_b, measured_b, **kw_b):
    store = bl.MemoryInventory()
    run(day_a, measured_a, store, today=NOW.date())
    warm, wrep, wfake = run(day_b, measured_b, store, today=(NOW + DAY).date(), **kw_b)
    cold, crep, cfake = run(day_b, measured_b, bl.MemoryInventory(), today=(NOW + DAY).date(), **kw_b)
    return warm, cold, wfake, cfake, store


def test_new_uploads_changed_views_and_removed_samples_give_the_same_baseline():
    a = {"UCa": uploads("a", 60, NOW)}
    res_a, _, _ = run(a, [m("x", "UCa", NOW - DAY)], bl.MemoryInventory())
    picked_a = res_a["x"]["video_ids"]
    # next day: 3 new uploads, every view count doubled, two of yesterday's picks removed
    gone = {picked_a[3], picked_a[10]}
    ups = uploads("n", 3, NOW + DAY, every=0.3) + [
        (v, p, d, n * 2) for v, p, d, n in a["UCa"] if v not in gone]
    b = {"UCa": ups}
    warm, cold, wfake, cfake, _ = warm_and_cold(a, [m("x", "UCa", NOW - DAY)], b, [m("y", "UCa", NOW + DAY)])
    assert warm == cold and warm["y"]["rule"] == "standard"
    assert not gone & set(warm["y"]["video_ids"])
    assert len(wfake.calls) < len(cfake.calls)
    assert len(wfake.of("playlistItems")) == 1                 # forward refresh, one page


def test_views_are_never_reused_from_an_earlier_run():
    a = {"UCa": uploads("a", 40, NOW)}
    b = {"UCa": [(v, p, d, n * 3) for v, p, d, n in a["UCa"]]}
    warm, cold, _, _, _ = warm_and_cold(a, [m("x", "UCa", NOW)], b, [m("x", "UCa", NOW)])
    fresh, _, _ = run(a, [m("x", "UCa", NOW)], bl.MemoryInventory())
    assert warm == cold and warm["x"]["baseline"] == 3 * fresh["x"]["baseline"]


def test_more_than_150_uploads_keeps_the_three_page_cap_exactly():
    a = {"UCa": uploads("a", 400, NOW, every=0.25)}              # 4 a day
    b = {"UCa": uploads("n", 20, NOW + DAY, every=0.05) + a["UCa"]}
    warm, cold, _, _, store = warm_and_cold(a, [m("x", "UCa", NOW)], b, [m("y", "UCa", NOW + DAY)])
    assert warm == cold
    assert len(store.data["UCa"]["items"]) <= bl.INVENTORY_MAX and store.data["UCa"]["capped"]


def test_a_measured_video_needing_a_deeper_window_triggers_a_full_read():
    a = {"UCa": uploads("a", 200, NOW, every=1.0)}               # one a day, 200 days
    # day A covers ~97 days back; day B measures a video published 60 days ago
    warm, cold, wfake, _, _ = warm_and_cold(a, [m("x", "UCa", NOW)], a,
                                            [m("a060", "UCa", NOW - 60 * DAY)])
    assert warm == cold
    assert len(wfake.of("playlistItems")) >= 2


def test_hidden_views_on_a_pick_are_excluded_and_chosen_again():
    a = {"UCa": uploads("a", 60, NOW)}
    res_a, _, _ = run(a, [m("x", "UCa", NOW)], bl.MemoryInventory())
    hide = res_a["x"]["video_ids"][5]
    b = {"UCa": [(v, p, d, None if v == hide else n) for v, p, d, n in a["UCa"]]}
    warm, cold, _, _, _ = warm_and_cold(a, [m("x", "UCa", NOW)], b, [m("x", "UCa", NOW)])
    assert warm == cold and hide not in warm["x"]["video_ids"]


def test_mixed_formats_and_long_videos_give_the_same_result_warm_and_cold():
    shorts = uploads("s", 50, NOW, every=1.5)
    longs = uploads("l", 50, NOW - 0.5 * DAY, every=1.5, dur="PT14M", views=lambda i: 90_000 + i)
    a = {"UCa": sorted(shorts + longs, key=lambda x: x[1], reverse=True)}
    b = {"UCa": uploads("n", 4, NOW + DAY, every=0.2) + a["UCa"]}
    ms = [m("ys", "UCa", NOW + DAY), m("yl", "UCa", NOW + DAY, "LONG")]
    warm, cold, _, _, _ = warm_and_cold(a, [m("x", "UCa", NOW)], b, ms)
    assert warm == cold and warm["yl"]["baseline"] > 50_000 > warm["ys"]["baseline"]


def test_one_read_per_channel_per_run():
    a = {"UCa": uploads("a", 60, NOW)}
    state, store = bl.new_run_state(), bl.MemoryInventory()
    _, _, f1 = run(a, [m("x", "UCa", NOW)], store, run_state=state)
    res, rep, f2 = run(a, [m("y", "UCa", NOW - 2 * DAY)], store, run_state=state)
    assert f2.of("playlistItems") == [] and f2.of("channels") == []
    assert rep["cached_in_run"] == 1 and res["y"]["rule"] == "standard"


def test_several_videos_of_one_channel_on_the_same_day_cost_one_read():
    a = {"UCa": uploads("a", 120, NOW)}
    res, rep, fake = run(a, [m("x", "UCa", NOW), m("y", "UCa", NOW - 5 * DAY),
                             m("z", "UCa", NOW - 9 * DAY)], bl.MemoryInventory())
    assert len(fake.of("playlistItems")) <= 3 and rep["full_reads"] == 1
    assert {r["rule"] for r in res.values()} == {"standard"}


def test_warm_cost_on_an_unchanged_channel():
    a = {"UCa": uploads("a", 120, NOW)}
    store = bl.MemoryInventory()
    _, _, cold = run(a, [m("x", "UCa", NOW)], store)
    _, rep, fake = run(a, [m("x", "UCa", NOW)], store)
    assert len(cold.of("playlistItems")) == 2 and len(fake.of("playlistItems")) == 1
    # every in-window candidate is checked again (existence, privacy, views)
    sent = {i for q in fake.of("videos") for i in q["id"].split(",")}
    in_window = {v for v, p, _, _ in a["UCa"] if 7 <= (NOW - p).total_seconds() / 86400 <= 90}
    assert sent == in_window and len(fake.of("videos")) == 2


def test_a_video_made_unlisted_is_excluded_as_a_fresh_read_would():
    a = {"UCa": uploads("a", 60, NOW)}
    res_a, _, _ = run(a, [m("x", "UCa", NOW)], bl.MemoryInventory())
    hidden = res_a["x"]["video_ids"][7]
    warm, cold, _, _, _ = warm_and_cold(a, [m("x", "UCa", NOW)], a, [m("x", "UCa", NOW)],
                                        unlisted={hidden, "a030"})
    assert warm == cold and hidden not in warm["x"]["video_ids"]


def test_a_removal_among_the_150_while_the_cap_binds_refills_them():
    a = {"UCa": uploads("a", 400, NOW, every=0.25)}              # the cap truncates the window
    gone = {"a010", "a011", "a012", "a149"}                      # inside the 150 most recent
    b = {"UCa": [u for u in a["UCa"] if u[0] not in gone]}
    warm, cold, wfake, _, _ = warm_and_cold(a, [m("x", "UCa", NOW)], b, [m("x", "UCa", NOW)])
    assert warm == cold
    assert len(wfake.of("playlistItems")) >= 3                    # read again from the newest


@pytest.mark.usefixtures("db")
def test_supabase_inventory_round_trip(db):
    from tests.pg_client import PgClient
    store = bl.SupabaseInventory(PgClient(db))
    inv = {"UCa": {"items": {"v1": [1759300000, "SHORT"], "v2": [1759200000, None]},
                   "covered_back_to": 1759200000, "capped": True, "ended": False,
                   "refreshed_on": "2026-10-01"}}
    store.save(inv)
    assert store.load(["UCa", "UCzz"]) == inv


@pytest.mark.parametrize("seed", range(300))
def test_randomised_warm_equals_cold(seed):
    """300 generated histories: uploads at random rates and formats, then a
    next day with new uploads, removals, unlisted videos, changed and hidden
    views, and measured videos of random age. Warm must equal cold."""
    import random
    rnd = random.Random(seed)
    n = rnd.choice([3, 8, 30, 70, 160, 260, 420])
    every = rnd.choice([0.2, 0.5, 1.0, 2.0, 4.0])
    ups = []
    for i in range(n):
        dur = "PT40S" if rnd.random() < 0.7 else rnd.choice(["PT12M", "P0D"])
        ups.append((f"v{i:03d}", NOW - timedelta(days=i * every + rnd.random() * 0.1), dur,
                    rnd.randint(0, 50_000)))
    a = {"UCa": ups}
    measured_a = [m("xa", "UCa", NOW - rnd.randint(0, 20) * DAY)]
    # new uploads come after every existing one (an upload is newer than what
    # was already on the channel); a reappearing old video is the declared
    # exception, tested separately below
    new = [(f"n{i:03d}", NOW + DAY - timedelta(minutes=4 * i), "PT40S", rnd.randint(0, 5000))
           for i in range(rnd.choice([0, 1, 5, 60, 200]))]
    kept = [(v, p, d, None if rnd.random() < 0.03 else int(views * rnd.uniform(1, 3)))
            for v, p, d, views in ups if rnd.random() > 0.05]
    b = {"UCa": sorted(new + kept, key=lambda u: u[1], reverse=True)}
    unlisted = {u[0] for u in kept if rnd.random() < 0.03}
    fmt = rnd.choice(["SHORT", "SHORT", "LONG"])
    measured_b = [m("yb", "UCa", NOW + DAY - rnd.randint(0, 80) * DAY, fmt),
                  m("zb", "UCa", NOW + DAY - rnd.randint(0, 5) * DAY)]
    warm, cold, _, _, store = warm_and_cold(a, measured_a, b, measured_b, unlisted=unlisted)
    assert warm == cold
    assert len(store.data["UCa"]["items"]) <= bl.INVENTORY_MAX


def test_declared_exception_an_old_video_reappearing_is_missed_until_a_full_read():
    """02 section 4.4, declared: the forward refresh stops at the first page
    holding a known upload, so an old video that becomes public again deeper
    in the list is not seen. A fresh read includes it. This test pins the
    exception, so that it stays visible and any change to it shows up."""
    base = uploads("a", 80, NOW)
    back = ("old1", NOW - 60 * DAY + timedelta(hours=1), "PT40S", 10**6)   # on page 2
    a = {"UCa": base}
    b = {"UCa": sorted(base + [back], key=lambda u: u[1], reverse=True)}
    warm, cold, wfake, _, _ = warm_and_cold(a, [m("x", "UCa", NOW)], b, [m("x", "UCa", NOW)])
    assert len(wfake.of("playlistItems")) == 1
    assert cold["x"]["samples"] == warm["x"]["samples"] == 20
    assert warm["x"] != cold["x"]                   # the exception, as declared
    assert "old1" not in warm["x"]["video_ids"]
