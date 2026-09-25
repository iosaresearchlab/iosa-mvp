"""The two formats in the v2 engine, with the API mocked (T-10 rewrite).

The claim this file has always proved, now on the v2 path: from one read of
a channel's uploads come two separate baselines, and the Shorts baseline does
not move when the same channel's long videos are added. The quota is a daily
budget and is not spent on tests.

docs/01-methodology-protocol.md sections 1 and 2.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import responses

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import baseline as bl  # noqa: E402

REF = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _api(uploads, calls):
    """uploads: [(video_id, days_before_REF, duration, views)]"""
    def cb(request):
        u = urlparse(request.url)
        ep = u.path.rsplit("/", 1)[-1]
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        calls.append(ep)
        if ep == "channels":
            return (200, {}, json.dumps({"items": [{"id": "UCx", "snippet": {}, "statistics": {}}]}))
        if ep == "playlistItems":
            return (200, {}, json.dumps({"items": [
                {"contentDetails": {"videoId": v, "videoPublishedAt": _iso(REF - timedelta(days=d))}}
                for v, d, _, _ in uploads]}))
        by_id = {v: (dur, n) for v, _, dur, n in uploads}
        return (200, {}, json.dumps({"items": [
            {"id": v, "contentDetails": {"duration": by_id[v][0]},
             "statistics": {"viewCount": str(by_id[v][1])}} for v in q["id"].split(",")]}))
    return cb


def _baselines(uploads, measured_formats=("SHORT", "LONG")):
    calls = []
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        for ep in ("channels", "playlistItems", "videos"):
            rsps.add_callback(responses.GET, f"{bl.BASE}/{ep}", callback=_api(uploads, calls))
        measured = [{"video_id": f"m_{f}", "channel_id": "UCx", "format": f,
                     "published_at": _iso(REF)} for f in measured_formats]
        res, _ = bl.baselines_for_videos(measured, "test-key", sleep=lambda s: None)
    return res, calls


SHORTS = [(f"s{i}", 10 + 3 * i, "PT45S", 100 * (i + 1)) for i in range(7)]      # median 400
LONGS = [(f"l{i}", 11 + 3 * i, "PT12M30S", 50_000 + i) for i in range(6)]


def test_samples_come_out_split_by_format():
    res, _ = _baselines(SHORTS + LONGS)
    assert set(res["m_SHORT"]["video_ids"]) == {v for v, *_ in SHORTS}
    assert set(res["m_LONG"]["video_ids"]) == {v for v, *_ in LONGS}


def test_the_shorts_baseline_does_not_change_when_long_videos_are_added():
    only_shorts, _ = _baselines(SHORTS, ("SHORT",))
    mixed, _ = _baselines(SHORTS + LONGS)
    assert only_shorts["m_SHORT"]["baseline"] == mixed["m_SHORT"]["baseline"] == 400.0
    assert mixed["m_LONG"]["baseline"] == 50_002.5


def test_unusable_durations_enter_no_format():
    live = [("live1", 12, "P0D", 10**7), ("live2", 13, "", 10**7)]
    res, _ = _baselines(SHORTS + LONGS + live)
    for r in res.values():
        assert not {"live1", "live2"} & set(r["video_ids"])


def test_one_read_of_the_uploads_serves_both_formats():
    _, calls = _baselines(SHORTS + LONGS)
    assert calls.count("playlistItems") == 1 and calls.count("videos") == 1
