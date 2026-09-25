"""Census of YouTube's Most Popular category charts, and the daily snapshot.

docs/02-technical-specification.md section 4.3; docs/01-methodology-protocol.md
sections 4 and 5.

Only the CATEGORY charts are read (34 countries x 13 categories = 442 slices,
of which 414 return data). YouTube's own general chart (no videoCategoryId) is
never requested: it is a curated showcase, not ordered by views, and 58.8% of
its videos appear in no category chart (01 section 5).

The partial-reading rule (01 section 4): a partial reading observes presence
but not absence. read_charts() reports whether the census was complete;
close_exits() refuses to run when it was not.

This module creates no database client and reads no environment at import:
callers pass the Supabase client and the API key.
"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import requests

from vpi_core import formato_da_durata, parse_iso_duration

API_URL = "https://www.googleapis.com/youtube/v3/videos"

TARGET_COUNTRIES = [
    'US', 'IT', 'GB', 'DE', 'FR', 'ES', 'BR', 'JP', 'IN', 'CA', 'AU',
    'MX', 'AR', 'KR', 'NL', 'PL', 'SE', 'NO', 'FI', 'DK', 'ZA', 'TR',
    'CH', 'AT', 'BE', 'PT', 'IE', 'NZ', 'CL', 'CO', 'PH', 'ID', 'TH', 'VN',
]

# 13 categories. 19 (Travel & Events) and 27 (Education) return 404 in all 34
# countries and are not requested. 29 answers in 6 countries with 1 video: it
# is kept, it costs 34 calls. Names must match frontend/src/lib/segments.ts.
CATEGORY_MAP = {
    '1': 'Film & Animation',
    '2': 'Autos & Vehicles',
    '10': 'Music',
    '15': 'Pets & Animals',
    '17': 'Sports',
    '20': 'Gaming',
    '22': 'People & Blogs',
    '23': 'Comedy',
    '24': 'Entertainment',
    '25': 'News & Politics',
    '26': 'Howto & Style',
    '28': 'Tech',
    '29': 'Nonprofits & Activism',
}

WORKERS = 10          # measured: 1,486 calls in 112 s at this concurrency
RETRIES = 2           # extra attempts on a 5xx or a network error
TIMEOUT_S = 15
SNAPSHOT_BATCH = 500
RPC_PAGE = 1000       # PostgREST returns at most 1,000 rows per request


def read_charts(countries, categories, api_key=None, *, workers=WORKERS,
                session=None, sleep=time.sleep):
    """Full census of the category charts. Returns (videos, report).

    videos: {video_id: {channel_id, format, published_at, views,
                        countries: set, categories: set}}

    One call per page (part=snippet,contentDetails,statistics, maxResults=50),
    following nextPageToken to exhaustion. Every HTTP attempt costs 1 unit
    and is counted in report['quota_charts'].

    - 404 on a slice's first page: the slice does not exist; skipped, and the
      census can still be complete.
    - 403: everything stops, outcome 'partial'.
    - 5xx or network error: retried RETRIES times; if it still fails the
      slice is unread, and the census is not complete.
    - any other status: the slice is unread, the census is not complete.

    Slices are processed in the order given; the caller randomises it (T-10).
    """
    api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY is not set")
    http = session or requests.Session()

    stop = threading.Event()
    lock = threading.Lock()
    videos: dict = {}
    report = {
        "quota_charts": 0, "slices_ok": 0, "slices_404": 0, "slices_error": 0,
        "slices_unread": 0, "videos_seen": 0, "channels_seen": 0,
        "discards": {"no_duration": 0, "no_channel": 0},
        "stop_reason": None, "complete": False, "outcome": None,
    }

    def call(params):
        """One counted HTTP attempt. None if stopped before sending."""
        if stop.is_set():
            return None
        with lock:
            report["quota_charts"] += 1
        return http.get(API_URL, params=params, timeout=TIMEOUT_S)

    def fetch_page(params):
        """('ok', json) | ('404', None) | ('403', reason) | ('error', why) | ('stopped', None)"""
        for attempt in range(RETRIES + 1):
            try:
                res = call(params)
            except requests.RequestException as e:
                why = f"network: {type(e).__name__}"
            else:
                if res is None:
                    return "stopped", None
                if res.status_code == 200:
                    return "ok", res.json()
                if res.status_code == 404:
                    return "404", None
                if res.status_code == 403:
                    return "403", _reason(res)
                why = f"HTTP {res.status_code}"
                if res.status_code < 500:
                    return "error", why
            if attempt < RETRIES:
                sleep(2 ** attempt)
        return "error", why

    def read_slice(country, category):
        params = {
            "part": "snippet,contentDetails,statistics",
            "chart": "mostPopular",
            "maxResults": 50,
            "regionCode": country,
            "videoCategoryId": category,
            "key": api_key,
        }
        items, first = [], True
        while True:
            state, payload = fetch_page(params)
            if state == "ok":
                items.extend(payload.get("items", []))
                token = payload.get("nextPageToken")
                if not token:
                    break
                params = {**params, "pageToken": token}
                first = False
                continue
            with lock:
                if state == "404" and first:
                    report["slices_404"] += 1
                elif state == "403":
                    report["stop_reason"] = f"403 on {country}/{category}: {payload}"
                    report["slices_unread"] += 1
                    stop.set()
                elif state == "stopped":
                    report["slices_unread"] += 1
                else:
                    report["slices_error"] += 1
            return
        with lock:
            report["slices_ok"] += 1
            for item in items:
                _merge(videos, item, country, category, report["discards"])

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for f in [pool.submit(read_slice, c, k) for c in countries for k in categories]:
            f.result()

    report["videos_seen"] = len(videos)
    report["channels_seen"] = len({v["channel_id"] for v in videos.values()})
    report["complete"] = (report["slices_error"] == 0
                          and report["slices_unread"] == 0
                          and not stop.is_set())
    report["outcome"] = "ok" if report["complete"] else "partial"
    return videos, report


def _reason(res):
    try:
        return res.json()["error"]["errors"][0]["reason"]
    except Exception:
        return "unknown"


def _merge(videos, item, country, category, discards):
    """Add one chart item, deduplicating across slices."""
    vid = item.get("id")
    snippet = item.get("snippet", {})
    seconds = parse_iso_duration(item.get("contentDetails", {}).get("duration", ""))
    fmt = formato_da_durata(seconds)
    if fmt is None:
        discards["no_duration"] += 1   # live streams, premieres
        return
    channel = snippet.get("channelId")
    if not channel:
        discards["no_channel"] += 1
        return
    raw = item.get("statistics", {}).get("viewCount")
    views = int(raw) if raw is not None else None
    v = videos.get(vid)
    if v is None:
        videos[vid] = {
            "channel_id": channel,
            "format": fmt,
            "published_at": snippet.get("publishedAt"),
            "views": views,
            "countries": {country},
            "categories": {category},
        }
        return
    v["countries"].add(country)
    v["categories"].add(category)
    # The same call window; if two slices disagree, keep the higher count
    # rather than whichever thread happened to answer first.
    if views is not None and (v["views"] is None or views > v["views"]):
        v["views"] = views


def save_snapshot(client, day: date, videos: dict, *, permanent=False) -> int:
    """Write the day's snapshot, every video seen, ingested or not.

    permanent=True only for day 0 (02 section 3.1).
    """
    rows = [{
        "day": day.isoformat(),
        "video_id": vid,
        "channel_id": v["channel_id"],
        "format": v["format"],
        "published_at": v["published_at"],
        "views": v["views"],
        "countries": sorted(v["countries"]),
        "categories": sorted(v["categories"], key=int),
        "permanent": permanent,
    } for vid, v in sorted(videos.items())]
    for i in range(0, len(rows), SNAPSHOT_BATCH):
        client.table("trend_snapshot").upsert(rows[i:i + SNAPSHOT_BATCH]).execute()
    return len(rows)


def entries(client, day: date) -> list[dict]:
    """The day's entries: [{video_id, gap_days, entry_certain}], all pages."""
    out, start = [], 0
    while True:
        page = (client.rpc("entries_of_day", {"d": day.isoformat()})
                .order("video_id")
                .range(start, start + RPC_PAGE - 1)
                .execute().data) or []
        out.extend(page)
        if len(page) < RPC_PAGE:
            return out
        start += RPC_PAGE


def close_exits(client, day: date, run_complete: bool) -> int:
    """Close the v2 records absent from today's snapshot.

    Never after a partial run: absence is not observable in an unfinished
    read. Then nothing is touched and 0 is returned (01 section 4).
    """
    if not run_complete:
        return 0
    return client.rpc("close_exits_of_day", {"d": day.isoformat()}).execute().data or 0
