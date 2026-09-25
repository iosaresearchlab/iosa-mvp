"""T-07: backend/census.py on mocked HTTP. No test here reaches YouTube.

docs/02-technical-specification.md section 4.3; docs/01-methodology-protocol.md
sections 4 and 5; docs/08-implementation-plan.md T-07.
"""

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import responses

import census

KEY = "test-key-not-real"


def item(vid, channel="UCa", duration="PT45S", views="1000", published="2026-09-20T10:00:00Z"):
    it = {"id": vid,
          "snippet": {"channelId": channel, "publishedAt": published},
          "contentDetails": {"duration": duration},
          "statistics": {}}
    if views is not None:
        it["statistics"]["viewCount"] = views
    return it


class FakeAPI:
    """Answers videos.list?chart=mostPopular per (regionCode, videoCategoryId).

    slices[(country, category)] is either a list of pages (each a list of
    items), or a list of status codes / pages consumed one per attempt.
    """

    def __init__(self, slices):
        self.slices = slices
        self.calls = []

    def __call__(self, request):
        q = {k: v[0] for k, v in parse_qs(urlparse(request.url).query).items()}
        self.calls.append(q)
        spec = self.slices.get((q.get("regionCode"), q.get("videoCategoryId")), 404)
        if isinstance(spec, int):
            return self._status(spec)
        if isinstance(spec, dict):  # scripted attempts: {"attempts": [...]}
            nxt = spec["attempts"].pop(0)
            if isinstance(nxt, int):
                return self._status(nxt)
            return (200, {}, json.dumps({"items": nxt}))
        page = int(q.get("pageToken", "p0")[1:])
        body = {"items": spec[page]}
        if page + 1 < len(spec):
            body["nextPageToken"] = f"p{page + 1}"
        return (200, {}, json.dumps(body))

    @staticmethod
    def _status(code):
        body = {"error": {"code": code, "errors": [{"reason": "quotaExceeded" if code == 403 else "x"}]}}
        return (code, {}, json.dumps(body))


@pytest.fixture
def api():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        holder = {}

        def install(slices):
            fake = FakeAPI(slices)
            rsps.add_callback(responses.GET, census.API_URL, callback=fake)
            holder["fake"] = fake
            return fake
        yield install


def run(countries, categories, **kw):
    kw.setdefault("sleep", lambda s: None)
    return census.read_charts(countries, categories, KEY, **kw)


# --- what is read, and how -------------------------------------------------


def test_thirteen_categories_without_19_and_27():
    assert len(census.CATEGORY_MAP) == 13
    assert "19" not in census.CATEGORY_MAP and "27" not in census.CATEGORY_MAP
    assert len(census.TARGET_COUNTRIES) == 34 == len(set(census.TARGET_COUNTRIES))


def test_category_names_match_the_frontend_segments():
    ts = (Path(__file__).resolve().parent.parent
          / "frontend" / "src" / "lib" / "segments.ts").read_text(encoding="utf-8")
    block = ts[ts.index("export const CATEGORIE = ["):]
    block = block[:block.index("];")]
    assert sorted(re.findall(r"'([^']+)'", block)) == sorted(census.CATEGORY_MAP.values())


def test_every_request_is_a_category_chart_never_the_general_chart(api):
    fake = api({("IT", "24"): [[item("a")]], ("US", "10"): [[item("b")]]})
    run(["IT", "US"], ["24", "10"])
    assert fake.calls, "no request made"
    for q in fake.calls:
        assert q["chart"] == "mostPopular"
        assert q.get("videoCategoryId"), "general chart requested"
        assert q["part"] == "snippet,contentDetails,statistics"
        assert q["maxResults"] == "50"
        assert q["key"] == KEY


# --- the closing check of T-07 ---------------------------------------------


def test_pagination_to_exhaustion(api):
    pages = [[item(f"v{p}_{i}") for i in range(50)] for p in range(3)] + [[item("last")]]
    fake = api({("IT", "24"): pages})
    videos, rep = run(["IT"], ["24"])
    assert len(videos) == 151
    assert len(fake.calls) == rep["quota_charts"] == 4
    assert [c.get("pageToken") for c in fake.calls] == [None, "p1", "p2", "p3"]
    assert rep["complete"] and rep["outcome"] == "ok"


def test_404_on_a_slice_skips_it_without_failing_the_run(api):
    api({("IT", "24"): [[item("a")]], ("IT", "29"): 404})
    videos, rep = run(["IT"], ["24", "29"])
    assert set(videos) == {"a"}
    assert rep["slices_404"] == 1 and rep["slices_ok"] == 1
    assert rep["complete"] and rep["outcome"] == "ok"


def test_403_stops_everything_with_outcome_partial(api):
    slices = {("IT", k): [[item(f"it{k}")]] for k in ["1", "2", "10", "15"]}
    slices[("IT", "2")] = 403
    fake = api(slices)
    videos, rep = run(["IT"], ["1", "2", "10", "15"], workers=1)
    # sequential: slice 1 read, slice 2 answers 403, nothing is sent after it
    assert len(fake.calls) == rep["quota_charts"] == 2
    assert set(videos) == {"it1"}
    assert rep["outcome"] == "partial" and not rep["complete"]
    assert "quotaExceeded" in rep["stop_reason"]
    assert rep["slices_unread"] == 3


def test_403_under_concurrency_is_still_partial(api):
    slices = {(c, "24"): [[item(f"{c}1")]] for c in census.TARGET_COUNTRIES}
    slices[("IT", "24")] = 403
    fake = api(slices)
    _, rep = run(census.TARGET_COUNTRIES, ["24"], workers=8)
    assert rep["outcome"] == "partial"
    assert rep["quota_charts"] == len(fake.calls) <= 34


def test_dedup_across_slices(api):
    api({("IT", "24"): [[item("a", views="100"), item("b")]],
         ("US", "10"): [[item("a", views="120")]],
         ("DE", "24"): [[item("a", views="110")]]})
    videos, rep = run(["IT", "US", "DE"], ["24", "10"])
    assert set(videos) == {"a", "b"}
    assert videos["a"]["countries"] == {"IT", "US", "DE"}
    assert videos["a"]["categories"] == {"24", "10"}
    assert videos["a"]["views"] == 120
    assert rep["videos_seen"] == 2 and rep["channels_seen"] == 1


def test_call_count_for_a_three_country_fixture_is_exact(api):
    # IT: 3 + 1 + 404  | US: 2 + 1 + 1 | DE: 404 + 1 + (5xx, 5xx, ok)
    slices = {
        ("IT", "1"): [[item("i1")], [item("i2")], [item("i3")]],
        ("IT", "10"): [[item("i4")]],
        ("IT", "29"): 404,
        ("US", "1"): [[item("u1")], [item("u2")]],
        ("US", "10"): [[item("u3")]],
        ("US", "29"): [[item("u4")]],
        ("DE", "1"): 404,
        ("DE", "10"): [[item("d1")]],
        ("DE", "29"): {"attempts": [503, 500, [item("d2")]]},
    }
    fake = api(slices)
    videos, rep = run(["IT", "US", "DE"], ["1", "10", "29"])
    expected = 3 + 1 + 1 + 2 + 1 + 1 + 1 + 1 + 3
    assert len(fake.calls) == rep["quota_charts"] == expected == 14
    assert rep["slices_ok"] == 7 and rep["slices_404"] == 2 and rep["slices_error"] == 0
    assert len(videos) == 10 and rep["outcome"] == "ok"


# --- partial readings: an unread slice is not an absence -------------------


def test_a_slice_still_failing_after_retries_makes_the_census_incomplete(api):
    fake = api({("IT", "24"): [[item("a")]], ("IT", "10"): 503})
    videos, rep = run(["IT"], ["24", "10"])
    assert set(videos) == {"a"}  # presence observed where we did read
    assert rep["slices_error"] == 1
    assert len(fake.calls) == 1 + 1 + census.RETRIES
    assert not rep["complete"] and rep["outcome"] == "partial"


def test_a_4xx_other_than_403_and_404_is_not_retried_and_is_incomplete(api):
    fake = api({("IT", "24"): 400})
    _, rep = run(["IT"], ["24"])
    assert len(fake.calls) == 1
    assert rep["outcome"] == "partial"


def test_videos_without_a_usable_duration_are_discarded_and_counted(api):
    api({("IT", "24"): [[item("live", duration="P0D"), item("ok")]]})
    videos, rep = run(["IT"], ["24"])
    assert set(videos) == {"ok"}
    assert rep["discards"]["no_duration"] == 1


def test_format_is_classified_by_duration(api):
    api({("IT", "24"): [[item("s", duration="PT3M"), item("l", duration="PT3M1S")]]})
    videos, _ = run(["IT"], ["24"])
    assert videos["s"]["format"] == "SHORT" and videos["l"]["format"] == "LONG"


def test_missing_api_key_is_an_error_not_a_silent_empty_census(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        census.read_charts(["IT"], ["24"])


# --- the database side, with a recording client ----------------------------


class RecordingClient:
    def __init__(self, rpc_pages=None):
        self.ops = []
        self.rpc_pages = list(rpc_pages or [])

    def table(self, name):
        client = self

        class T:
            def upsert(self, rows):
                client.ops.append(("upsert", name, rows))
                return self

            def execute(self):
                return type("R", (), {"data": None})()
        return T()

    def rpc(self, fn, params):
        client = self

        class Q:
            def order(self, col):
                client.ops.append(("order", fn, col))
                return self

            def range(self, a, b):
                client.ops.append(("range", fn, a, b))
                return self

            def execute(self):
                client.ops.append(("rpc", fn, params))
                data = client.rpc_pages.pop(0) if client.rpc_pages else None
                return type("R", (), {"data": data})()
        return Q()


def test_close_exits_after_a_partial_run_makes_no_database_call():
    db = RecordingClient()
    assert census.close_exits(db, date(2026, 10, 2), run_complete=False) == 0
    assert db.ops == []


def test_close_exits_after_a_complete_run_calls_the_database_function():
    db = RecordingClient(rpc_pages=[7])
    assert census.close_exits(db, date(2026, 10, 2), run_complete=True) == 7
    assert db.ops == [("rpc", "close_exits_of_day", {"d": "2026-10-02"})]


def test_entries_reads_every_page_of_the_rpc():
    full = [{"video_id": f"v{i}", "gap_days": 0, "entry_certain": True}
            for i in range(census.RPC_PAGE)]
    db = RecordingClient(rpc_pages=[full, full, full[:3]])
    got = census.entries(db, date(2026, 10, 2))
    assert len(got) == 2 * census.RPC_PAGE + 3
    ranges = [op[2:] for op in db.ops if op[0] == "range"]
    assert ranges == [(0, 999), (1000, 1999), (2000, 2999)]


def test_save_snapshot_writes_every_video_in_batches_with_the_permanent_flag():
    videos = {f"v{i:04d}": {"channel_id": "UCa", "format": "SHORT",
                            "published_at": None, "views": 1,
                            "countries": {"US", "IT"}, "categories": {"24", "10"}}
              for i in range(1201)}
    db = RecordingClient()
    assert census.save_snapshot(db, date(2026, 10, 1), videos, permanent=True) == 1201
    batches = [op[2] for op in db.ops if op[0] == "upsert"]
    assert [len(b) for b in batches] == [500, 500, 201]
    row = batches[0][0]
    assert row["day"] == "2026-10-01" and row["permanent"] is True
    assert row["countries"] == ["IT", "US"] and row["categories"] == ["10", "24"]
    assert all(op[1] == "trend_snapshot" for op in db.ops)
