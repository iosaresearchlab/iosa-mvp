"""Closing check of the 27/09/2026 perimeter change, on a real run.

    python tests/check_run.py 2026-09-27      # exit 0 = PASS, 1 = FAIL

Reads production with the service key from backend/.env (never printed).
PASS needs all of: quota_total <= 9,500, census complete (outcome 'ok',
slices_error = 0); zero quota_stop records; every entering record long-form
with either a baseline and a VPI or baseline_rule 'not_computable'; no Short
record created; units per channel in the run notes.
"""

import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent


def env():
    out = {}
    for line in (ROOT / "backend" / ".env").read_text(encoding="utf-8").splitlines():
        k, _, v = line.strip().partition("=")
        out[k] = v.strip().strip('"')
    return out


def main(day):
    e = env()
    url, svc = e["SUPABASE_URL"], e["SUPABASE_SERVICE_KEY"]
    hdr = {"apikey": svc, "Authorization": f"Bearer {svc}"}
    run = requests.get(f"{url}/rest/v1/ingest_run", headers=hdr, params={"day": f"eq.{day}", "select": "*"},
                       timeout=60).json()
    if not run:
        print(f"FAIL: no ingest_run for {day}")
        return 1
    r = run[0]
    recs, off = [], 0
    while True:
        b = requests.get(f"{url}/rest/v1/posts", headers={**hdr, "Range": f"{off}-{off + 999}"},
                         params={"entered_on": f"eq.{day}", "method_version": "eq.v2",
                                 "select": "format,baseline_rule,baseline_score,vpi_ratio"}, timeout=60).json()
        recs += b
        if len(b) < 1000:
            break
        off += 1000
    checks = [
        ("quota_total <= 9500", (r["quota_total"] or 0) <= 9500, r["quota_total"]),
        ("census complete: outcome ok", r["outcome"] == "ok", r["outcome"]),
        ("slices_error = 0", r["slices_error"] == 0, r["slices_error"]),
        ("zero quota_stop records", not any(x["baseline_rule"] == "quota_stop" for x in recs),
         sum(x["baseline_rule"] == "quota_stop" for x in recs)),
        ("every record: baseline + VPI, or not_computable",
         all((x["baseline_rule"] == "standard" and x["baseline_score"] is not None and x["vpi_ratio"] is not None)
             or (x["baseline_rule"] == "not_computable" and x["vpi_ratio"] is None) for x in recs),
         {k: sum(x["baseline_rule"] == k for x in recs) for k in ("standard", "not_computable", "quota_stop",
                                                                  "read_failed")}),
        ("no Short record created", not any(x["format"] == "SHORT" for x in recs),
         sum(x["format"] == "SHORT" for x in recs)),
        ("records exist", len(recs) > 0, len(recs)),
        ("units per channel in the notes", "per channel" in (r["notes"] or ""), None),
    ]
    ok = True
    for name, passed, value in checks:
        ok &= bool(passed)
        print(f"{'PASS' if passed else 'FAIL'}  {name}" + (f"  [{value}]" if value is not None else ""))
    print(f"notes: {r['notes']}")
    print("VERDICT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
