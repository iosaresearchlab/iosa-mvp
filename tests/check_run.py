"""The nightly check, for any day: the criteria of tests/check_run.sql.

    python tests/check_run.py              # the UTC day that has just closed
    python tests/check_run.py 2026-09-30   # exit 0 = PASS, 1 = FAIL

tests/check_run.sql is the query the scheduled task "IOSA check_run
notturno" runs at 02:07 UTC; this script applies the same criteria, reading
production through the REST API with the service key from backend/.env
(never printed). tests/test_check_run.py runs both on the same fixtures and
holds them to the same verdicts.

A quota_stop is expected (owner decision 01/10/2026), and the day can PASS,
when the census is complete, the run notes carry Google's 403, and the units
of the previous day's morning reprocess that fell in the same Pacific quota
day plus this run's quota_total reach 9,000. FAIL only on: a quota_stop not
expected, the previous day still waiting, read_failed > 0, an incomplete
census or a failed run, malformed records, a Short record, the retention not
run clean, the database or Storage over its threshold (header of
tests/check_run.sql). Records written as quota_stop or read_failed have no
VPI and are well-formed.

Run it before the 08:20 UTC morning pass to see what the 02:07 check saw:
afterwards the pass has completed the day's quota_stop records and added
its own units to the run's quota_total.
"""

import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
PACIFIC = ZoneInfo("America/Los_Angeles")
QUOTA_BRAKE = 9_900            # backend/quota.py QUOTA_HARD_MAX
QUOTA_DAY_EXHAUSTED = 9_000    # owner decision 01/10/2026
DB_LIMIT = 400 * 1024 * 1024   # of the 500 MB free tier
STORAGE_LIMIT = 800 * 1024 * 1024
WINDOW_DAYS = 7                # backend/retention.py WINDOW_DAYS
GOOGLE_403 = "baselines stopped: 403 on "
PASS_UNITS = re.compile(r".*[^0-9]([0-9]+) units in this pass", re.S)
WAITING = ("quota_stop", "read_failed")


def _ts(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None


def pass_units_same_quota_day(run, prev_run):
    """Units of the previous day's morning reprocess spent in the Pacific
    quota day of this run's reading; 0 when there is none."""
    if not run or not prev_run or not prev_run.get("reprocessed_at"):
        return 0
    if _ts(prev_run["reprocessed_at"]).astimezone(PACIFIC).date() != \
            _ts(run["started_at"]).astimezone(PACIFIC).date():
        return 0
    m = PASS_UNITS.match(prev_run.get("notes") or "")
    return int(m.group(1)) if m else 0


def well_formed(rec):
    if rec["baseline_rule"] == "standard":
        return rec["baseline_score"] is not None and rec["vpi_ratio"] is not None
    return rec["baseline_rule"] in ("not_computable",) + WAITING and rec["vpi_ratio"] is None


def facts(runs, prev_run, records, previous_day_still_waiting, stale_snapshot_days,
          db_bytes, storage_bytes):
    """The columns tests/check_run.sql computes, from the rows it reads."""
    run = runs[0] if len(runs) == 1 else None
    notes = (run or {}).get("notes") or ""
    rules = [r["baseline_rule"] for r in records]
    return {
        "runs": len(runs),
        "quota_total": (run or {}).get("quota_total"),
        "outcome": (run or {}).get("outcome"),
        "slices_error": (run or {}).get("slices_error"),
        "finished": bool(run and run.get("finished_at")),
        "records": len(records),
        "quota_stop": rules.count("quota_stop"),
        "read_failed": rules.count("read_failed"),
        "waiting_for_reprocess": sum(r in WAITING for r in rules),
        "census_complete": (run or {}).get("census_complete"),
        "stopped_by_google_403": GOOGLE_403 in notes,
        "same_quota_day_pass_units": pass_units_same_quota_day(run, prev_run),
        "previous_day_still_waiting": previous_day_still_waiting,
        "bad_records": sum(not well_formed(r) for r in records),
        "shorts": sum(r["format"] == "SHORT" for r in records),
        "units_in_notes": "per channel" in notes,
        "retention_ran": "retention: kept from" in notes,
        "retention_failed": "RETENTION FAILED" in notes,
        "stale_snapshot_days": stale_snapshot_days,
        "storage_bytes": storage_bytes,
        "db_bytes": db_bytes,
    }


def evaluate(f):
    """(verdict, quota_stop_expected, failed conditions) for one day."""
    expected = bool(f["quota_stop"] > 0 and f["census_complete"] and f["stopped_by_google_403"]
                    and f["same_quota_day_pass_units"] + (f["quota_total"] or 0) >= QUOTA_DAY_EXHAUSTED)
    checks = [
        ("one run", f["runs"] == 1),
        ("run finished", f["finished"]),
        ("quota_total <= 9900", f["quota_total"] is not None and f["quota_total"] <= QUOTA_BRAKE),
        ("outcome ok", f["outcome"] == "ok"),
        ("census complete", f["census_complete"] is True),
        ("slices_error = 0", f["slices_error"] == 0),
        ("records exist", f["records"] > 0),
        ("read_failed = 0", f["read_failed"] == 0),
        ("quota_stop = 0 or expected", f["quota_stop"] == 0 or expected),
        ("previous day not waiting", f["previous_day_still_waiting"] == 0),
        ("bad_records = 0", f["bad_records"] == 0),
        ("no Short record", f["shorts"] == 0),
        ("units per channel in the notes", f["units_in_notes"]),
        ("retention ran", f["retention_ran"]),
        ("no retention failure", not f["retention_failed"]),
        ("no snapshot day past the window", f["stale_snapshot_days"] == 0),
        ("database < 400 MB", f["db_bytes"] < DB_LIMIT),
        ("Storage < 800 MB", f["storage_bytes"] < STORAGE_LIMIT),
    ]
    failed = [name for name, ok in checks if not ok]
    return ("FAIL" if failed else "PASS"), expected, failed


# --- production, through the REST API -----------------------------------------


def env():
    out = {}
    for line in (ROOT / "backend" / ".env").read_text(encoding="utf-8").splitlines():
        k, _, v = line.strip().partition("=")
        out[k] = v.strip().strip('"')
    return out


def read_production(day):
    import requests

    e = env()
    url, svc = e["SUPABASE_URL"], e["SUPABASE_SERVICE_KEY"]
    hdr = {"apikey": svc, "Authorization": f"Bearer {svc}"}

    def get(path, params, extra=None):
        r = requests.get(f"{url}/rest/v1/{path}", headers={**hdr, **(extra or {})},
                         params=params, timeout=60)
        r.raise_for_status()
        return r

    def rpc(fn, body):
        r = requests.post(f"{url}/rest/v1/rpc/{fn}", headers=hdr, json=body, timeout=60)
        r.raise_for_status()
        return r.json()

    prev = day - timedelta(days=1)
    runs = get("ingest_run", {"day": f"eq.{day}", "select": "*"}).json()
    prev_runs = get("ingest_run", {"day": f"eq.{prev}", "select": "*"}).json()
    records, off = [], 0
    while True:
        b = get("posts", {"entered_on": f"eq.{day}", "method_version": "eq.v2",
                          "select": "format,baseline_rule,baseline_score,vpi_ratio"},
                {"Range": f"{off}-{off + 999}"}).json()
        records += b
        if len(b) < 1000:
            break
        off += 1000
    waiting = get("posts", {"entered_on": f"eq.{prev}", "method_version": "eq.v2",
                            "baseline_rule": f"in.({','.join(WAITING)})", "select": "id"},
                  {"Prefer": "count=exact", "Range": "0-0"})
    previous_day_still_waiting = int(waiting.headers.get("content-range", "*/0").split("/")[-1])
    stale = rpc("snapshot_days_before", {"p_day": str(day - timedelta(days=WINDOW_DAYS - 1))})
    sizes = rpc("check_run_sizes", {})
    sizes = sizes[0] if isinstance(sizes, list) else sizes
    return facts(runs, prev_runs[0] if prev_runs else None, records, previous_day_still_waiting,
                 len(stale), int(sizes["db_bytes"]), int(sizes["storage_bytes"])), runs


def main(argv):
    day = (date.fromisoformat(argv[1]) if len(argv) > 1
           else datetime.now(timezone.utc).date() - timedelta(days=1))
    f, runs = read_production(day)
    verdict, expected, failed = evaluate(f)
    print(f"day {day}")
    for k, v in f.items():
        print(f"  {k}: {v}")
    print(f"  quota_stop_expected: {expected}")
    if runs:
        print(f"notes: {runs[0].get('notes')}")
    for name in failed:
        print(f"FAIL  {name}")
    print("VERDICT:", verdict)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
