"""27/09/2026: the read-cost changes, each proved against the full read.

1. itemCount: a channel with fewer than 5 uploads in total is not enumerated
   and is not_computable - the same rule a full read reaches.
2. videos.list on a warm channel checks only ids whose stored format is
   unknown or measured: same baseline and same ids as a cold read (also the
   300 randomised histories in test_inventory.py).
3. The sampling proposed on 27/09 (select candidates spread across the
   window, fetch 50, keep the right format, fetch more only if fewer than 20)
   is NOT the same estimator: the counterexample below picks different ids.
   It is therefore not implemented (01 section 2 is closed).
"""

import random
from datetime import timedelta

import pytest
import responses

import baseline as bl
import vpi_core as core
from tests.test_baseline import FakeYouTube, KEY, iso
from tests.test_inventory import NOW, DAY, m, uploads


@pytest.fixture(autouse=True)
def probe_on(monkeypatch):
    """The probe is off in production (measured not to pay); proved here."""
    monkeypatch.setattr(bl, "ITEM_COUNT_PROBE", True)


def test_the_probe_is_off_by_default():
    import importlib
    assert importlib.reload(bl).ITEM_COUNT_PROBE is False


def run(channels, measured, store=None, **kw):
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        fake = FakeYouTube(channels, **kw)
        for ep in ("channels", "playlists", "playlistItems", "videos"):
            rsps.add_callback(responses.GET, f"{bl.BASE}/{ep}", callback=fake)
        res, rep = bl.baselines_for_videos(measured, KEY, sleep=lambda s: None,
                                           inventory=store or bl.MemoryInventory())
    return res, rep, fake


# --- 1. itemCount -----------------------------------------------------------------


@pytest.mark.parametrize("n", [0, 1, 2, 3, 4])
def test_fewer_than_5_uploads_is_not_enumerated_and_not_computable(n):
    ch = {"UCa": uploads("a", n, NOW - 10 * DAY, every=3)}
    res, rep, fake = run(ch, [m("x", "UCa", NOW, "LONG")])
    assert fake.of("playlistItems") == [] and fake.of("videos") == []
    assert rep["skipped_by_item_count"] == 1
    assert res["x"]["rule"] == core.RULE_NOT_COMPUTABLE and res["x"]["baseline"] is None
    # the full read (itemCount unavailable) reaches the same rule
    full, _, ffake = run(ch, [m("x", "UCa", NOW, "LONG")], status={("playlists", "*"): [500, 500, 500]})
    assert full["x"]["rule"] == res["x"]["rule"] and full["x"]["baseline"] is None
    assert len(ffake.of("playlistItems")) == 1


@pytest.mark.parametrize("seed", range(60))
def test_the_skip_never_changes_a_rule_or_a_baseline(seed):
    rnd = random.Random(seed)
    chans, measured = {}, []
    for i in range(12):
        n = rnd.choice([0, 2, 4, 5, 6, 9, 40])
        dur = lambda: rnd.choice(["PT12M", "PT40S"])
        chans[f"UC{i}"] = [(f"c{i}_{j}", NOW - timedelta(days=8 + j * rnd.choice([1, 3, 9])), dur(),
                            rnd.randint(1, 9000)) for j in range(n)]
        measured.append(m(f"x{i}", f"UC{i}", NOW, "LONG"))
    skip, _, _ = run(chans, measured)
    full, _, _ = run(chans, measured, status={("playlists", "*"): [500, 500, 500]})
    for vid in full:
        assert (skip[vid]["rule"], skip[vid]["baseline"]) == (full[vid]["rule"], full[vid]["baseline"])
        if full[vid]["rule"] == core.RULE_STANDARD:
            assert skip[vid] == full[vid]


def test_the_itemcount_call_is_batched_50_per_unit():
    chans = {f"UC{i:03d}": uploads(f"c{i}_", 8, NOW - 8 * DAY, every=5) for i in range(120)}
    _, rep, fake = run(chans, [m(f"x{i}", c, NOW, "LONG") for i, c in enumerate(chans)])
    assert [len(q["id"].split(",")) for q in fake.of("playlists")] == [50, 50, 20]
    assert rep["quota_playlists"] == 3


# --- 2. warm channels: only the measured format is checked -----------------------


def test_a_warm_channel_checks_only_unknown_or_measured_format_ids():
    mixed = [(f"v{i:03d}", NOW - timedelta(days=8 + i), "PT12M" if i % 4 == 0 else "PT40S", 1000 + i)
             for i in range(60)]
    store = bl.MemoryInventory()
    run({"UCa": mixed}, [m("warmup", "UCa", NOW, "SHORT")], store)   # formats now stored
    warm, wrep, wfake = run({"UCa": mixed}, [m("x", "UCa", NOW, "LONG")], store)
    cold, crep, cfake = run({"UCa": mixed}, [m("x", "UCa", NOW, "LONG")])
    assert warm == cold and warm["x"]["rule"] == core.RULE_STANDARD
    asked = {i for q in wfake.of("videos") for i in q["id"].split(",")}
    assert asked and all(int(v[1:]) % 4 == 0 for v in asked)          # long-form only
    assert wrep["videos_skipped_other_format"] > 0
    assert wrep["videos_checked"] < crep["videos_checked"]


# --- 3. the proposed spread sampling is a different estimator -------------------


def spread_sampling(window, fmt, fetch):
    """The rule proposed on 27/09, literally: candidates spread across the
    window, 50 at a time, keep the right format, stop at 20 or when done."""
    ordered = sorted(window)
    step = max(1, len(ordered) // 50)
    picks = ordered[::step][:50]
    rest = [w for w in ordered if w not in picks]
    kept = [w for w in picks if fetch(w) == fmt]
    while len(kept) < 20 and rest:
        batch, rest = rest[:50], rest[50:]
        kept += [w for w in batch if fetch(w) == fmt]
    return sorted(kept)


def test_the_proposed_spread_sampling_picks_different_ids_than_the_rule():
    # 80 in-window long-form videos among 150: the rule picks 20 evenly over
    # all 80; the spread sample sees only those among its first 50 and picks
    # 20 evenly over those.
    ups = [(f"v{i:03d}", NOW - timedelta(days=8 + i * 0.5), "PT12M" if i % 15 < 8 else "PT40S",
            1000 + 13 * i) for i in range(150)]
    fmt_of = {v: core.formato(core.parse_iso_duration(d), "563", "1000", iso(p)) for v, p, d, _ in ups}
    res, _, _ = run({"UCa": ups}, [m("x", "UCa", NOW, "LONG")])
    window = [(p, v) for v, p, _, _ in ups]
    sampled = spread_sampling(window, "LONG", lambda w: fmt_of[w[1]])
    views = {v: n for v, _, _, n in ups}
    alt = core.baseline_v2([{"video_id": v, "published_at": iso(p), "views": views[v]} for p, v in sampled],
                           "x", iso(NOW))
    assert res["x"]["rule"] == alt["rule"] == core.RULE_STANDARD
    assert res["x"]["video_ids"] != alt["video_ids"]
