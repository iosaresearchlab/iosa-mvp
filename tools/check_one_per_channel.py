"""SOC-2 one-off: does a Most Popular category chart list more than one video
of the same channel? Read raw from the API, slice by slice.

    python tools/check_one_per_channel.py [out.json]

Reads the 30 slices below live (videos.list chart=mostPopular, part=snippet,
maxResults=50, every page via nextPageToken) and reports, per slice, the
items returned, the distinct channels and the channels holding two or more
videos (with their ids), counted on the raw response: no deduplication, no
filter. 25 non-music slices spread across the 11 non-music categories that
return data and across countries (the largest slices of each category on
08/10 among them), plus 5 music slices (category 10) as the control.

Quota: 1 unit per page, at most 4 pages per slice (200 items): at most 120
units, the owner's ceiling for this run (10/10/2026). Every call is marked on
a QuotaCounter(120) before it is sent (backend/quota.py), so the brake
refuses the call that would cross it. Run it outside the nightly reading and
its retries (pg_cron 23:59, 00:30, 06:00, 08:20 UTC). The units spent are
printed and go into quota_ledger as 'measurement'.

Needs YOUTUBE_API_KEY (backend/.env, CRLF tolerated). Standard library only.
"""

import importlib.util
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("quota", ROOT / "backend" / "quota.py")
quota_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(quota_mod)

API_URL = "https://www.googleapis.com/youtube/v3/videos"
UNITS_MAX = 120
MUSIC = "10"
NON_MUSIC = [
    ("JP", "1"), ("US", "1"), ("IT", "1"),
    ("KR", "2"), ("DE", "2"),
    ("ID", "15"), ("GB", "15"),
    ("US", "17"), ("TR", "17"), ("BR", "17"),
    ("FR", "20"), ("IN", "20"), ("JP", "20"),
    ("ES", "22"), ("US", "22"),
    ("TH", "23"), ("IT", "23"),
    ("PL", "24"), ("GB", "24"), ("MX", "24"),
    ("ID", "25"), ("US", "25"),
    ("IN", "26"), ("KR", "26"),
    ("VN", "28"),
]
MUSIC_SLICES = [("US", MUSIC), ("JP", MUSIC), ("IN", MUSIC), ("BR", MUSIC), ("KR", MUSIC)]
SLICES = NON_MUSIC + MUSIC_SLICES


def env_key():
    if os.environ.get("YOUTUBE_API_KEY"):
        return os.environ["YOUTUBE_API_KEY"]
    for line in open(ROOT / "backend" / ".env", encoding="utf-8"):
        line = line.strip().replace("\r", "")
        if line.startswith("YOUTUBE_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("YOUTUBE_API_KEY not found")


def read_slice(key, quota, country, category):
    """(status, items): status 'ok', '404', 'error: ...' or 'braked'."""
    params = {"part": "snippet", "chart": "mostPopular", "maxResults": 50,
              "regionCode": country, "videoCategoryId": category, "key": key}
    items, pages = [], 0
    while True:
        try:
            quota.mark("charts")
        except quota_mod.QuotaExhausted:
            return "braked", items, pages
        pages += 1
        url = f"{API_URL}?{urllib.parse.urlencode(params)}"
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                payload = json.load(r)
        except urllib.error.HTTPError as e:
            return ("404" if e.code == 404 else f"error: HTTP {e.code}"), items, pages
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            return f"error: {e}", items, pages
        items.extend(payload.get("items", []))
        token = payload.get("nextPageToken")
        if not token:
            return "ok", items, pages
        params = {**params, "pageToken": token}


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    key = env_key()
    quota = quota_mod.QuotaCounter(UNITS_MAX)
    started = datetime.now(timezone.utc)
    rows = []
    for country, category in SLICES:
        status, items, pages = read_slice(key, quota, country, category)
        by_channel = defaultdict(list)
        for it in items:
            by_channel[(it.get("snippet") or {}).get("channelId")].append(it.get("id"))
        multi = {ch: ids for ch, ids in by_channel.items() if len(ids) >= 2}
        rows.append({"slice": f"{country}:{category}", "music": category == MUSIC, "status": status,
                     "pages": pages, "items": len(items), "distinct_ids": len({it.get("id") for it in items}),
                     "channels": len(by_channel), "channels_2plus": len(multi),
                     "multi": {ch: ids for ch, ids in sorted(multi.items())}})
        if status == "braked":
            break
        time.sleep(0.2)
    finished = datetime.now(timezone.utc)

    def total(music):
        sel = [r for r in rows if r["music"] == music and r["status"] == "ok"]
        return {"slices": len(sel), "items": sum(r["items"] for r in sel),
                "channel_slice_pairs": sum(r["channels"] for r in sel),
                "with_2plus": sum(r["channels_2plus"] for r in sel),
                "slices_with_2plus": sum(1 for r in sel if r["channels_2plus"])}

    report = {"started": started.isoformat(timespec="seconds"), "finished": finished.isoformat(timespec="seconds"),
              "units": quota.total, "units_max": UNITS_MAX,
              "non_music": total(False), "music": total(True),
              "not_ok": [r["slice"] + " " + r["status"] for r in rows if r["status"] != "ok"],
              "slices": rows}
    for r in rows:
        print(f"{r['slice']:7s} {r['status']:6s} pages {r['pages']} items {r['items']:3d} "
              f"channels {r['channels']:3d} with>=2 {r['channels_2plus']}")
    print("non-music:", report["non_music"])
    print("music:    ", report["music"])
    print("not ok:", report["not_ok"], "| units:", quota.total)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print("written", out)


if __name__ == "__main__":
    main()
