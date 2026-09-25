"""The v2 baseline, frozen at first observation.

docs/01-methodology-protocol.md section 2; docs/02-technical-specification.md
section 4.4. The computation itself is vpi_core.baseline_v2(); this module
reads what it needs from the official API, as cheaply as the rule allows.

Per video, not per channel: the window is anchored to each measured video's
own publishedAt. A channel's uploads are read once per run and serve every
measured video of that channel (the in-run cache: nothing is persisted, the
baseline is frozen once computed).

Phases, each HTTP attempt counted (1 unit each):
  1. channels.list in blocks of 50 (part=snippet,statistics) - subscribers,
     customUrl. The uploads playlist is not requested: UC... -> UU...
  2. playlistItems.list, one channel per call (not batchable), paginated
     until the oldest window of that channel is covered or 3 pages are read.
     The date filter runs HERE, before any id is sent to videos.list.
  3. videos.list in blocks of 50 over the in-window ids, for duration and
     views; then per measured video: same format only, at most 20 spread
     evenly, median (vpi_core.baseline_v2).

This module reads no environment and creates no client at import.
"""

from __future__ import annotations

import os
import time
from datetime import timedelta

import requests

import vpi_core as core
from quota import QuotaCounter, QuotaExhausted

BASE = "https://www.googleapis.com/youtube/v3"
BLOCK = 50
RETRIES = 2
TIMEOUT_S = 15


class QuotaStop(Exception):
    """The API answered 403: stop everything, the run is partial."""


def uploads_playlist(channel_id: str) -> str:
    """UC... -> UU...: the uploads playlist, without a channels.list part."""
    if not channel_id.startswith("UC"):
        raise ValueError(f"not a channel id: {channel_id!r}")
    return "UU" + channel_id[2:]


def baselines_for_videos(measured, api_key=None, *, session=None, sleep=time.sleep, quota=None):
    """Baselines for the measured videos. Returns (results, report).

    measured: [{video_id, channel_id, format, published_at}]
    results:  {video_id: {baseline, samples, rule, span_days, video_ids}}
              for every measured video whose data was read in full. Left
              out, with report['outcome'] == 'partial': every video when a
              403 stopped the run, and the videos of a channel whose uploads
              or durations could not be read after the retries. A transient
              failure never produces 'not_computable': those videos have no
              baseline YET, and must not be given one by any other rule.
    report['unresolved'] = the measured video ids left out.

    Every HTTP attempt is marked on `quota` (shared by the run) before it is
    sent. The quota brake stops everything like a 403: nothing in this call
    is resolved, so the caller should pass channels in batches.
    channels: report['channels'] = {channel_id: {subscribers, custom_url, title}}
    """
    api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY is not set")
    http = session or requests.Session()
    quota = quota if quota is not None else QuotaCounter()
    report = {"quota_channels": 0, "quota_playlist": 0, "quota_videos": 0,
              "channels": {}, "playlist_missing": 0, "errors": 0,
              "stop_reason": None, "outcome": None}

    def get(endpoint, params, counter):
        params = {**params, "key": api_key}
        why = None
        for attempt in range(RETRIES + 1):
            try:
                quota.mark(counter.removeprefix("quota_"))
            except QuotaExhausted as e:
                raise QuotaStop(str(e))
            report[counter] += 1
            try:
                res = http.get(f"{BASE}/{endpoint}", params=params, timeout=TIMEOUT_S)
            except requests.RequestException as e:
                why = f"network: {type(e).__name__}"
            else:
                if res.status_code == 200:
                    return res.json()
                if res.status_code == 403:
                    raise QuotaStop(f"403 on {endpoint}")
                if res.status_code == 404:
                    return None
                why = f"HTTP {res.status_code}"
                if res.status_code < 500:
                    break
            if attempt < RETRIES:
                sleep(2 ** attempt)
        report["errors"] += 1
        return {"_error": why}

    measured = list(measured)
    by_channel: dict[str, list] = {}
    for m in measured:
        by_channel.setdefault(m["channel_id"], []).append(m)
    channel_ids = sorted(by_channel)
    results: dict = {}
    failed_channels: set[str] = set()

    try:
        # 1. channels.list, 50 per call
        for i in range(0, len(channel_ids), BLOCK):
            block = channel_ids[i:i + BLOCK]
            data = get("channels", {"part": "snippet,statistics",
                                    "id": ",".join(block), "maxResults": BLOCK},
                       "quota_channels") or {}
            for it in data.get("items", []):
                stats, snip = it.get("statistics", {}), it.get("snippet", {})
                subs = stats.get("subscriberCount")
                report["channels"][it["id"]] = {
                    "subscribers": int(subs) if subs is not None and not stats.get("hiddenSubscriberCount") else None,
                    "custom_url": snip.get("customUrl"),
                    "title": snip.get("title"),
                }

        # 2. playlistItems, one channel per call, date filter here
        in_window: dict[str, dict] = {}      # video_id -> {channel_id, published_at}
        for ch in channel_ids:
            refs = [core._as_datetime(m["published_at"]) for m in by_channel[ch]]
            oldest_needed = min(refs) - timedelta(days=core.BASELINE_MAX_AGE_DAYS)
            params = {"part": "contentDetails", "maxResults": BLOCK,
                      "playlistId": uploads_playlist(ch)}
            for _page in range(core.BASELINE_PAGES_MAX):
                data = get("playlistItems", params, "quota_playlist")
                if data is None:
                    report["playlist_missing"] += 1
                    break
                if "_error" in data:
                    failed_channels.add(ch)
                    break
                oldest_seen = None
                for it in data.get("items", []):
                    cd = it.get("contentDetails", {})
                    vid, pub = cd.get("videoId"), cd.get("videoPublishedAt")
                    if not vid or not pub:
                        continue
                    p = core._as_datetime(pub)
                    oldest_seen = p if oldest_seen is None or p < oldest_seen else oldest_seen
                    if any(core.BASELINE_MIN_AGE_DAYS <= (r - p).total_seconds() / 86400.0
                           <= core.BASELINE_MAX_AGE_DAYS for r in refs):
                        in_window[vid] = {"channel_id": ch, "published_at": pub}
                token = data.get("nextPageToken")
                if not token or (oldest_seen is not None and oldest_seen < oldest_needed):
                    break
                params = {**params, "pageToken": token}

        # 3. videos.list over the in-window ids, 50 per call
        ids = sorted(set(in_window) - {m["video_id"] for m in measured})
        details: dict[str, dict] = {}
        for i in range(0, len(ids), BLOCK):
            block = ids[i:i + BLOCK]
            data = get("videos", {"part": "contentDetails,statistics",
                                  "id": ",".join(block),
                                  "maxResults": BLOCK}, "quota_videos") or {}
            if "_error" in data:
                failed_channels.update(in_window[v]["channel_id"] for v in block)
                continue
            for it in data.get("items", []):
                seconds = core.parse_iso_duration(it.get("contentDetails", {}).get("duration", ""))
                raw = it.get("statistics", {}).get("viewCount")
                details[it["id"]] = {"format": core.formato_da_durata(seconds),
                                     "views": int(raw) if raw is not None else None}
    except QuotaStop as e:
        report["stop_reason"] = str(e)
        report["outcome"] = "partial"
        report["unresolved"] = sorted(m["video_id"] for m in measured)
        return results, report

    # per measured video: same channel, same format, its own window
    report["unresolved"] = sorted(m["video_id"] for m in measured
                                  if m["channel_id"] in failed_channels)
    for m in measured:
        if m["channel_id"] in failed_channels:
            continue
        samples = [{"video_id": vid, "published_at": w["published_at"],
                    "views": details[vid]["views"]}
                   for vid, w in in_window.items()
                   if w["channel_id"] == m["channel_id"]
                   and vid in details and details[vid]["format"] == m["format"]]
        results[m["video_id"]] = core.baseline_v2(samples, m["video_id"], m["published_at"])

    report["outcome"] = "ok" if not report["unresolved"] else "partial"
    return results, report
