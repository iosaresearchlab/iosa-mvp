"""FMT-1, step 3 of the closing check (08 FMT-1): the records of the first
reading under the new Short rule, read-only, 0 YouTube units.

    python tests/check_fmt1.py 2026-10-04     # exit 0 = PASS, 1 = FAIL

Run with tests/check_run.py <day>, which gives the day's general verdict.
Reads production through the REST API with the service key from
backend/.env (never printed), like check_run.py. Checks, among the day's v2
records (01 section 1.1, 02 section 4.9):

  - every one has format_rule = 'youtube_shape' and a non-null duration_s;
  - every one of 180 s or less has a non-null shape;
  - at least one long-form record has duration_s <= 180 and shape = 'wide';
  - none has duration_s <= 180 with a shape other than 'wide', unless it was
    published before 15/10/2024 and is over 60 s.

Reports discards.unknown_shape and quota_total (and the previous night's,
for the comparison with the estimate of 02 section 4.9).
"""

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.check_run import env  # noqa: E402

SHORT_MAX = 180
SHORT_MAX_BEFORE = 60
SHORT_3MIN_FROM = "2024-10-15"


def _pub_day(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc).date().isoformat()


def evaluate(records):
    """(verdict, failed conditions, counts) for one day's v2 records."""
    short_dur = [r for r in records if r["duration_s"] is not None and r["duration_s"] <= SHORT_MAX]
    wide_short_dur = [r for r in short_dur if r["format"] == "LONG" and r["shape"] == "wide"]
    not_wide = [r for r in short_dur if r["shape"] != "wide"
                and not (r["created_at"] and _pub_day(r["created_at"]) < SHORT_3MIN_FROM
                         and r["duration_s"] > SHORT_MAX_BEFORE)]
    counts = {
        "records": len(records),
        "format_rule_not_youtube_shape": sum(r["format_rule"] != "youtube_shape" for r in records),
        "duration_s_null": sum(r["duration_s"] is None for r in records),
        "up_to_180_without_shape": sum(r["shape"] is None for r in short_dur),
        "long_up_to_180_wide": len(wide_short_dur),
        "up_to_180_not_wide_not_old_rule": len(not_wide),
        "shorts": sum(r["format"] != "LONG" for r in records),
    }
    checks = [
        ("records exist", counts["records"] > 0),
        ("every record format_rule = youtube_shape", counts["format_rule_not_youtube_shape"] == 0),
        ("every record has duration_s", counts["duration_s_null"] == 0),
        ("every record <= 180 s has a shape", counts["up_to_180_without_shape"] == 0),
        ("at least one long-form <= 180 s and wide", counts["long_up_to_180_wide"] > 0),
        ("none <= 180 s not wide, except before 15/10/2024 and over 60 s",
         counts["up_to_180_not_wide_not_old_rule"] == 0),
        ("no record other than long-form", counts["shorts"] == 0),
    ]
    failed = [name for name, ok in checks if not ok]
    return ("FAIL" if failed else "PASS"), failed, counts


def read_production(day):
    import requests

    e = env()
    url, svc = e["SUPABASE_URL"], e["SUPABASE_SERVICE_KEY"]
    hdr = {"apikey": svc, "Authorization": f"Bearer {svc}"}

    def get(path, params, extra=None):
        r = requests.get(f"{url}/rest/v1/{path}", headers={**hdr, **(extra or {})},
                         params=params, timeout=60)
        r.raise_for_status()
        return r.json()

    records, off = [], 0
    while True:
        b = get("posts", {"entered_on": f"eq.{day}", "method_version": "eq.v2",
                          "select": "format,duration_s,shape,was_live,format_rule,created_at"},
                {"Range": f"{off}-{off + 999}"})
        records += b
        if len(b) < 1000:
            break
        off += 1000
    runs = {r["day"][:10]: r for r in get("ingest_run", {
        "day": f"in.({day - timedelta(days=1)},{day})",
        "select": "day,quota_total,discards,entries,outcome"})}
    return records, runs


def main(argv):
    day = (date.fromisoformat(argv[1]) if len(argv) > 1
           else datetime.now(timezone.utc).date() - timedelta(days=1))
    records, runs = read_production(day)
    verdict, failed, counts = evaluate(records)
    run, prev = runs.get(str(day)) or {}, runs.get(str(day - timedelta(days=1))) or {}
    print(f"day {day}")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    print(f"  was_live: {sum(bool(r['was_live']) for r in records)}")
    print(f"  discards.unknown_shape: {(run.get('discards') or {}).get('unknown_shape')}")
    print(f"  quota_total: {run.get('quota_total')} (previous night {prev.get('quota_total')})")
    for name in failed:
        print(f"FAIL  {name}")
    print("VERDICT:", verdict)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
