"""FIX-1a closing check (read-only, 0 YouTube units).

    python tests/check_plaques.py --token T1 T2 ... [--not-archived T] [--backend URL]

For every token: its plaque is in the archive (the CDN answers 200) and
/api/trophy/preview answers 307 to it in under 1 s. For --not-archived: the
endpoint answers 202 and the backend's resident memory (rss_kb on /) does not
grow by more than 20 MB across the request; before and after are printed.
Prints PASS or FAIL and exits 0 or 1.
"""
import argparse
import sys
import time

import requests

SUPABASE = "https://jodgdhkfkgvbyirvfcds.supabase.co"
BACKEND = "https://iosa-mvp-backend.onrender.com"
RSS_LIMIT_KB = 20 * 1024


def rss(backend):
    return requests.get(f"{backend}/", timeout=60).json().get("rss_kb")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", nargs="*", default=[])
    ap.add_argument("--not-archived", default=None)
    ap.add_argument("--backend", default=BACKEND)
    a = ap.parse_args(argv)
    b = a.backend.rstrip("/")
    fails = []
    requests.get(f"{b}/", timeout=120)                       # wake the free instance
    for t in a.token:
        t0 = time.monotonic()
        r = requests.get(f"{b}/api/trophy/preview", params={"claim_token": t},
                         allow_redirects=False, timeout=30)
        ms = (time.monotonic() - t0) * 1000
        loc = r.headers.get("location", "")
        cdn = requests.head(loc, timeout=30).status_code if loc else None
        ok = r.status_code == 307 and ms < 1000 and cdn == 200 and loc.startswith(SUPABASE)
        print(f"{'OK  ' if ok else 'FAIL'} {t}: {r.status_code} in {ms:.0f} ms, CDN {cdn}")
        if not ok:
            fails.append(t)
    if a.not_archived:
        before = rss(b)
        r = requests.get(f"{b}/api/trophy/preview", params={"claim_token": a.not_archived},
                         allow_redirects=False, timeout=60)
        time.sleep(2)
        after = rss(b)
        grew = (after - before) if (before is not None and after is not None) else None
        ok = r.status_code == 202 and grew is not None and grew < RSS_LIMIT_KB
        print(f"{'OK  ' if ok else 'FAIL'} not archived {a.not_archived}: {r.status_code} "
              f"{r.text[:40]!r}, RSS {before} -> {after} kB")
        if not ok:
            fails.append(a.not_archived)
    print("PASS" if not fails else f"FAIL ({len(fails)})")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
