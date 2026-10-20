"""FIX-1d closing check (read-only): a claim link previews as its record.

    python tests/check_og.py [--base https://iosaresearch.org] TOKEN [TOKEN ...]
    python tests/check_og.py --creator HANDLE ...      # creator pages too

For each claim token: the page's og:image and twitter:image point to that
record's own image (/claim/<token>/opengraph-image, /twitter-image), and the
image answers 200, image/png, Cache-Control "public, max-age=86400,
immutable", in under 1.5 s on a miss (a query string no cache has seen).
robots.txt lets Twitterbot read /claim/ (it obeys robots.txt: without that X
shows no card). Prints one line per URL, then PASS or FAIL; exit 1 on FAIL.
No YouTube quota: only the site is requested.
"""
import re
import sys
import time
import uuid
import urllib.request

LIMIT_S = 1.5
CACHE = "public, max-age=86400, immutable"
UA = "IOSA-check-og/1 (+https://iosaresearch.org)"


def _get(url, ua=UA):
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
        return r.status, dict(r.headers), body, time.perf_counter() - t0


def _meta(html, attr, name):
    m = re.search(rf'<meta {attr}="{re.escape(name)}" content="([^"]+)"', html)
    return m.group(1) if m else None


def twitterbot_may_read_claims(robots):
    """True when the Twitterbot group of robots.txt allows /claim/."""
    groups = re.split(r"\n\s*\n", robots.strip())
    for g in groups:
        agents = [a.strip().lower() for a in re.findall(r"(?im)^user-agent:\s*(.+)$", g)]
        if "twitterbot" in agents:
            return not re.search(r"(?im)^disallow:\s*/claim/", g)
    return False


def check_page(base, path, own):
    """Failures for one page whose images must live under `own`."""
    fails = []
    status, _, body, _ = _get(base + path, ua="Twitterbot/1.0")
    html = body.decode("utf-8", "replace")
    for attr, name, kind in (("property", "og:image", "opengraph-image"),
                             ("name", "twitter:image", "twitter-image")):
        url = _meta(html, attr, name)
        if not url or f"{own}/{kind}" not in url:
            fails.append(f"{path}: {name} = {url}")
            continue
        img = re.sub(r"^https?://[^/]+", base, url)
        img += ("&" if "?" in img else "?") + "miss=" + uuid.uuid4().hex[:8]
        st, headers, data, secs = _get(img)
        ctype = headers.get("Content-Type", headers.get("content-type", ""))
        cache = headers.get("Cache-Control", headers.get("cache-control", ""))
        ok = st == 200 and ctype.startswith("image/png") and cache == CACHE and secs < LIMIT_S \
            and data[:8] == b"\x89PNG\r\n\x1a\n"
        print(f"{'OK  ' if ok else 'FAIL'} {name} {path} {st} {ctype} {len(data)} B {secs:.2f} s [{cache}]")
        if not ok:
            fails.append(f"{path}: {name} {st} {ctype} {secs:.2f} s cache={cache!r}")
    if status != 200:
        fails.append(f"{path}: page {status}")
    return fails


def main(argv):
    base = "https://iosaresearch.org"
    if "--base" in argv:
        i = argv.index("--base")
        base = argv[i + 1].rstrip("/")
        argv = argv[:i] + argv[i + 2:]
    creators = []
    while "--creator" in argv:
        i = argv.index("--creator")
        creators.append(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    tokens = argv
    if not tokens and not creators:
        sys.exit(__doc__)
    fails = []
    robots = _get(base + "/robots.txt")[2].decode()
    if not twitterbot_may_read_claims(robots):
        fails.append("robots.txt: Twitterbot may not read /claim/")
    for t in tokens:
        fails += check_page(base, f"/claim/{t}", f"/claim/{t}")
    for h in creators:
        fails += check_page(base, f"/creators/{h}", f"/creators/{h}")
    print("PASS" if not fails else "FAIL\n" + "\n".join(fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
