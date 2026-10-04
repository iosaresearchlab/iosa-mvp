"""Measure whether the player's embed size tells vertical from horizontal,
and how many chart entries the duration-only rule puts in the wrong format.

Read-only. Cost: one videos.list call per 50 ids (1 unit each), printed
with the sample size. Run on 04/10/2026: 22 units (docs/03 section 11).

    python tests/measure_shape.py 2026-10-03 [n_short] [n_long]

Population: the day's entries (in the day's trend_snapshot, absent from the
previous day's), split by the format the duration-only rule stored. Sample:
the first n of each format ordered by md5(video_id || 's'), the same order
as the SQL used to cross-check it. For each video: duration, embed width and
height (part=player with maxHeight), and whether it was a live broadcast
(liveStreamingDetails.actualStartTime). Writes the CSV to 'Claude outputs/'
(the 04/10 run is kept as docs/shape-2026-10-03.csv) and prints the summary.
"""

import csv
import hashlib
import os
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from vpi_core import parse_iso_duration  # noqa: E402
API = "https://www.googleapis.com/youtube/v3/videos"
MAX_HEIGHT = 1000
SHORTS_3MIN_FROM = "2024-10-15"     # YouTube Help 15424877


def env():
    out = {}
    for line in (ROOT / "backend" / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip().rstrip("\r")
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def snapshot(e, day):
    url = f"{e['SUPABASE_URL']}/rest/v1/trend_snapshot"
    key = e.get("SUPABASE_SERVICE_KEY") or e["SUPABASE_KEY"]
    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    rows, start = {}, 0
    while True:
        for attempt in range(5):
            try:
                r = requests.get(url, headers=h, timeout=30, params={
                    "select": "video_id,format", "day": f"eq.{day}", "order": "video_id",
                    "limit": 1000, "offset": start})
                r.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 4:
                    raise
        page = r.json()
        rows.update({x["video_id"]: x["format"] for x in page})
        if len(page) < 1000:
            return rows
        start += 1000


def order_key(vid):
    return hashlib.md5((vid + "s").encode()).hexdigest()


def shape(w, h):
    if not w or not h:
        return "unknown"
    r = w / h
    if r < 0.99:
        return "vertical"
    if r <= 1.01:
        return "square"
    return "horizontal"


def main():
    day = sys.argv[1]
    n_short = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    n_long = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    e = env()
    prev = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    today, yesterday = snapshot(e, day), snapshot(e, prev)
    entries = {v: f for v, f in today.items() if v not in yesterday}
    sample = []
    for fmt, n in (("SHORT", n_short), ("LONG", n_long)):
        ids = sorted((v for v, f in entries.items() if f == fmt), key=order_key)[:n]
        sample += [(v, fmt) for v in ids]
    calls = -(-len(sample) // 50)
    print(f"entries {day}: {Counter(entries.values())}; sample {len(sample)}; "
          f"cost {calls} units")

    rows = []
    for i in range(0, len(sample), 50):
        block = dict(sample[i:i + 50])
        r = requests.get(API, timeout=30, params={
            "part": "snippet,contentDetails,player,liveStreamingDetails",
            "id": ",".join(block), "maxHeight": MAX_HEIGHT, "key": e["YOUTUBE_API_KEY"]})
        r.raise_for_status()
        for it in r.json().get("items", []):
            dur = it["contentDetails"].get("duration", "")
            p = it.get("player", {})
            rows.append({
                "video_id": it["id"], "stored_format": block[it["id"]],
                "seconds": parse_iso_duration(dur),
                "published_at": it["snippet"]["publishedAt"],
                "embed_w": p.get("embedWidth"), "embed_h": p.get("embedHeight"),
                "shape": shape(int(p.get("embedWidth") or 0), int(p.get("embedHeight") or 0)),
                "live": bool((it.get("liveStreamingDetails") or {}).get("actualStartTime")),
                "title": it["snippet"]["title"][:80],
            })

    out = ROOT / "Claude outputs" / f"shape_{day}.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    for fmt in ("SHORT", "LONG"):
        rs = [r for r in rows if r["stored_format"] == fmt]
        print(f"\n{fmt} (stored by duration): {len(rs)} returned")
        print("  shape:", dict(Counter(r["shape"] for r in rs)))
        print("  live:", sum(r["live"] for r in rs))
        print("  embed w x h, top:",
              Counter(f"{r['embed_w']}x{r['embed_h']}" for r in rs).most_common(8))
        if fmt == "SHORT":
            hor = [r for r in rs if r["shape"] == "horizontal"]
            old = [r for r in rs if r["published_at"] < SHORTS_3MIN_FROM]
            print("  horizontal <=180s (long-form for YouTube):", len(hor))
            print("  published before 2024-10-15:", len(old),
                  "of which >60s:", sum(r["seconds"] > 60 for r in old))
            print("  durations of horizontal ones:",
                  sorted(r["seconds"] for r in hor)[:15], "...")
    print(f"\nCSV: {out}")


if __name__ == "__main__":
    main()
