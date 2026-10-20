"""FIX-1a closing check (read-only, 0 YouTube units).

    python tests/check_plaques.py [--needed] [--token T1 T2 ...] [--not-archived T] [--backend URL]

--needed adds every token of plaques_needed() (needs SUPABASE_URL and
SUPABASE_SERVICE_KEY in the environment). For every token: its plaque is in
the archive (the CDN answers 200), /api/trophy/preview answers 307 to it in
under 1 s, and /api/trophy/live answers its HTML in under 1 s; a record still charting
or without a VPI is refused by both (409/404), which is correct. For --not-archived: the
endpoint answers 202 and the backend's resident memory (rss_kb on /) does not
grow by more than 20 MB across the request; before and after are printed.
Prints PASS or FAIL and exits 0 or 1.
"""
import argparse
import os
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
    ap.add_argument("--needed", action="store_true")
    ap.add_argument("--not-archived", default=None)
    ap.add_argument("--backend", default=BACKEND)
    a = ap.parse_args(argv)
    b = a.backend.rstrip("/")
    fails = []
    requests.get(f"{b}/", timeout=120)                       # wake the free instance
    tokens = list(a.token)
    if a.needed:
        url, key = os.environ["SUPABASE_URL"].strip().rstrip("/"), os.environ["SUPABASE_SERVICE_KEY"].strip()
        rows = requests.post(f"{url}/rest/v1/rpc/plaques_needed", json={}, timeout=60,
                             headers={"apikey": key, "Authorization": f"Bearer {key}"}).json()
        tokens += [r if isinstance(r, str) else next(iter(r.values())) for r in rows]
        print(f"plaques_needed(): {len(rows)} tokens")
    for t in tokens:
        t0 = time.monotonic()
        r = requests.get(f"{b}/api/trophy/preview", params={"claim_token": t},
                         allow_redirects=False, timeout=30)
        ms = (time.monotonic() - t0) * 1000
        loc = r.headers.get("location", "")
        cdn = requests.head(loc, timeout=30).status_code if loc else None
        t1 = time.monotonic()
        live = requests.get(f"{b}/api/trophy/live", params={"claim_token": t}, timeout=30)
        live_ms = (time.monotonic() - t1) * 1000
        live_ok = live.status_code == 200 and "<html" in live.json().get("html", "") and live_ms < 1000
        ok = r.status_code == 307 and ms < 1000 and cdn == 200 and loc.startswith(SUPABASE) and live_ok
        # A record still charting (409) or without a VPI (404) has no plaque by design: both
        # endpoints refuse it, quickly, and nothing is rendered.
        refused = r.status_code in (404, 409) and live.status_code == r.status_code and ms < 1000
        print(f"{'OK  ' if ok or refused else 'FAIL'} {t}: preview {r.status_code} in {ms:.0f} ms, CDN {cdn}; "
              f"live {live.status_code} in {live_ms:.0f} ms{' (no plaque by design)' if refused else ''}")
        ok = ok or refused
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
