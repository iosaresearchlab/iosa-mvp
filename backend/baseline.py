"""The v2 baseline, frozen at first observation.

docs/01-methodology-protocol.md section 2; docs/02-technical-specification.md
section 4.4. The computation itself is vpi_core.baseline_v2(); this module
reads what it needs from the official API, as cheaply as the rule allows,
without changing what the rule computes.

Per video, not per channel: the window is anchored to each measured video's
own publishedAt. Per channel, once per run: a channel is read once in a run,
over the union of its measured videos' windows.

The channel inventory (02 section 4.4, GATE-2). A video's id, publishedAt and
duration never change, so they are kept across runs (channel_inventory). Views
change: they are read in the run that computes the baseline, for all the from an earlier run. Every choice is made on
the set a fresh read would give:
  - only the 150 most recent uploads are ever considered: the 3-page cap;
  - a chosen sample that videos.list no longer returns is removed and the 20
    are chosen again; a hidden view count is excluded and chosen again.

Phases, each HTTP attempt marked on the run's QuotaCounter (1 unit each):
  1. channels.list in blocks of 50 (part=snippet,statistics).
  2. playlistItems.list, one channel per call: a full read (from the newest,
     up to 3 pages, until the window is covered) for a channel never read or
     not read far enough back; otherwise a forward refresh from the newest,
     stopping at the first page holding an already-known video.
  3. videos.list in blocks of 50 over every candidate a fresh read would
     consider: the in-window ids, plus all 150 most recent when the cap
     truncates a window (contentDetails + statistics + status, 1 unit per
     call). Gone or not public -> removed; if that happens among the 150 most
     recent while the cap binds, the channel is read again from the newest.
  4. per measured video: public, same format, views readable, 20 evenly.

This module reads no environment and creates no client at import.
"""

from __future__ import annotations

import copy
import os
import time
from datetime import datetime, timezone

import requests

import vpi_core as core
from quota import QuotaCounter, QuotaExhausted

BASE = "https://www.googleapis.com/youtube/v3"
BLOCK = 50
RETRIES = 2
TIMEOUT_S = 15
INVENTORY_MAX = core.BASELINE_PAGES_MAX * BLOCK       # 150: what 3 pages return


class QuotaStop(Exception):
    """The API answered 403 or the brake fired: stop, the run is partial."""


def uploads_playlist(channel_id: str) -> str:
    """UC... -> UU...: the uploads playlist, without a channels.list part."""
    if not channel_id.startswith("UC"):
        raise ValueError(f"not a channel id: {channel_id!r}")
    return "UU" + channel_id[2:]


def _epoch(value) -> int:
    return int(core._as_datetime(value).timestamp())


def _iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def empty_inventory():
    return {"items": {}, "covered_back_to": None, "capped": False, "ended": False,
            "refreshed_on": None}


def new_run_state():
    """What a run remembers across baselines_for_videos() calls: channels
    already refreshed, channel metadata, and the view counts read in this run."""
    return {"inv": {}, "meta": {}, "views": {}, "checked": set()}


class MemoryInventory:
    """Inventory store in memory (tests, dry runs)."""

    def __init__(self, data=None):
        self.data = copy.deepcopy(data or {})

    def load(self, channel_ids):
        return {c: copy.deepcopy(self.data[c]) for c in channel_ids if c in self.data}

    def save(self, invs):
        self.data.update(copy.deepcopy(invs))


class SupabaseInventory:
    """Inventory store in public.channel_inventory (02 section 3.1.2)."""

    def __init__(self, client, batch=100):
        self.client, self.batch = client, batch

    def load(self, channel_ids):
        ids, out = list(channel_ids), {}
        for i in range(0, len(ids), self.batch):
            rows = (self.client.table("channel_inventory").select("*")
                    .in_("channel_id", ids[i:i + self.batch]).execute().data) or []
            for r in rows:
                cbt = r.get("covered_back_to")
                out[r["channel_id"]] = {
                    "items": {k: [int(v[0]), v[1]] for k, v in (r["items"] or {}).items()},
                    "covered_back_to": _epoch(cbt) if cbt else None,
                    "capped": bool(r.get("capped")), "ended": bool(r.get("ended")),
                    "refreshed_on": r.get("refreshed_on"),
                }
        return out

    def save(self, invs):
        rows = [{"channel_id": ch, "items": inv["items"],
                 "covered_back_to": _iso(inv["covered_back_to"]) if inv["covered_back_to"] else None,
                 "capped": inv["capped"], "ended": inv["ended"],
                 "refreshed_on": inv["refreshed_on"]} for ch, inv in sorted(invs.items())]
        for i in range(0, len(rows), self.batch):
            self.client.table("channel_inventory").upsert(rows[i:i + self.batch]).execute()


def _recent(inv):
    """The uploads a fresh read could see: the 150 most recent."""
    ordered = sorted(inv["items"].items(), key=lambda kv: (kv[1][0], kv[0]), reverse=True)
    return ordered[:INVENTORY_MAX]


def _prune(inv):
    if len(inv["items"]) > INVENTORY_MAX:
        inv["items"] = dict(_recent(inv))
        inv["capped"] = True


def baselines_for_videos(measured, api_key=None, *, session=None, sleep=time.sleep, quota=None,
                         inventory=None, run_state=None, today=None):
    """Baselines for the measured videos. Returns (results, report).

    measured: [{video_id, channel_id, format, published_at}]
    results:  {video_id: {baseline, samples, rule, span_days, video_ids}} for
              every measured video whose data was read in full. Left out, with
              report['outcome'] == 'partial': every video when a 403 or the
              quota brake stopped the call (report['stop_reason'] set), and the
              videos of a channel whose uploads or durations could not be read
              after the retries. A transient failure never produces
              'not_computable'.
    report['unresolved'] = the measured video ids left out.
    """
    api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY is not set")
    http = session or requests.Session()
    quota = quota if quota is not None else QuotaCounter()
    store = inventory if inventory is not None else MemoryInventory()
    run = run_state if run_state is not None else new_run_state()
    today = (today or datetime.now(timezone.utc).date()).isoformat()
    report = {"quota_channels": 0, "quota_playlist": 0, "quota_videos": 0,
              "channels": {}, "playlist_missing": 0, "errors": 0,
              "full_reads": 0, "forward_refreshes": 0, "cached_in_run": 0, "removed": 0,
              "stop_reason": None, "outcome": None, "unresolved": []}

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
    failed: set[str] = set()
    changed: dict[str, dict] = {}
    results: dict = {}

    def read_page(ch, inv, params, known):
        data = get("playlistItems", params, "quota_playlist")
        if data is None:
            return None, None, False
        if "_error" in data:
            return "error", None, False
        seen_known, oldest = False, None
        for it in data.get("items", []):
            cd = it.get("contentDetails", {})
            vid, pub = cd.get("videoId"), cd.get("videoPublishedAt")
            if not vid or not pub:
                continue
            e = _epoch(pub)
            oldest = e if oldest is None or e < oldest else oldest
            if vid in known:
                seen_known = True
            if vid not in inv["items"]:
                inv["items"][vid] = [e, None]
        return data.get("nextPageToken"), oldest, seen_known

    try:
        # 1. channels.list, 50 per call, once per run
        need_meta = [c for c in channel_ids if c not in run["meta"]]
        for i in range(0, len(need_meta), BLOCK):
            block = need_meta[i:i + BLOCK]
            data = get("channels", {"part": "snippet,statistics",
                                    "id": ",".join(block), "maxResults": BLOCK},
                       "quota_channels") or {}
            for c in block:
                run["meta"].setdefault(c, {})
            for it in data.get("items", []):
                stats, snip = it.get("statistics", {}), it.get("snippet", {})
                subs = stats.get("subscriberCount")
                run["meta"][it["id"]] = {
                    "subscribers": int(subs) if subs is not None and not stats.get("hiddenSubscriberCount") else None,
                    "custom_url": snip.get("customUrl"),
                    "title": snip.get("title"),
                }
        report["channels"] = {c: run["meta"].get(c, {}) for c in channel_ids}

        # 2. uploads: once per run, full read or forward refresh
        loaded = store.load([c for c in channel_ids if c not in run["inv"]])
        for ch in channel_ids:
            if ch in run["inv"]:
                report["cached_in_run"] += 1
                continue
            inv = loaded.get(ch) or empty_inventory()
            refs = [_epoch(m["published_at"]) for m in by_channel[ch]]
            oldest_needed = min(refs) - core.BASELINE_MAX_AGE_DAYS * 86400
            known = set(inv["items"])
            full = (not known) or (not inv["capped"] and not inv["ended"]
                                   and (inv["covered_back_to"] is None
                                        or inv["covered_back_to"] > oldest_needed))
            params = {"part": "contentDetails", "maxResults": BLOCK, "playlistId": uploads_playlist(ch)}
            oldest_read, token, overlap, pages = None, None, False, 0
            report["full_reads" if full else "forward_refreshes"] += 1
            for pages in range(1, core.BASELINE_PAGES_MAX + 1):
                token, oldest, seen_known = read_page(ch, inv, params, known)
                if token == "error":
                    failed.add(ch)
                    break
                overlap = overlap or seen_known
                if oldest is not None:
                    oldest_read = oldest if oldest_read is None else min(oldest_read, oldest)
                if not token:
                    inv["ended"] = True         # the playlist ends here (or 404)
                    break
                if full and oldest_read is not None and oldest_read < oldest_needed:
                    break                       # the window is covered
                if not full and seen_known:
                    break                       # back to what we already hold
                params = {**params, "pageToken": token}
            if ch in failed:
                continue
            if not inv["items"]:
                report["playlist_missing"] += oldest_read is None
                inv["ended"] = True
            hit_cap = pages == core.BASELINE_PAGES_MAX and bool(token)
            if known and not overlap:
                # nothing read joins what we held (more than 150 new uploads):
                # the old items are no longer contiguous from the newest
                inv["items"] = {v: x for v, x in inv["items"].items() if v not in known}
                inv["covered_back_to"], inv["capped"] = None, False
            if full or (known and not overlap):
                prior = inv["covered_back_to"] if (known and overlap) else None
                inv["covered_back_to"] = (min(prior, oldest_read) if prior and oldest_read
                                          else oldest_read)
            if hit_cap:
                inv["capped"] = True            # the 150 most recent are held
            _prune(inv)
            inv["refreshed_on"] = today
            run["inv"][ch] = inv
            changed[ch] = inv

        def window(m):
            inv = run["inv"][m["channel_id"]]
            ref = _epoch(m["published_at"])
            lo, hi = ref - core.BASELINE_MAX_AGE_DAYS * 86400, ref - core.BASELINE_MIN_AGE_DAYS * 86400
            return [(e, v, f) for v, (e, f) in _recent(inv)
                    if lo <= e <= hi and v != m["video_id"]]

        def cap_binds(ch):
            """The 150-upload cap truncates some measured video's window."""
            inv = run["inv"][ch]
            if not inv["capped"]:
                return False
            recent = _recent(inv)
            oldest_held = recent[-1][1][0] if recent else None
            return any(oldest_held is not None and oldest_held >
                       _epoch(mm["published_at"]) - core.BASELINE_MAX_AGE_DAYS * 86400
                       for mm in by_channel[ch])

        def verify(chs):
            """3. Every candidate a fresh read would consider is checked in this
            run: in-window ids, plus all 150 when the cap truncates a window.
            Duration, views and privacy in one call (1 unit per 50 ids). Gone
            or no longer public -> removed. Returns the channels that lost an
            upload among their 150 most recent while the cap binds."""
            ids, owner, binding = set(), {}, set()
            for ch in chs:
                if cap_binds(ch):
                    binding.add(ch)
                    pool = [v for v, _ in _recent(run["inv"][ch])]
                else:
                    pool = [v for mm in by_channel[ch] for _, v, _ in window(mm)]
                for v in pool:
                    owner[v] = ch
                    if v not in run["views"] and v not in run["checked"]:
                        ids.add(v)
            ids = sorted(ids)
            lost = set()
            for i in range(0, len(ids), BLOCK):
                block = ids[i:i + BLOCK]
                data = get("videos", {"part": "contentDetails,statistics,status",
                                      "id": ",".join(block), "maxResults": BLOCK},
                           "quota_videos") or {}
                if "_error" in data:
                    failed.update(owner[v] for v in block)
                    continue
                public = set()
                for it in data.get("items", []):
                    if (it.get("status") or {}).get("privacyStatus", "public") != "public":
                        continue
                    seconds = core.parse_iso_duration(it.get("contentDetails", {}).get("duration", ""))
                    raw = it.get("statistics", {}).get("viewCount")
                    run["inv"][owner[it["id"]]]["items"][it["id"]][1] = core.formato_da_durata(seconds) or "NONE"
                    run["views"][it["id"]] = int(raw) if raw is not None else None
                    public.add(it["id"])
                for v in block:
                    run["checked"].add(v)
                for v in set(block) - public:
                    run["inv"][owner[v]]["items"].pop(v, None)
                    report["removed"] += 1
                    if owner[v] in binding:
                        lost.add(owner[v])
            return lost - failed

        todo_ch = [c for c in channel_ids if c not in failed]
        lost = verify(todo_ch)
        if lost:
            # the 150 most recent changed under a binding cap: read them again
            # from the newest, exactly as a fresh read would, and check again
            for ch in sorted(lost):
                inv = run["inv"][ch]
                kept = {v: x for v, x in inv["items"].items()}
                inv["items"], inv["capped"] = {}, False
                params = {"part": "contentDetails", "maxResults": BLOCK, "playlistId": uploads_playlist(ch)}
                report["full_reads"] += 1
                for pages in range(1, core.BASELINE_PAGES_MAX + 1):
                    token, oldest, _ = read_page(ch, inv, params, set())
                    if token == "error":
                        failed.add(ch)
                        break
                    if not token:
                        inv["ended"] = True
                        break
                    params = {**params, "pageToken": token}
                else:
                    inv["capped"] = True
                for v, x in inv["items"].items():
                    if v in kept and kept[v][1] is not None:
                        x[1] = kept[v][1]
                _prune(inv)
            verify(sorted(lost - failed))

        # 4. per measured video: verified, public, same format, views readable
        for m in measured:
            if m["channel_id"] in failed:
                continue
            cands = sorted((e, v) for e, v, f in window(m)
                           if f == m["format"] and run["views"].get(v) is not None)
            samples = [{"video_id": v, "published_at": _iso(e), "views": run["views"][v]}
                       for e, v in cands]
            results[m["video_id"]] = core.baseline_v2(samples, m["video_id"], m["published_at"])
    except QuotaStop as e:
        report["stop_reason"] = str(e)
        report["outcome"] = "partial"
        report["unresolved"] = sorted(m["video_id"] for m in measured)
        return {}, report
    finally:
        if changed:
            store.save({c: run["inv"][c] for c in changed if c not in failed})

    report["unresolved"] = sorted(m["video_id"] for m in measured if m["channel_id"] in failed)
    report["outcome"] = "ok" if not report["unresolved"] else "partial"
    return results, report
