"""SEO-1 closing check (read-only): every URL of the sitemap answers 200 and
names itself as canonical; a paginated home names the home.

    python tests/check_seo.py [base] [--shard k/n]   # base: https://iosaresearch.org

--shard k/n checks only every n-th URL starting at the k-th (1-based), and
/?page=2 in shard 1: the n shards together are the whole check, for a shell
that cuts a call at 3 minutes.

Requests every <loc> of <base>/sitemap.xml, at most 8 at a time, retrying
once, after 3 s, on a timeout or a connection error
(TLS included). Prints OK and exits 0, or lists every
failure and exits 1. No YouTube quota: only the site is requested.
"""

import html
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

_ARGS = [a for a in sys.argv[1:] if not a.startswith("--shard")]
_SHARD = next((a.split("=", 1)[-1] if "=" in a else sys.argv[sys.argv.index(a) + 1]
               for a in sys.argv[1:] if a.startswith("--shard")), "1/1")
_ARGS = [a for a in _ARGS if a != _SHARD]
BASE = (_ARGS[0] if _ARGS else "https://iosaresearch.org").rstrip("/")
SHARD_K, SHARD_N = (int(x) for x in _SHARD.split("/"))
PARALLEL = 8
TIMEOUT = 30
RETRY_PAUSE = 3      # seconds before the one retry
UA = "IOSA-check-seo/1 (+https://iosaresearch.org)"

_LINK = re.compile(r"<link\b[^>]*>", re.I)
_REL = re.compile(r"""\brel\s*=\s*["']?canonical["'\s/>]""", re.I)
_HREF = re.compile(r"""\bhref\s*=\s*["']([^"']+)["']""", re.I)


def fetch(url):
    """(status, body) with one retry on a timeout or a connection error."""
    for attempt in (1, 2):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, ""
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            if attempt == 2:
                return f"error: {e}", ""
            time.sleep(RETRY_PAUSE)
    return "unreachable", ""


def canonicals(body):
    out = []
    for tag in _LINK.findall(body):
        if _REL.search(tag):
            m = _HREF.search(tag)
            if m:
                out.append(html.unescape(m.group(1)))
    return out


def same(a, b):
    """Equal URLs. An empty path is the path "/" (RFC 3986 6.2.3): Next renders
    the home's canonical as https://iosaresearch.org, the sitemap lists
    https://iosaresearch.org/, and they are one URL. Nothing else is
    normalised: a query string or a different path is a different URL."""
    def norm(u):
        p = urllib.parse.urlsplit(u)
        return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path or "/", p.query, p.fragment))
    return norm(a) == norm(b)


def check(url, expected=None):
    status, body = fetch(url)
    if status != 200:
        return f"{url}: status {status}"
    found = canonicals(body)
    want = expected or url
    if len(found) != 1 or not same(found[0], want):
        return f"{url}: canonical {found or 'missing'}, expected {want}"
    return None


def main():
    status, xml = fetch(f"{BASE}/sitemap.xml")
    if status != 200:
        print(f"FAIL: sitemap.xml status {status}")
        return 1
    urls = [html.unescape(u.strip()) for u in re.findall(r"<loc>(.*?)</loc>", xml, re.S)]
    if not urls:
        print("FAIL: no <loc> in sitemap.xml")
        return 1
    jobs = [(u, None) for u in urls[SHARD_K - 1::SHARD_N]]
    if SHARD_K == 1:
        jobs.append((f"{BASE}/?page=2", f"{BASE}/"))
    with ThreadPoolExecutor(PARALLEL) as pool:
        failures = [f for f in pool.map(lambda j: check(*j), jobs) if f]
    print(f"shard {SHARD_K}/{SHARD_N}: {len(jobs)} of {len(urls)} sitemap URLs"
          f"{' + /?page=2' if SHARD_K == 1 else ''} checked")
    if failures:
        for f in failures:
            print("FAIL:", f)
        print(f"{len(failures)} failures")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
