"""SOC-N (23/10/2026): everything addressed to us on the social channels, by their official APIs.

Usage (from C:\\Work\\iosa-lab\\renders\\social, through the wrapper there):
    python3 notifications.py                         # the last 24 hours
    python3 notifications.py --hours 48
    python3 notifications.py --since 2026-10-22T08:00Z

Writes renders/social/queue/<date>-notifications.json and prints a short summary. Zero YouTube
units. Credentials are read from renders/ as publish_api.py reads them and are never printed;
the `paging` blocks of the Graph APIs (their `next` URL carries the token) are dropped as soon
as a response arrives.

What each channel gives (measured 23/10/2026):
- Bluesky, app.bsky.notification.listNotifications: replies (also to our replies under other
  people's posts), mentions, quotes, follows, likes. Answered = one of our posts replies to it
  (app.bsky.feed.getPostThread, depth 1); for a follow, whether we follow back.
- Threads: replies to our last 25 posts (/{post}/conversation, only posts with has_replies),
  answered = one of our replies under it (/{reply}/replies). Replies to OUR replies under
  someone else's thread are not returned by /replies nor by /conversation: our reply under
  oriohac's post (Dew9Q4cgE1O, 21/10) has has_replies = true, his reply of 22/10 is on the
  page, and both endpoints return an empty list. Those come from threads.com/activity: the
  summary lists our recent replies that have replies. Mentions (/me/mentions) need the
  permission threads_manage_mentions, which the current token does not have (403 code 10).
- Instagram: comments (and replies inside their threads) on our last 10 media; mentions as
  photo tags (/me/tags); @mentions in other people's captions and comments reach an app only
  by webhook. DMs (/me/conversations) when the token has the messaging permission.
- X: no API here; read in the browser.

Each item: channel, kind, author, text, link, time, answers ("our post" / "our reply" / None),
answers_link, already_answered (true / false / None when it does not apply, e.g. a like).
"""
import argparse, datetime, json, pathlib, sys

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # the repo: social.paths
from social import paths
from social.publish_api import _redact

HERE = paths.work()
RENDERS = paths.renders()
BSKY = "https://bsky.social/xrpc"
BSKY_HANDLE = "iosaresearch.bsky.social"
TH_API = "https://graph.threads.net/v1.0"
IG_API = "https://graph.instagram.com/v21.0"
OURS = "iosa.research.lab"                       # Threads and Instagram username
BSKY_KINDS = ("reply", "mention", "quote", "follow", "like")
THREADS_POSTS, IG_MEDIA, OWN_REPLIES = 25, 10, 25


def when(s):
    """API timestamps (…Z, …+0000, …+00:00) as aware UTC datetimes."""
    s = s.strip().replace("Z", "+00:00")
    if len(s) > 5 and s[-5] in "+-" and s[-3] != ":":
        s = s[:-2] + ":" + s[-2:]
    return datetime.datetime.fromisoformat(s).astimezone(datetime.timezone.utc)


def iso(d):
    return d.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Api:
    """GET/POST that counts requests per platform and never lets a token out."""
    def __init__(self):
        self.count = {"bluesky": 0, "threads": 0, "instagram": 0}

    def call(self, platform, method, url, **kw):
        self.count[platform] += 1
        try:
            r = requests.request(method, url, timeout=30, **kw)
            j = r.json()
        except (requests.RequestException, ValueError) as e:
            return 0, {"error": {"message": _redact(type(e).__name__)}}
        if isinstance(j, dict):
            j.pop("paging", None)
        return r.status_code, j


def err(j):
    e = (j or {}).get("error") or {}
    if isinstance(e, str):                                  # Bluesky: {"error": "...", "message": "..."}
        return _redact(f"{e}: {j.get('message', '')}"[:160])
    return _redact(f"code {e.get('code')}: {(e.get('message') or '')[:140]}")


def item(channel, kind, author, text, link, t, answers=None, answers_link=None, already=None):
    return {"channel": channel, "kind": kind, "author": author, "text": (text or "").strip(),
            "link": link, "time": iso(t), "answers": answers, "answers_link": answers_link,
            "already_answered": already}


# ---------- Bluesky ----------
def bsky_web(uri, handle):
    """at://did/app.bsky.feed.post/rkey -> https://bsky.app/profile/<handle>/post/<rkey>."""
    return f"https://bsky.app/profile/{handle}/post/{uri.rsplit('/', 1)[-1]}"


def bluesky(api, since):
    items, notes = [], []
    pw = (RENDERS / "bluesky.txt").read_text(encoding="utf-8-sig").strip().splitlines()[0].strip()
    s, j = api.call("bluesky", "POST", BSKY + "/com.atproto.server.createSession",
                    json={"identifier": BSKY_HANDLE, "password": pw})
    if "accessJwt" not in j:
        return items, [f"Bluesky: login failed ({err(j)})"]
    H, me = {"Authorization": "Bearer " + j["accessJwt"]}, j["did"]
    notes_raw, cursor = [], None
    while True:
        p = {"limit": 100, **({"cursor": cursor} if cursor else {})}
        s, j = api.call("bluesky", "GET", BSKY + "/app.bsky.notification.listNotifications", headers=H, params=p)
        if s != 200:
            return items, [f"Bluesky: listNotifications {s} ({err(j)})"]
        page = j.get("notifications") or []
        notes_raw += [n for n in page if when(n["indexedAt"]) >= since]
        cursor = j.get("cursor")
        if not cursor or not page or when(page[-1]["indexedAt"]) < since:
            break
    # what each notification answers: the parent of a reply, the subject of a like or a quote
    def subject(n):
        rec = n.get("record") or {}
        if n["reason"] == "reply":
            return ((rec.get("reply") or {}).get("parent") or {}).get("uri")
        return n.get("reasonSubject") if n["reason"] in ("like", "quote") else None
    subjects = sorted({u for u in map(subject, notes_raw) if u and u.split("/")[2] == me})
    ours = {}
    for i in range(0, len(subjects), 25):
        s, j = api.call("bluesky", "GET", BSKY + "/app.bsky.feed.getPosts", headers=H,
                        params=[("uris", u) for u in subjects[i:i + 25]])
        for p in j.get("posts") or []:
            ours[p["uri"]] = "our reply" if (p.get("record") or {}).get("reply") else "our post"
    skipped = 0
    for n in notes_raw:
        kind, a = n["reason"], n["author"]
        if kind not in BSKY_KINDS:
            skipped += 1
            continue
        rec, subj = n.get("record") or {}, subject(n)
        answers = ours.get(subj) if subj else None
        if kind == "follow":
            link, already = f"https://bsky.app/profile/{a['handle']}", bool((a.get("viewer") or {}).get("following"))
        elif kind == "like":
            link, already = bsky_web(subj, BSKY_HANDLE) if subj else None, None
        else:
            link = bsky_web(n["uri"], a["handle"])
            s, j = api.call("bluesky", "GET", BSKY + "/app.bsky.feed.getPostThread", headers=H,
                            params={"uri": n["uri"], "depth": 1, "parentHeight": 0})
            replies = ((j.get("thread") or {}).get("replies") or []) if s == 200 else None
            already = None if replies is None else any(
                ((r.get("post") or {}).get("author") or {}).get("did") == me for r in replies)
        items.append(item("bluesky", kind, a["handle"], rec.get("text") if kind not in ("like", "follow") else "",
                          link, when(n["indexedAt"]), answers,
                          bsky_web(subj, BSKY_HANDLE) if subj and subj.split("/")[2] == me else None, already))
    if skipped:
        notes.append(f"Bluesky: {skipped} other notifications (reposts and the like) not listed")
    return items, notes


# ---------- Threads ----------
def threads(api, since):
    items, notes = [], []
    tok = json.loads((RENDERS / "threads_token.json").read_text(encoding="utf-8"))["access_token"]

    def get(path, **p):
        return api.call("threads", "GET", TH_API + path, params={**p, "access_token": tok})

    def answered(reply_id):
        s, j = get(f"/{reply_id}/replies", fields="id,username")
        return None if s != 200 else any(x.get("username") == OURS for x in j.get("data") or [])

    s, j = get("/me/threads", fields="id,timestamp,permalink,has_replies", limit=THREADS_POSTS)
    if s != 200:
        notes.append(f"Threads: /me/threads {s} ({err(j)})")
    for post in (j.get("data") or []) if s == 200 else []:
        if not post.get("has_replies"):
            continue
        s2, c = get(f"/{post['id']}/conversation", fields="id,text,username,timestamp,permalink")
        if s2 != 200:
            notes.append(f"Threads: conversation of {post['permalink']} {s2} ({err(c)})")
            continue
        for r in c.get("data") or []:
            if r.get("username") == OURS or when(r["timestamp"]) < since:
                continue
            items.append(item("threads", "reply", r.get("username"), r.get("text"), r.get("permalink"),
                              when(r["timestamp"]), "our post", post["permalink"], answered(r["id"])))
    # replies to our replies: has_replies says they exist; the API does not return them
    s, j = get("/me/replies", fields="id,timestamp,permalink,has_replies", limit=OWN_REPLIES)
    hidden = []
    for r in (j.get("data") or []) if s == 200 else []:
        if r.get("has_replies"):
            s2, c = get(f"/{r['id']}/replies", fields="id,text,username,timestamp,permalink")
            got = [x for x in (c.get("data") or []) if x.get("username") != OURS] if s2 == 200 else []
            for x in got:
                if when(x["timestamp"]) >= since:
                    items.append(item("threads", "reply", x.get("username"), x.get("text"), x.get("permalink"),
                                      when(x["timestamp"]), "our reply", r["permalink"], answered(x["id"])))
            if not got:
                hidden.append(r["permalink"])
    if s != 200:
        notes.append(f"Threads: /me/replies {s} ({err(j)})")
    if hidden:
        notes.append("Threads: replies to our replies need threads.com/activity "
                     f"({len(hidden)} of our replies have replies the API does not return: {', '.join(hidden)})")
    s, j = get("/me/mentions", fields="id,text,username,timestamp,permalink")
    if s == 200:
        for m in j.get("data") or []:
            if when(m["timestamp"]) >= since:
                items.append(item("threads", "mention", m.get("username"), m.get("text"), m.get("permalink"),
                                  when(m["timestamp"]), None, None, answered(m["id"])))
    else:
        notes.append(f"Threads: mentions not readable with this token ({err(j)}; needs threads_manage_mentions)")
    return items, notes


# ---------- Instagram ----------
def instagram(api, since):
    items, notes = [], []
    tok = json.loads((RENDERS / "instagram_token.json").read_text(encoding="utf-8"))["access_token"]

    def get(path, **p):
        return api.call("instagram", "GET", IG_API + path, params={**p, "access_token": tok})

    s, j = get("/me/media", fields="id,timestamp,permalink,comments_count", limit=IG_MEDIA)
    if s != 200:
        notes.append(f"Instagram: /me/media {s} ({err(j)})")
    for m in (j.get("data") or []) if s == 200 else []:
        if not m.get("comments_count"):
            continue
        s2, c = get(f"/{m['id']}/comments", fields="id,text,username,timestamp,replies{id,text,username,timestamp}")
        if s2 != 200:
            notes.append(f"Instagram: comments of {m['permalink']} {s2} ({err(c)})")
            continue
        for com in c.get("data") or []:
            rs = sorted((com.get("replies") or {}).get("data") or [], key=lambda x: x["timestamp"])
            ours_at = [when(x["timestamp"]) for x in rs if x.get("username") == OURS]
            if com.get("username") != OURS and when(com["timestamp"]) >= since:
                items.append(item("instagram", "comment", com.get("username"), com.get("text"), m["permalink"],
                                  when(com["timestamp"]), "our post", m["permalink"], bool(ours_at)))
            for x in rs:
                t = when(x["timestamp"])
                if x.get("username") == OURS or t < since:
                    continue
                before = [o for o in ours_at if o < t] or (com.get("username") == OURS and [when(com["timestamp"])])
                items.append(item("instagram", "comment", x.get("username"), x.get("text"), m["permalink"], t,
                                  "our reply" if before else "our post", m["permalink"], any(o > t for o in ours_at)))
    s, j = get("/me/tags", fields="id,username,timestamp,permalink,caption")
    if s == 200:
        for m in j.get("data") or []:
            if when(m["timestamp"]) >= since:
                items.append(item("instagram", "tag", m.get("username"), m.get("caption"), m.get("permalink"),
                                  when(m["timestamp"])))
    else:
        notes.append(f"Instagram: tags {s} ({err(j)})")
    notes.append("Instagram: @mentions in other people's captions and comments arrive only by webhook; "
                 "photo tags are listed")
    s, j = get("/me/conversations", platform="instagram",
               fields="id,updated_time,messages.limit(5){id,from,message,created_time}")
    if s != 200:
        notes.append(f"Instagram: DMs not readable with this token ({err(j)}; needs the messaging permission)")
    else:
        notes.append(f"Instagram: DMs read ({len(j.get('data') or [])} conversations on the first page)")
        for conv in j.get("data") or []:
            msgs = sorted((conv.get("messages") or {}).get("data") or [], key=lambda x: x["created_time"])
            theirs = [x for x in msgs if (x.get("from") or {}).get("username") != OURS]
            if not theirs or when(theirs[-1]["created_time"]) < since:
                continue
            last = theirs[-1]
            items.append(item("instagram", "dm", (last.get("from") or {}).get("username"), last.get("message"),
                              "https://www.instagram.com/direct/inbox/", when(last["created_time"]), None, None,
                              (msgs[-1].get("from") or {}).get("username") == OURS))
    return items, notes


# ---------- run ----------
def collect(since, until, api=None):
    api = api or Api()
    items, notes = [], []
    for name, fn in (("Bluesky", bluesky), ("Threads", threads), ("Instagram", instagram)):
        try:
            i, n = fn(api, since)
        except (OSError, KeyError, ValueError) as e:
            i, n = [], [f"{name}: stopped ({_redact(type(e).__name__)}: {_redact(e)[:120]})"]
        items += i
        notes += n
    notes.append("X: browser")
    items.sort(key=lambda x: x["time"], reverse=True)
    return {"since": iso(since), "until": iso(until), "items": items, "notes": notes,
            "requests": dict(api.count), "youtube_units": 0}


def summary(out):
    lines = [f"Notifications {out['since']} -> {out['until']}"]
    for ch in ("bluesky", "threads", "instagram"):
        mine = [x for x in out["items"] if x["channel"] == ch]
        kinds = {}
        for x in mine:
            kinds[x["kind"]] = kinds.get(x["kind"], 0) + 1
        k = ", ".join(f"{n} {kd}" for kd, n in sorted(kinds.items())) or "nothing"
        lines.append(f"{ch.capitalize()}: {k} ({out['requests'][ch]} requests)")
    todo = [x for x in out["items"] if x["already_answered"] is False and x["kind"] != "follow"]
    if todo:
        lines.append("Not answered yet:")
        for x in todo:
            what = f" to {x['answers']}" if x["answers"] else ""
            lines.append(f"  {x['channel']} {x['kind']}{what} @{x['author']} {x['time'][5:16]}: "
                         f"{x['text'][:70]!r} {x['link']}")
    lines += out["notes"]
    lines.append("YouTube units: 0")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--since", help="UTC time, e.g. 2026-10-22T08:00Z (overrides --hours)")
    a = ap.parse_args(argv)
    until = datetime.datetime.now(datetime.timezone.utc)
    since = when(a.since) if a.since else until - datetime.timedelta(hours=a.hours)
    out = collect(since, until)
    q = HERE / "queue"
    q.mkdir(parents=True, exist_ok=True)
    f = q / f"{until:%Y-%m-%d}-notifications.json"
    f.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(_redact(summary(out)))
    print("written", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
