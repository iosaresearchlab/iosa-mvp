"""SOC-E (23/10/2026; limits SOC-E2, owner 24/10): likes and follows on Bluesky, within fixed
limits, by the official API.

Usage (from C:\\Work\\iosa-lab\\renders\\social, through the wrapper there):
    python3 bsky_engage.py --like <post> [<post> ...] --follow <handle> [<handle> ...]
    python3 bsky_engage.py --like https://bsky.app/profile/x.bsky.social/post/3abc --dry-run

A post is an at:// URI or its bsky.app link; a handle may carry the @. The limits are fixed:
- never more than 25 likes and 10 follows in one run (a run asking for more does nothing);
- the same account at most once in 24 hours, counting likes and follows together and the run
  itself: an account already in renders/social/bsky_engage.log in the last 24 hours is skipped
  (SOC-E2, the owner's volumes of 24/10; were 4 likes, 2 follows, once in 7 days);
- never a reply, never a post: the script only writes app.bsky.feed.like and
  app.bsky.graph.follow records.
A post already liked, or an account already followed, is skipped and not logged. Every action
is logged (UTC time, action, account DID, handle, post URI). Zero YouTube units. The password
is read from renders/bluesky.txt as publish_api.py reads it and is never printed.
"""
import argparse, datetime, pathlib, re, sys, time

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # the repo: social.paths
from social import paths
from social.publish_api import _redact

HERE = paths.work()
RENDERS = paths.renders()
BSKY = "https://bsky.social/xrpc"
HANDLE = "iosaresearch.bsky.social"
LOG = "bsky_engage.log"
MAX_LIKES, MAX_FOLLOWS, HOURS = 25, 10, 24
WEB = re.compile(r"^https://bsky\.app/profile/([^/]+)/post/([A-Za-z0-9]+)/?$")


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def recent(hours=HOURS):
    """DIDs in the log of the last `hours` hours."""
    f = HERE / LOG
    seen, since = set(), now() - datetime.timedelta(hours=hours)
    if not f.is_file():
        return seen
    for line in f.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        try:
            t = datetime.datetime.fromisoformat(parts[0].replace("Z", "+00:00"))
        except (ValueError, IndexError):
            continue
        if t >= since and len(parts) >= 3:
            seen.add(parts[2])
    return seen


def log(action, did, handle, uri=""):
    with (HERE / LOG).open("a", encoding="utf-8") as f:
        f.write(f"{now().strftime('%Y-%m-%dT%H:%M:%SZ')} {action} {did} {handle} {uri}".rstrip() + "\n")


class Bsky:
    def __init__(self):
        self.requests = 0
        self.H = {}
        self.did = None

    def call(self, method, nsid, **kw):
        self.requests += 1
        r = requests.request(method, f"{BSKY}/{nsid}", headers=self.H, timeout=30, **kw)
        if r.status_code >= 500 and method == "GET":          # 23/10: one 502 UpstreamFailure on getPosts
            time.sleep(2)                                     # a read is retried once; a write never is
            self.requests += 1
            r = requests.request(method, f"{BSKY}/{nsid}", headers=self.H, timeout=30, **kw)
        try:
            j = r.json()
        except ValueError:
            j = {}
        if r.status_code != 200:
            raise SystemExit(_redact(f"ERRORE bluesky {nsid}: {r.status_code} {j.get('error')} {j.get('message', '')[:120]}"))
        return j

    def login(self):
        pw = (RENDERS / "bluesky.txt").read_text(encoding="utf-8-sig").strip().splitlines()[0].strip()
        j = self.call("POST", "com.atproto.server.createSession", json={"identifier": HANDLE, "password": pw})
        self.H, self.did = {"Authorization": "Bearer " + j["accessJwt"]}, j["did"]

    def create(self, collection, record):
        record = {"$type": collection, "createdAt": now().strftime("%Y-%m-%dT%H:%M:%S.000Z"), **record}
        return self.call("POST", "com.atproto.repo.createRecord",
                         json={"repo": self.did, "collection": collection, "record": record})


def post_uri(api, s):
    """at:// URI of a post given as a URI or a bsky.app link."""
    if s.startswith("at://"):
        return s
    m = WEB.match(s.strip())
    if not m:
        raise SystemExit(f"ERRORE: not a Bluesky post: {s}")
    actor, rkey = m.groups()
    did = actor if actor.startswith("did:") else api.call(
        "GET", "com.atproto.identity.resolveHandle", params={"handle": actor})["did"]
    return f"at://{did}/app.bsky.feed.post/{rkey}"


def run(likes, follows, dry=False, api=None):
    if len(likes) > MAX_LIKES or len(follows) > MAX_FOLLOWS:
        raise SystemExit(f"ERRORE: at most {MAX_LIKES} likes and {MAX_FOLLOWS} follows per run "
                         f"(asked {len(likes)} and {len(follows)}): nothing done")
    api = api or Bsky()
    api.login()
    seen, done, skipped = recent(), [], []
    plan = []                                              # (action, did, handle, uri, cid)
    if likes:
        uris = [post_uri(api, s) for s in likes]
        got = {p["uri"]: p for p in api.call("GET", "app.bsky.feed.getPosts",
                                              params=[("uris", u) for u in uris]).get("posts") or []}
        for u in uris:
            p = got.get(u)
            if not p:
                skipped.append(f"like {u}: post not found")
            elif (p.get("viewer") or {}).get("like"):
                skipped.append(f"like {u}: already liked")
            else:
                plan.append(("like", p["author"]["did"], p["author"]["handle"], u, p["cid"]))
    if follows:
        handles = [h.lstrip("@").strip() for h in follows]
        profs = api.call("GET", "app.bsky.actor.getProfiles", params=[("actors", h) for h in handles]).get("profiles") or []
        by = {p["handle"]: p for p in profs} | {p["did"]: p for p in profs}
        for h in handles:
            p = by.get(h)
            if not p:
                skipped.append(f"follow {h}: account not found")
            elif (p.get("viewer") or {}).get("following"):
                skipped.append(f"follow {h}: already followed")
            else:
                plan.append(("follow", p["did"], p["handle"], "", None))
    for action, did, handle, uri, cid in plan:
        if did == api.did:
            skipped.append(f"{action} {handle}: our own account")
            continue
        if did in seen:
            skipped.append(f"{action} {handle}: account already engaged in the last {HOURS} hours")
            continue
        seen.add(did)
        if not dry:
            if action == "like":
                api.create("app.bsky.feed.like", {"subject": {"uri": uri, "cid": cid}})
            else:
                api.create("app.bsky.graph.follow", {"subject": did})
            log(action, did, handle, uri)
        done.append(f"{action} {handle} {uri}".rstrip())
    return done, skipped, api.requests


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--like", nargs="*", default=[], metavar="POST")
    ap.add_argument("--follow", nargs="*", default=[], metavar="HANDLE")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not a.like and not a.follow:
        ap.error("nothing to do: give --like and/or --follow")
    done, skipped, n = run(a.like, a.follow, a.dry_run)
    for d in done:
        print(("would " if a.dry_run else "done ") + d)
    for s in skipped:
        print("skipped " + s)
    print(f"bluesky requests: {n}; YouTube units: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
