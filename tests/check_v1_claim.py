"""Production check that a v1 claim link still works (V1-SLIM, 28/09/2026).

    python tests/check_v1_claim.py iosa_LtdFPTUvgWIGxs0p   # exit 0 = PASS

Uses only the public key from backend/.env (never printed), as the claim page
does, and the public backend. PASS needs all of:
  - claim_record_v1(token) answers exactly one row, and its fields are the
    ones the claim page and the plaque read;
  - the archive cannot be listed with the public key (posts_v1 and
    posts_v1_links refuse a select, the archive bucket lists nothing);
  - the backend claim window for the token answers 200 with a start date;
  - the backend plaque for the token answers an image.
Prints the md5 of the row's fields, to compare before and after a change.
"""

import hashlib
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
BACKEND = "https://iosa-mvp-backend.onrender.com"
READ = ["id", "claim_token", "platform", "author_handle", "content_text", "engagement_score",
        "baseline_score", "vpi_ratio", "vpi_level_name", "vpi_max", "views_max", "days_charting",
        "created_at", "detected_at", "entered_on", "method_version"]


def env():
    out = {}
    for line in (ROOT / "backend" / ".env").read_text(encoding="utf-8").splitlines():
        k, _, v = line.strip().partition("=")
        out[k] = v.strip().strip('"')
    return out


def main(token):
    e = env()
    url, anon = e["SUPABASE_URL"].rstrip("/"), e["SUPABASE_KEY"]
    hdr = {"apikey": anon, "Authorization": f"Bearer {anon}"}
    rows = requests.post(f"{url}/rest/v1/rpc/claim_record_v1", headers=hdr,
                         json={"p_token": token}, timeout=60).json()
    row = rows[0] if isinstance(rows, list) and len(rows) == 1 else {}
    fields = {k: row.get(k) for k in READ}
    print("row md5 of the read fields:",
          hashlib.md5(json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest())
    listing = [requests.get(f"{url}/rest/v1/{t}", headers=hdr, params={"select": "*", "limit": "1"},
                            timeout=60) for t in ("posts_v1", "posts_v1_links")]
    bucket = requests.post(f"{url}/storage/v1/object/list/archivio", headers=hdr,
                           json={"prefix": "posts_v1", "limit": 10}, timeout=60)
    window = requests.get(f"{BACKEND}/api/claim/{token}/window", timeout=120)
    plaque = requests.get(f"{BACKEND}/api/trophy/preview", params={"claim_token": token},
                          timeout=180, allow_redirects=True)
    checks = [
        ("claim_record_v1 answers one row", isinstance(rows, list) and len(rows) == 1,
         len(rows) if isinstance(rows, list) else rows),
        ("the row carries every field the page and plaque read", set(READ) <= set(row), sorted(set(READ) - set(row))),
        ("the row carries no other field", set(row) <= set(READ), sorted(set(row) - set(READ))),
        ("posts_v1 not listable with the public key", listing[0].status_code in (401, 403), listing[0].status_code),
        ("posts_v1_links not listable with the public key", listing[1].status_code in (401, 403), listing[1].status_code),
        ("archive bucket lists nothing with the public key", bucket.status_code != 200 or bucket.json() == [],
         bucket.status_code),
        ("claim window 200 with a start", window.status_code == 200 and bool(window.json().get("start")),
         window.status_code),
        ("plaque answers an image", plaque.status_code == 200 and plaque.headers.get("content-type", "").startswith("image/"),
         f"{plaque.status_code} {plaque.headers.get('content-type')} {len(plaque.content)} bytes"),
    ]
    ok = True
    for name, passed, value in checks:
        ok &= bool(passed)
        print(f"{'PASS' if passed else 'FAIL'}  {name}  [{value}]")
    print("VERDICT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
