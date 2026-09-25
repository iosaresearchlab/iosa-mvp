"""T-08: backend/baseline.py and vpi_core.baseline_v2(), on mocked HTTP.

docs/01-methodology-protocol.md section 2; docs/02-technical-specification.md
section 4.4; docs/08-implementation-plan.md T-08. No test reaches YouTube.
"""

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
import responses

import baseline as bl
import vpi_core as core

KEY = "test-key-not-real"
NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def days_before(ref, n):
    return ref - timedelta(days=n)


class FakeYouTube:
    """channels: {channel_id: [(video_id, published_dt, duration, views), ...]}
    newest first, as the uploads playlist returns them.
    status: {(endpoint, key): [codes...]} scripted failures, consumed in order.
    """

    def __init__(self, channels, status=None, missing_playlists=()):
        self.channels = channels
        self.status = {k: list(v) for k, v in (status or {}).items()}
        self.missing = set(missing_playlists)
        self.calls = []
        self.videos = {v[0]: v for ups in channels.values() for v in ups}

    def __call__(self, request):
        u = urlparse(request.url)
        endpoint = u.path.rsplit("/", 1)[-1]
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        self.calls.append((endpoint, q))
        key = q.get("playlistId") or q.get("id")
        scripted = self.status.get((endpoint, key)) or self.status.get((endpoint, "*"))
        if scripted:
            return (scripted.pop(0), {}, json.dumps({"error": {"errors": [{"reason": "x"}]}}))
        if endpoint == "channels":
            items = [{"id": c, "snippet": {"customUrl": f"@{c}", "title": c},
                      "statistics": {"subscriberCount": "1000"}}
                     for c in q["id"].split(",") if c in self.channels]
            return (200, {}, json.dumps({"items": items}))
        if endpoint == "playlistItems":
            ch = "UC" + q["playlistId"][2:]
            if ch not in self.channels or q["playlistId"] in self.missing:
                return (404, {}, "{}")
            ups = self.channels[ch]
            page = int(q.get("pageToken", "0"))
            chunk = ups[page * 50:(page + 1) * 50]
            body = {"items": [{"contentDetails": {"videoId": v, "videoPublishedAt": iso(p)}}
                              for v, p, _, _ in chunk]}
            if (page + 1) * 50 < len(ups):
                body["nextPageToken"] = str(page + 1)
            return (200, {}, json.dumps(body))
        if endpoint == "videos":
            items = []
            for vid in q["id"].split(","):
                if vid in self.videos:
                    _, _, dur, views = self.videos[vid]
                    st = {} if views is None else {"viewCount": str(views)}
                    items.append({"id": vid, "contentDetails": {"duration": dur}, "statistics": st})
            return (200, {}, json.dumps({"items": items}))
        return (400, {}, "{}")

    def of(self, endpoint):
        return [q for e, q in self.calls if e == endpoint]


@pytest.fixture
def yt():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        def install(channels, **kw):
            fake = FakeYouTube(channels, **kw)
            for ep in ("channels", "playlistItems", "videos"):
                rsps.add_callback(responses.GET, f"{bl.BASE}/{ep}", callback=fake)
            return fake
        yield install


def daily_uploads(prefix, n, start=NOW, every_days=1.0, duration="PT40S", views=1000):
    """n uploads, one every every_days, newest first, starting at start."""
    return [(f"{prefix}{i:03d}", start - timedelta(days=i * every_days), duration,
             views if not callable(views) else views(i)) for i in range(n)]


def measure(video_id, channel_id, published, fmt="SHORT"):
    return {"video_id": video_id, "channel_id": channel_id, "format": fmt,
            "published_at": iso(published)}


def run(measured, **kw):
    kw.setdefault("sleep", lambda s: None)
    return bl.baselines_for_videos(measured, KEY, **kw)


# --- the closing check of T-08 ---------------------------------------------


def test_channels_list_in_blocks_of_50_without_the_uploads_part(yt):
    chans = {f"UC{i:04d}": daily_uploads(f"c{i}_", 10, every_days=10) for i in range(120)}
    fake = yt(chans)
    _, rep = run([measure(f"m{i}", c, NOW) for i, c in enumerate(chans)])
    calls = fake.of("channels")
    assert [len(q["id"].split(",")) for q in calls] == [50, 50, 20]
    assert all(q["part"] == "snippet,statistics" for q in calls)
    assert rep["quota_channels"] == 3


def test_videos_list_in_blocks_of_50(yt):
    fake = yt({"UCa": daily_uploads("a", 150, every_days=0.5)})  # 150 uploads in 75 days
    run([measure("m", "UCa", NOW)])
    sizes = [len(q["id"].split(",")) for q in fake.of("videos")]
    assert sizes and all(s <= 50 for s in sizes)
    assert sum(sizes) == len({i for q in fake.of("videos") for i in q["id"].split(",")})


def test_uploads_playlist_is_uc_to_uu(yt):
    fake = yt({"UCabcdef": daily_uploads("a", 5)})
    run([measure("m", "UCabcdef", NOW)])
    assert fake.of("playlistItems")[0]["playlistId"] == "UUabcdef"
    with pytest.raises(ValueError):
        bl.uploads_playlist("XXabcdef")


def test_pagination_stops_at_three_pages(yt):
    # 400 uploads, 4 a day: the 7-90 day window needs far more than 3 pages
    fake = yt({"UCa": daily_uploads("a", 400, every_days=0.25)})
    _, rep = run([measure("m", "UCa", NOW)])
    assert len(fake.of("playlistItems")) == rep["quota_playlist"] == core.BASELINE_PAGES_MAX == 3


def test_pagination_stops_once_the_window_is_covered(yt):
    # one upload a day: the page ending at day 99 already covers day 90
    fake = yt({"UCa": daily_uploads("a", 300, every_days=1.0)})
    run([measure("m", "UCa", NOW)])
    assert len(fake.of("playlistItems")) == 2


def test_date_filter_runs_before_videos_list(yt):
    # 30 uploads in the last 6 days: none is 7+ days older than the measured video
    fake = yt({"UCa": daily_uploads("a", 30, every_days=0.2)})
    res, rep = run([measure("m", "UCa", NOW)])
    assert rep["quota_videos"] == 0 and fake.of("videos") == []
    assert res["m"]["rule"] == core.RULE_NOT_COMPUTABLE


def test_only_in_window_ids_are_sent_to_videos_list(yt):
    ups = daily_uploads("a", 120, every_days=1.0)
    fake = yt({"UCa": ups})
    run([measure("m", "UCa", NOW)])
    sent = {i for q in fake.of("videos") for i in q["id"].split(",")}
    expected = {v for v, p, _, _ in ups if 7 <= (NOW - p).total_seconds() / 86400 <= 90}
    assert sent == expected


def test_even_sampling_across_the_window_not_the_most_recent(yt):
    ups = daily_uploads("a", 100, every_days=1.0, views=lambda i: 1000 + i)
    yt({"UCa": ups})
    res, _ = run([measure("m", "UCa", NOW)])
    r = res["m"]
    window = sorted((p, v) for v, p, _, _ in ups if 7 <= (NOW - p).days <= 90)
    assert len(window) == 84
    assert r["samples"] == 20 and r["rule"] == core.RULE_STANDARD
    assert r["video_ids"] == [v for _, v in core.even_pick(window, 20)]
    assert r["video_ids"][0] == window[0][1] and r["video_ids"][-1] == window[-1][1]
    most_recent = {v for _, v in window[-20:]}
    assert set(r["video_ids"]) != most_recent
    assert r["span_days"] == pytest.approx(83.0)


def test_not_computable_when_fewer_than_five_survive(yt):
    ups = [("a1", NOW - timedelta(days=10), "PT30S", 500),
           ("a2", NOW - timedelta(days=20), "PT30S", 500),
           ("a3", NOW - timedelta(days=30), "PT30S", 500),
           ("a4", NOW - timedelta(days=40), "PT30S", 500),
           ("a5", NOW - timedelta(days=95), "PT30S", 500)]   # outside the window
    yt({"UCa": ups})
    res, rep = run([measure("m", "UCa", NOW)])
    assert res["m"] == {"baseline": None, "rule": core.RULE_NOT_COMPUTABLE, "samples": 4,
                        "video_ids": ["a4", "a3", "a2", "a1"], "span_days": 30.0}
    assert rep["outcome"] == "ok"   # a record with no VPI is a valid outcome


def test_window_is_anchored_to_the_measured_videos_publication_not_to_today(yt):
    ups = daily_uploads("a", 140, every_days=1.0)
    fake = yt({"UCa": ups})
    res, _ = run([measure("new", "UCa", NOW), measure("old", "UCa", NOW - timedelta(days=40))])
    assert set(res["new"]["video_ids"]) != set(res["old"]["video_ids"])
    old_ref = NOW - timedelta(days=40)
    for vid in res["old"]["video_ids"]:
        p = dict((v, p) for v, p, _, _ in ups)[vid]
        assert 7 <= (old_ref - p).total_seconds() / 86400 <= 90, vid
    # one uploads read serves both measured videos of the channel
    assert len({q.get("pageToken") for q in fake.of("playlistItems")}) == len(fake.of("playlistItems"))


# --- the rest of 01 §2 ------------------------------------------------------


def test_same_format_only(yt):
    shorts = daily_uploads("s", 40, every_days=2.0, duration="PT50S", views=100)
    longs = [(f"l{i:03d}", NOW - timedelta(days=2 * i + 1), "PT12M", 90000) for i in range(40)]
    yt({"UCa": sorted(shorts + longs, key=lambda x: x[1], reverse=True)})
    res, _ = run([measure("ms", "UCa", NOW, "SHORT"), measure("ml", "UCa", NOW, "LONG")])
    assert res["ms"]["baseline"] == 100.0 and all(v.startswith("s") for v in res["ms"]["video_ids"])
    assert res["ml"]["baseline"] == 90000.0 and all(v.startswith("l") for v in res["ml"]["video_ids"])


def test_the_measured_video_is_not_its_own_sample(yt):
    ups = daily_uploads("a", 60, every_days=1.0)
    yt({"UCa": ups})
    res, _ = run([measure("a020", "UCa", NOW - timedelta(days=20))])
    assert "a020" not in res["a020"]["video_ids"]


def test_hidden_view_counts_are_not_samples(yt):
    ups = [(f"a{i}", NOW - timedelta(days=10 + i), "PT30S", None if i < 3 else 700) for i in range(7)]
    yt({"UCa": ups})
    res, _ = run([measure("m", "UCa", NOW)])
    assert res["m"]["samples"] == 4 and res["m"]["rule"] == core.RULE_NOT_COMPUTABLE


def test_zero_median_is_not_computable(yt):
    yt({"UCa": [(f"a{i}", NOW - timedelta(days=10 + i), "PT30S", 0) for i in range(6)]})
    res, _ = run([measure("m", "UCa", NOW)])
    assert res["m"]["rule"] == core.RULE_NOT_COMPUTABLE and res["m"]["baseline"] is None


def test_channel_without_an_uploads_playlist_is_not_computable(yt):
    yt({"UCa": daily_uploads("a", 10)}, missing_playlists={"UUa"})
    res, rep = run([measure("m", "UCa", NOW)])
    assert res["m"]["rule"] == core.RULE_NOT_COMPUTABLE and rep["playlist_missing"] == 1


# --- failures: never a rule invented to fill a gap ---------------------------


def test_a_transient_failure_leaves_the_video_unresolved_not_not_computable(yt):
    fake = yt({"UCa": daily_uploads("a", 60), "UCb": daily_uploads("b", 60)},
              status={("playlistItems", "UUa"): [503, 503, 503]})
    res, rep = run([measure("ma", "UCa", NOW), measure("mb", "UCb", NOW)])
    assert "ma" not in res and rep["unresolved"] == ["ma"]
    assert res["mb"]["rule"] == core.RULE_STANDARD
    assert rep["outcome"] == "partial"
    assert len([q for q in fake.of("playlistItems") if q["playlistId"] == "UUa"]) == 1 + bl.RETRIES


def test_a_transient_failure_that_recovers_is_retried_and_counted(yt):
    fake = yt({"UCa": daily_uploads("a", 60)}, status={("playlistItems", "UUa"): [500]})
    res, rep = run([measure("m", "UCa", NOW)])
    assert res["m"]["rule"] == core.RULE_STANDARD and rep["outcome"] == "ok"
    assert rep["quota_playlist"] == len(fake.of("playlistItems"))


def test_a_failed_videos_block_leaves_its_channels_unresolved(yt):
    yt({"UCa": daily_uploads("a", 60)}, status={("videos", "*"): [503, 503, 503]})
    res, rep = run([measure("m", "UCa", NOW)])
    assert res == {} and rep["unresolved"] == ["m"] and rep["outcome"] == "partial"


def test_403_stops_everything_and_resolves_nothing(yt):
    fake = yt({f"UC{i}": daily_uploads(f"c{i}", 60) for i in range(5)},
              status={("playlistItems", "UU2"): [403]})
    res, rep = run([measure(f"m{i}", f"UC{i}", NOW) for i in range(5)])
    assert res == {} and rep["outcome"] == "partial"
    assert rep["unresolved"] == [f"m{i}" for i in range(5)]
    assert fake.of("videos") == []
    last = fake.calls[-1]
    assert last[0] == "playlistItems" and last[1]["playlistId"] == "UU2"


def test_every_http_attempt_is_counted(yt):
    fake = yt({"UCa": daily_uploads("a", 120), "UCb": daily_uploads("b", 30, every_days=3)})
    _, rep = run([measure("ma", "UCa", NOW), measure("mb", "UCb", NOW)])
    total = rep["quota_channels"] + rep["quota_playlist"] + rep["quota_videos"]
    assert total == len(fake.calls)


# --- the pure rule, boundaries ----------------------------------------------


def test_window_ends_are_included_and_nothing_beyond():
    ref = NOW
    s = lambda vid, d: {"video_id": vid, "published_at": iso(ref - timedelta(days=d)), "views": 10}
    samples = [s("in7", 7), s("in90", 90), s("a", 30), s("b", 40), s("c", 50),
               s("out6", 6.99), s("out91", 90.01)]
    r = core.baseline_v2(samples, "m", iso(ref))
    assert set(r["video_ids"]) == {"in7", "in90", "a", "b", "c"} and r["rule"] == core.RULE_STANDARD


def test_even_pick():
    assert core.even_pick(list(range(5)), 20) == [0, 1, 2, 3, 4]
    assert core.even_pick(list(range(100)), 5) == [0, 25, 50, 74, 99]
    assert len(set(core.even_pick(list(range(21)), 20))) == 20
