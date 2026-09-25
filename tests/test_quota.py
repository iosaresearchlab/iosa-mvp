"""T-09: the quota counter and the brake.

docs/02-technical-specification.md section 4.6; docs/08 T-09. Mocked HTTP
only: the brake is proved without spending a unit.
"""

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
import responses

import baseline as bl
import census
import quota as q

KEY = "test-key-not-real"


def chart_item(vid):
    return {"id": vid, "snippet": {"channelId": "UCa", "publishedAt": "2026-09-20T10:00:00Z"},
            "contentDetails": {"duration": "PT40S"}, "statistics": {"viewCount": "10"}}


@pytest.fixture
def charts():
    """20 slices of one page each; records every request that reaches the API."""
    seen = []

    def cb(request):
        qs = {k: v[0] for k, v in parse_qs(urlparse(request.url).query).items()}
        seen.append(qs)
        return (200, {}, json.dumps({"items": [chart_item(qs["regionCode"] + qs["videoCategoryId"])]}))

    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_callback(responses.GET, census.API_URL, callback=cb)
        yield seen


COUNTRIES = census.TARGET_COUNTRIES[:4]
CATS = list(census.CATEGORY_MAP)[:5]          # 4 x 5 = 20 slices, 20 calls


def test_limit_10_stops_at_exactly_10_calls_and_reports_partial(charts):
    counter = q.QuotaCounter(limit=10)
    videos, rep = census.read_charts(COUNTRIES, CATS, KEY, workers=1, quota=counter)
    assert len(charts) == 10 == counter.total == rep["quota_charts"]
    assert rep["outcome"] == "partial" and not rep["complete"]
    assert "quota brake" in rep["stop_reason"]
    assert counter.braked and len(videos) == 10


def test_under_concurrency_the_brake_is_still_exact(charts):
    counter = q.QuotaCounter(limit=10)
    _, rep = census.read_charts(COUNTRIES, CATS, KEY, workers=8, quota=counter)
    assert len(charts) == 10 == counter.total
    assert rep["outcome"] == "partial"


def test_without_the_brake_firing_the_counter_equals_the_calls(charts):
    counter = q.QuotaCounter(limit=100)
    _, rep = census.read_charts(COUNTRIES, CATS, KEY, workers=8, quota=counter)
    assert len(charts) == counter.total == 20 and rep["outcome"] == "ok"
    assert not counter.braked


def test_one_counter_across_census_and_baseline_no_drift():
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    seen = []

    def api(request):
        u = urlparse(request.url)
        ep = u.path.rsplit("/", 1)[-1]
        qs = {k: v[0] for k, v in parse_qs(u.query).items()}
        seen.append(ep)
        if ep == "videos" and qs.get("chart") == "mostPopular":
            return (200, {}, json.dumps({"items": [chart_item("v" + qs["regionCode"])]}))
        if ep == "channels":
            return (200, {}, json.dumps({"items": [{"id": "UCa", "snippet": {}, "statistics": {}}]}))
        if ep == "playlistItems":
            items = [{"contentDetails": {"videoId": f"u{i}", "videoPublishedAt":
                     (now - timedelta(days=10 + i)).strftime("%Y-%m-%dT%H:%M:%SZ")}} for i in range(8)]
            return (200, {}, json.dumps({"items": items}))
        ids = qs["id"].split(",")
        return (200, {}, json.dumps({"items": [{"id": i, "contentDetails": {"duration": "PT30S"},
                                                "statistics": {"viewCount": "5"}} for i in ids]}))

    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        for ep in ("videos", "channels", "playlistItems"):
            rsps.add_callback(responses.GET, f"https://www.googleapis.com/youtube/v3/{ep}", callback=api)
        counter = q.QuotaCounter(limit=1000)
        census.read_charts(["IT", "US", "DE"], ["24"], KEY, quota=counter)
        res, _ = bl.baselines_for_videos(
            [{"video_id": "vIT", "channel_id": "UCa", "format": "SHORT",
              "published_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}], KEY, quota=counter)
    assert counter.total == len(seen) == 3 + 1 + 1 + 1
    assert counter.as_ingest_run() == {"quota_charts": 3, "quota_channels": 1, "quota_playlist": 1,
                                       "quota_videos": 1, "quota_total": 6}
    assert res["vIT"]["rule"] == "standard"


def test_the_brake_inside_baseline_resolves_nothing_and_sends_nothing_more():
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    seen = []

    def api(request):
        seen.append(request.url)
        ep = urlparse(request.url).path.rsplit("/", 1)[-1]
        if ep == "channels":
            return (200, {}, json.dumps({"items": []}))
        return (200, {}, json.dumps({"items": []}))

    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        for ep in ("channels", "playlistItems", "videos"):
            rsps.add_callback(responses.GET, f"https://www.googleapis.com/youtube/v3/{ep}", callback=api)
        counter = q.QuotaCounter(limit=3)
        measured = [{"video_id": f"m{i}", "channel_id": f"UC{i}", "format": "SHORT",
                     "published_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")} for i in range(5)]
        res, rep = bl.baselines_for_videos(measured, KEY, quota=counter)
    assert len(seen) == 3 == counter.total
    assert res == {} and rep["outcome"] == "partial" and len(rep["unresolved"]) == 5
    assert "quota brake" in rep["stop_reason"]


# --- the limit itself --------------------------------------------------------


def test_default_limit_is_9500(monkeypatch):
    monkeypatch.delenv("QUOTA_MAX_DAILY", raising=False)
    assert q.QuotaCounter().limit == 9500


def test_the_limit_can_be_lowered(monkeypatch):
    monkeypatch.setenv("QUOTA_MAX_DAILY", "2000")
    assert q.QuotaCounter().limit == 2000


def test_the_brake_cannot_be_raised_above_9500(monkeypatch):
    monkeypatch.setenv("QUOTA_MAX_DAILY", "20000")
    assert q.QuotaCounter().limit == 9500
    assert q.QuotaCounter(limit=10**9).limit == 9500


@pytest.mark.parametrize("bad", ["0", "-5", "abc"])
def test_a_nonsense_limit_is_an_error_not_an_unlimited_run(monkeypatch, bad):
    monkeypatch.setenv("QUOTA_MAX_DAILY", bad)
    with pytest.raises(ValueError):
        q.QuotaCounter()


def test_an_unknown_endpoint_is_refused():
    with pytest.raises(ValueError):
        q.QuotaCounter(limit=5).mark("search")
