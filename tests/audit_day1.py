"""T-17: the day-1 audit, every figure computed from production.

    python tests/audit_day1.py 2026-09-27 > docs/09-day1-audit.md

Read-only: the service key from backend/.env (never printed) and PostgREST.
Figures (08 T-17): quota_total; share of not_computable; 24-hour turnover of
videos and channels; distribution of age_at_first_obs_days; VPI distribution
by baseline band and format; rows written and bytes per row. Nothing
estimated: a figure the data cannot give is reported as missing.
"""

import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
BANDS = [(0, 100, "<100"), (100, 1_000, "100-1k"), (1_000, 10_000, "1k-10k"),
         (10_000, 100_000, "10k-100k"), (100_000, float("inf"), ">=100k")]


def env():
    out = {}
    for line in (ROOT / "backend" / ".env").read_text(encoding="utf-8").splitlines():
        k, _, v = line.strip().partition("=")
        out[k] = v.strip().strip('"')
    return out


E = env()
URL, HDR = E["SUPABASE_URL"], {"apikey": E["SUPABASE_SERVICE_KEY"],
                                "Authorization": f"Bearer {E['SUPABASE_SERVICE_KEY']}"}


def rows(table, params):
    out, off = [], 0
    while True:
        r = requests.get(f"{URL}/rest/v1/{table}", headers={**HDR, "Range": f"{off}-{off + 999}"},
                         params=params, timeout=120)
        r.raise_for_status()
        b = r.json()
        out += b
        if len(b) < 1000:
            return out
        off += 1000


def band(b):
    for lo, hi, name in BANDS:
        if lo <= b < hi:
            return name


def q(values, p):
    s = sorted(values)
    if not s:
        return None
    k = (len(s) - 1) * p
    f = int(k)
    return s[f] if f + 1 >= len(s) else s[f] + (s[f + 1] - s[f]) * (k - f)


def fmt(x, d=2):
    if isinstance(x, bool):
        return str(x).lower()
    return "—" if x is None else (f"{x:,.{d}f}" if isinstance(x, float) else f"{x:,}")


def main(day):
    prev = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    run = rows("ingest_run", {"day": f"eq.{day}", "select": "*"})[0]
    recs = rows("posts", {"entered_on": f"eq.{day}", "method_version": "eq.v2",
                          "select": "format,baseline_rule,baseline_score,vpi_ratio,age_at_first_obs_days,"
                                    "entry_certain,channel_id"})
    snap = rows("trend_snapshot", {"day": f"eq.{day}", "select": "video_id,channel_id,format"})
    snap_prev = rows("trend_snapshot", {"day": f"eq.{prev}", "select": "video_id,channel_id"})
    prev_v, prev_c = {r["video_id"] for r in snap_prev}, {r["channel_id"] for r in snap_prev}
    new = [r for r in snap if r["video_id"] not in prev_v]
    cur_c = {r["channel_id"] for r in snap}
    rules = Counter(r["baseline_rule"] for r in recs)
    ages = [r["age_at_first_obs_days"] for r in recs if r["age_at_first_obs_days"] is not None]
    by = defaultdict(list)
    for r in recs:
        if r["vpi_ratio"] is not None and r["baseline_score"] is not None:
            by[(r["format"], band(float(r["baseline_score"])))].append(float(r["vpi_ratio"]))
    size = requests.post(f"{URL}/rest/v1/rpc/audit_table_sizes", headers=HDR, json={}, timeout=60)
    sizes = size.json() if size.ok else None

    p = print
    p(f"# Day-1 audit — {day}\n")
    p(f"Computed by `tests/audit_day1.py {day}` from production (read-only). The reference day is "
      f"{prev}. Perimeter: long-form only (`01` §1).\n")
    p("## Run\n")
    p("| | |\n|---|---|")
    for k in ("outcome", "baselines_complete", "quota_total", "quota_charts", "quota_channels",
              "quota_playlists", "quota_playlist", "quota_videos", "slices_ok", "slices_404",
              "slices_error", "videos_seen", "channels_seen", "entries", "updated", "exits",
              "entering_channels", "entering_channels_in_inventory", "entering_long_channels",
              "entering_long_in_inventory", "started_at", "finished_at"):
        p(f"| `{k}` | {fmt(run.get(k)) if not isinstance(run.get(k), str) else run.get(k)} |")
    p(f"\nNotes: {run.get('notes')}\n")
    p("## Coverage\n")
    n = len(recs)
    p("| baseline_rule | records | share |\n|---|---|---|")
    for k, v in sorted(rules.items()):
        p(f"| `{k}` | {v:,} | {100 * v / n:.1f}% |")
    p(f"| total | {n:,} | |")
    p(f"\nShort records: {sum(r['format'] == 'SHORT' for r in recs)}; entries not certain: "
      f"{sum(not r['entry_certain'] for r in recs)}.\n")
    p("## 24-hour turnover\n")
    p("| | |\n|---|---|")
    p(f"| videos in the charts | {len(snap):,} |")
    p(f"| of which not in the reference day | {len(new):,} ({100 * len(new) / len(snap):.1f}%) |")
    p(f"| long-form among them | {sum(r['format'] == 'LONG' for r in new):,} |")
    p(f"| channels in the charts | {len(cur_c):,} |")
    p(f"| channels not in the reference day | {len(cur_c - prev_c):,} ({100 * len(cur_c - prev_c) / len(cur_c):.1f}%) |")
    p(f"| channels of the entries | {len({r['channel_id'] for r in new}):,} |")
    p("\n## Age at first observation (days), records of the day\n")
    p("| n | min | p10 | p25 | median | p75 | p90 | max |\n|---|---|---|---|---|---|---|---|")
    p(f"| {len(ages):,} | " + " | ".join(fmt(q(ages, x), 1) if ages else "—"
                                          for x in (0, .1, .25, .5, .75, .9, 1)) + " |")
    p("\n## VPI by baseline band and format (never pooled)\n")
    p("| format | band | n | p25 | median | p75 | p90 |\n|---|---|---|---|---|---|---|")
    for f in ("LONG", "SHORT"):
        for _, _, b in BANDS:
            v = by.get((f, b), [])
            if v:
                p(f"| {f} | {b} | {len(v):,} | {fmt(q(v, .25))} | {fmt(statistics.median(v))} | "
                  f"{fmt(q(v, .75))} | {fmt(q(v, .9))} |")
    p("\n## Storage\n")
    if sizes:
        p("| table | rows | bytes | bytes per row |\n|---|---|---|---|")
        for t in sizes:
            per = t["bytes"] / t["rows"] if t["rows"] else None
            p(f"| `{t['table']}` | {t['rows']:,} | {t['bytes']:,} | {fmt(per, 0)} |")
    else:
        p("Missing: `audit_table_sizes()` not reachable.")


if __name__ == "__main__":
    main(sys.argv[1])
