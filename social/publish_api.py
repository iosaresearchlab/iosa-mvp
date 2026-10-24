"""IOSA social publisher: Bluesky, Instagram, Threads and X (through Buffer) by their official APIs.

Usage (from C:\\Work\\iosa-lab\\renders\\social, through the wrapper there):
    python3 publish_api.py queue/<post>.json            # publish every channel still missing
    python3 publish_api.py queue/<post>.json --only bluesky,threads
    python3 publish_api.py queue/<post>.json --dry-run  # say what would go out; no network, no writes
    python3 publish_api.py queue/<post>.json --x        # also X, through Buffer (SOC-X, see below)

Before publishing anything the spec is checked (social/validate_spec.py, FIX-1f): X over 280
weighted, Bluesky over 300 graphemes or without alt text, Threads over 500, an Instagram caption
over 2,200 characters or 30 hashtags, a named file missing. An invalid spec publishes nothing.
    python3 publish_api.py --refresh-tokens            # extend the Instagram and Threads tokens
    python3 publish_api.py --check-insights            # can the Threads token read insights? (FIX-1g)

The code is versioned in the repo, social/publish_api.py (FIX-1e, 20/10/2026); it works in
renders/social (IOSA_SOCIAL_WORK, set by the wrapper): queue, media, credentials stay there.

Post spec (JSON):
{
  "id": "2026-10-10-ml7",
  "images": ["2026-10-10-breakout-ml7.jpg"],        # JPEG, 1 to 10 (carousel when > 1)
  "video": null, "cover": null,                     # a Reel/video instead of images (mp4 + jpg cover)
  "bluesky":   {"text": "...", "alt": "..."},       # null to skip
  "instagram": {"caption": "...", "user_tags": [{"username": "x", "x": 0.5, "y": 0.8}],
                "collaborators": ["user"], "trial": true},  # both optional, SOC-W5 below
  "threads":   {"text": "...", "topic_tag": "YouTube Creators"},
  "x":         {"text": "...", "reply": "https://youtu.be/... ..."}   # the card + the first reply
}

X (SOC-X, owner 20/10/2026) goes through Buffer's GraphQL API (api.buffer.com, key in
renders/buffer_key.txt), never the browser, and only when asked: --x, or --only with x in it,
until the slot tasks are switched to it. The post is x.text with the first image as the card;
x.reply (text only, YouTube link first) is the second item of the thread; the card is x.card
when the spec names one, else the first image. Buffer wants every
item in metadata.twitter.thread, the first one repeating the post (developers.buffer.com,
"create threaded post": the thread is the source of truth). Mode shareNow. The Buffer post id
is written to result.x_buffer at once, so a run that stops before the X link comes back reads
that post again instead of creating a second one. Free plan: 3,000 requests in 30 days; every
request is logged in renders/social/buffer_requests.log and the script refuses to start an X
publication past BUFFER_BUDGET of them (a publication costs 2 to 6).
Results (links and ids) are written back into the spec under "result". A channel that already has a
result is never published again, so a retry cannot double-post.

Instagram, two optional fields (SOC-W5, owner 24/10/2026), checked against the documentation of
the API this script uses (Instagram API with Instagram Login, graph.instagram.com), 24/10/2026:
- "trial": a trial reel, shown to non-followers first. Supported: changelog of 3 Dec 2025, "Trial
  Reels Support in Instagram API with Facebook Login and Instagram API with Instagram Login";
  "trial_params is optional and part of the create media endpoint"; graduation_strategy "should be
  either MANUAL or SS_PERFORMANCE"; "The media_type must be REELS if this parameter is included".
  true = SS_PERFORMANCE (Instagram shares it with followers if it performs); "MANUAL" also accepted.
  Reels only: on an image post it is ignored with a warning.
- "collaborators": NOT supported by this API. The create-media parameter ("A list of up to 3
  instagram usernames as collaborators", Feed image, Reels and Carousels) is documented for
  graph.facebook.com (Facebook Login), and the IG Media reference says of collaborators
  "Available for Instagram API with Facebook Login only". The field is accepted, validated (at
  most 3 usernames) and ignored, with a warning in the dry run and in the run.

Credentials are read from renders/*.txt|json and backend/.env and are never printed.
Media go to the public Supabase Storage bucket "social" (the APIs fetch images and videos by URL).
"""
import json, os, re, sys, time, datetime, mimetypes, pathlib, urllib.parse
import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # the repo: social.paths
from social import paths, validate_spec

# Never print a credential (20/10/2026: a DNS failure in --check-insights printed the
# exception of requests, whose message carries the URL with access_token=...). Every
# traceback and every error line of this script goes through _redact.
_SECRET = re.compile(r"(access_token=|Bearer\s+|\"(?:access_token|accessJwt|refreshJwt|password)\":\s*\")[^&\s'\"),]+")


def _redact(text):
    return _SECRET.sub(lambda m: m.group(1) + "***", str(text))


def _excepthook(kind, value, tb):
    import traceback
    sys.stderr.write(_redact("".join(traceback.format_exception(kind, value, tb))))


sys.excepthook = _excepthook

HERE = paths.work()                                        # renders/social: queue and media
RENDERS = paths.renders()                                  # renders: credentials
REPO = paths.REPO                                          # iosa-lab: backend/.env
IG_API = "https://graph.instagram.com/v21.0"
TH_API = "https://graph.threads.net/v1.0"


def env():
    txt = (REPO / "backend" / ".env").read_text(encoding="utf-8")
    return {k: v.strip().strip('"') for k, v in re.findall(r"^([A-Z_]+)=(.*)$", txt, re.M)}


def die(msg):
    print("ERRORE:", _redact(msg))
    sys.exit(1)


# ---------- storage ----------
def upload_public(path):
    e = env()
    p = pathlib.Path(path)
    if not p.is_absolute():
        p = HERE / p
    key = f"{datetime.date.today():%Y/%m}/{p.name}"
    ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    r = requests.post(f"{e['SUPABASE_URL']}/storage/v1/object/social/{key}",
                      headers={"Authorization": f"Bearer {e['SUPABASE_SERVICE_KEY']}",
                               "apikey": e["SUPABASE_SERVICE_KEY"], "Content-Type": ctype,
                               "x-upsert": "true"},
                      data=p.read_bytes(), timeout=120)
    if r.status_code >= 300:
        die(f"upload {p.name}: {r.status_code} {r.text[:200]}")
    return f"{e['SUPABASE_URL']}/storage/v1/object/public/social/{key}"


# ---------- bluesky ----------
def bsky_facets(text):
    b = text.encode("utf-8")
    facets = []
    for m in re.finditer(rb"(https?://)?(iosaresearch\.org[^\s]*|youtube\.com/[^\s]+|youtu\.be/[^\s]+)", b):
        uri = m.group(0).decode()
        if not uri.startswith("http"):
            uri = "https://" + uri
        facets.append({"index": {"byteStart": m.start(), "byteEnd": m.end()},
                       "features": [{"$type": "app.bsky.richtext.facet#link", "uri": uri}]})
    for m in re.finditer(rb"(?:^|\s)(#[A-Za-z][A-Za-z0-9_]*)", b):
        s, t = m.start(1), m.end(1)
        facets.append({"index": {"byteStart": s, "byteEnd": t},
                       "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": b[s + 1:t].decode()}]})
    return facets


def publish_bluesky(spec):
    pw = (RENDERS / "bluesky.txt").read_text(encoding="utf-8-sig").strip().splitlines()[0].strip()
    handle = "iosaresearch.bsky.social"
    s = requests.post("https://bsky.social/xrpc/com.atproto.server.createSession",
                      json={"identifier": handle, "password": pw}, timeout=30).json()
    if "accessJwt" not in s:
        die(f"bluesky login: {s.get('error')}")
    H = {"Authorization": f"Bearer {s['accessJwt']}"}
    text = spec["bluesky"]["text"]
    if len(text) > 300:
        die(f"bluesky: testo di {len(text)} caratteri (max 300)")
    rec = {"$type": "app.bsky.feed.post", "text": text, "langs": ["en"],
           "createdAt": datetime.datetime.utcnow().isoformat(timespec="milliseconds") + "Z"}
    f = bsky_facets(text)
    if f:
        rec["facets"] = f
    imgs = []
    for path in (spec.get("images") or [])[:4]:
        p = HERE / path
        blob = requests.post("https://bsky.social/xrpc/com.atproto.repo.uploadBlob",
                             headers={**H, "Content-Type": "image/jpeg"}, data=p.read_bytes(), timeout=60).json()
        if "blob" not in blob:
            die(f"bluesky upload: {blob}")
        try:
            from PIL import Image
            w, h = Image.open(p).size
        except Exception:
            w, h = 1080, 1350
        imgs.append({"alt": spec["bluesky"].get("alt", ""), "image": blob["blob"],
                     "aspectRatio": {"width": w, "height": h}})
    if imgs:
        rec["embed"] = {"$type": "app.bsky.embed.images", "images": imgs}
    r = requests.post("https://bsky.social/xrpc/com.atproto.repo.createRecord", headers=H,
                      json={"repo": s["did"], "collection": "app.bsky.feed.post", "record": rec}, timeout=30).json()
    if "uri" not in r:
        die(f"bluesky post: {r}")
    rkey = r["uri"].rsplit("/", 1)[1]
    return {"uri": r["uri"], "url": f"https://bsky.app/profile/{handle}/post/{rkey}"}


# ---------- instagram ----------
def ig_wait(cid, tok):
    for _ in range(60):
        st = requests.get(f"{IG_API}/{cid}", params={"fields": "status_code", "access_token": tok}, timeout=30).json()
        if st.get("status_code") == "FINISHED":
            return
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            die(f"instagram container {st}")
        time.sleep(5)
    die("instagram: container non pronto dopo 5 minuti")


def ig_extras(spec):
    """SOC-W5: (trial_params or None, warnings) for the optional Instagram fields."""
    ig = spec.get("instagram") or {}
    warnings, trial = [], None
    if ig.get("collaborators"):
        warnings.append("instagram.collaborators " + ", ".join(ig["collaborators"]) + ": ignored, "
                        "collaborator invites are not in the Instagram API with Instagram Login "
                        "(Facebook Login only)")
    t = ig.get("trial")
    if t not in (None, False):
        if not spec.get("video"):
            warnings.append("instagram.trial: ignored, a trial reel needs a video (media_type REELS)")
        else:
            trial = json.dumps({"graduation_strategy": t if isinstance(t, str) else "SS_PERFORMANCE"})
    return trial, warnings


def publish_instagram(spec, urls):
    t = json.loads((RENDERS / "instagram_token.json").read_text(encoding="utf-8"))
    tok, uid = t["access_token"], t["user_id"]
    ig = spec["instagram"]
    tags = json.dumps(ig.get("user_tags") or [])
    trial, warnings = ig_extras(spec)
    for w in warnings:
        print("ATTENZIONE:", w)
    if spec.get("video"):
        p = {"media_type": "REELS", "video_url": urls["video"], "caption": ig["caption"],
             "share_to_feed": "true", "access_token": tok}
        if trial:
            p["trial_params"] = trial
        if urls.get("cover"):
            p["cover_url"] = urls["cover"]
        if ig.get("user_tags"):
            p["user_tags"] = tags
        c = requests.post(f"{IG_API}/{uid}/media", data=p, timeout=60).json()
    elif len(urls["images"]) == 1:
        p = {"image_url": urls["images"][0], "caption": ig["caption"], "access_token": tok}
        if ig.get("user_tags"):
            p["user_tags"] = tags
        c = requests.post(f"{IG_API}/{uid}/media", data=p, timeout=60).json()
    else:
        kids = []
        for i, u in enumerate(urls["images"]):
            p = {"image_url": u, "is_carousel_item": "true", "access_token": tok}
            if i == 0 and ig.get("user_tags"):
                p["user_tags"] = tags
            k = requests.post(f"{IG_API}/{uid}/media", data=p, timeout=60).json()
            if "id" not in k:
                die(f"instagram carousel item: {k}")
            kids.append(k["id"])
        c = requests.post(f"{IG_API}/{uid}/media", data={"media_type": "CAROUSEL", "children": ",".join(kids),
                          "caption": ig["caption"], "access_token": tok}, timeout=60).json()
    if "id" not in c:
        die(f"instagram container: {c}")
    ig_wait(c["id"], tok)
    m = requests.post(f"{IG_API}/{uid}/media_publish", data={"creation_id": c["id"], "access_token": tok}, timeout=60).json()
    if "id" not in m:
        die(f"instagram publish: {m}")
    info = requests.get(f"{IG_API}/{m['id']}", params={"fields": "permalink,caption", "access_token": tok}, timeout=30).json()
    if (info.get("caption") or "").strip() != ig["caption"].strip():
        print("ATTENZIONE: la didascalia letta da Instagram non coincide con quella inviata")
    return {"id": m["id"], "url": info.get("permalink")}


# ---------- threads ----------
def tag_word(topic):
    """A Threads topic as an in-text tag: no spaces, periods or ampersands."""
    return re.sub(r"[\s.&]+", "", topic or "")


def text_with_tag(text, topic):
    """The text with the topic as its one tag at the end, if it has none and it fits in 500."""
    word = tag_word(topic)
    if not word or re.search(r"(?:^|\s)#\w", text or ""):
        return text
    out = f"{text}\n\n#{word}" if text else f"#{word}"
    return out if len(out) <= 500 else text


def publish_threads(spec, urls):
    t = json.loads((RENDERS / "threads_token.json").read_text(encoding="utf-8"))
    tok, uid = t["access_token"], t["user_id"]
    th = spec["threads"]
    if len(th["text"]) > 500:
        die(f"threads: testo di {len(th['text'])} caratteri (max 500)")
    base = {"text": th["text"], "access_token": tok}
    if th.get("topic_tag"):
        base["topic_tag"] = th["topic_tag"]

    def create(p):
        # Threads keeps topic_tag on carousels too (read back 21/10: snepy CAROUSEL_ALBUM "Gaming
        # Threads"); the deep dive of 21/10 lost it on one failed create that was taken for a
        # refusal. So a failure is retried once as it is; only then the topic goes into the text
        # as its one tag (Threads: one tag per post, no spaces, periods or ampersands).
        r = requests.post(f"{TH_API}/{uid}/threads", data=p, timeout=60).json()
        if "id" not in r and "topic_tag" in p:
            e = r.get("error", {})
            print("Threads: container con topic_tag non creato:", e.get("code"), e.get("error_subcode"), e.get("message"))
            r = requests.post(f"{TH_API}/{uid}/threads", data=p, timeout=60).json()
            if "id" not in r:
                p = {k: v for k, v in p.items() if k != "topic_tag"}
                p["text"] = text_with_tag(p.get("text", ""), th["topic_tag"])
                print("Threads: topic_tag rifiutato due volte, tag nel testo:", "#" + tag_word(th["topic_tag"]))
                r = requests.post(f"{TH_API}/{uid}/threads", data=p, timeout=60).json()
        return r

    if spec.get("video"):
        c = create({**base, "media_type": "VIDEO", "video_url": urls["video"]})
    elif not urls["images"]:
        c = create({**base, "media_type": "TEXT"})
    elif len(urls["images"]) == 1:
        c = create({**base, "media_type": "IMAGE", "image_url": urls["images"][0]})
    else:
        kids = []
        for u in urls["images"]:
            k = requests.post(f"{TH_API}/{uid}/threads", data={"media_type": "IMAGE", "image_url": u,
                              "is_carousel_item": "true", "access_token": tok}, timeout=60).json()
            if "id" not in k:
                die(f"threads carousel item: {k}")
            kids.append(k["id"])
        c = create({**base, "media_type": "CAROUSEL", "children": ",".join(kids)})
    if "id" not in c:
        die(f"threads container: {c}")
    for _ in range(60):                                   # media must finish processing before publish
        st = requests.get(f"{TH_API}/{c['id']}", params={"fields": "status,error_message", "access_token": tok}, timeout=30).json()
        if st.get("status") in ("FINISHED", None):
            break
        if st.get("status") in ("ERROR", "EXPIRED"):
            die(f"threads container {st}")
        time.sleep(5)
    m = requests.post(f"{TH_API}/{uid}/threads_publish", data={"creation_id": c["id"], "access_token": tok}, timeout=60).json()
    if "id" not in m:
        die(f"threads publish: {m}")
    info = requests.get(f"{TH_API}/{m['id']}", params={"fields": "permalink", "access_token": tok}, timeout=30).json()
    return {"id": m["id"], "url": info.get("permalink")}


# ---------- x, through buffer (SOC-X) ----------
BUFFER_API = "https://api.buffer.com"
BUFFER_ORG = "6ad7c7bbf110b1e5ece4214e"
BUFFER_X_CHANNEL = "6ad7c83b778b240e2f6ee253"          # @IOSAResearch
BUFFER_BUDGET = 1000                                   # of the plan's 3,000 requests in 30 days
BUFFER_POLL_S = (15, 30, 45, 90)                       # waits before reading the post: 4 reads at most
BUFFER_LOG = "buffer_requests.log"


def buffer_used(days=30):
    """Buffer requests of the last `days` days, from the log."""
    f = HERE / BUFFER_LOG
    if not f.is_file():
        return 0
    since = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    n = 0
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            if datetime.datetime.fromisoformat(line.split()[0].rstrip("Z")) >= since:
                n += 1
        except (ValueError, IndexError):
            continue
    return n


def buffer(query, variables, label):
    key = (RENDERS / "buffer_key.txt").read_text(encoding="utf-8-sig").strip()
    r = requests.post(BUFFER_API, json={"query": query, "variables": variables},
                      headers={"Authorization": "Bearer " + key}, timeout=60)
    with (HERE / BUFFER_LOG).open("a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.utcnow().isoformat(timespec='seconds')}Z {label} {r.status_code}\n")
    try:
        j = r.json()
    except ValueError:
        die(f"buffer {label}: {r.status_code} {r.text[:200]}")
    if j.get("errors"):
        die(f"buffer {label}: {j['errors'][0].get('message')}")
    return j["data"]


BUFFER_CREATE = """mutation($input: CreatePostInput!) { createPost(input: $input) {
  ... on PostActionSuccess { post { id status } }
  ... on MutationError { message } } }"""
BUFFER_READ = """query($id: PostId!) { post(input: {id: $id}) {
  id status externalLink sentAt error { message } } }"""


def x_input(spec, image_url):
    """createPost input for the X post: the card post, then the reply, as Buffer's thread."""
    x = spec["x"]
    assets = [{"image": {"url": image_url}}] if image_url else []
    thread = [{"text": x["text"], "assets": assets}]
    if x.get("reply"):
        thread.append({"text": x["reply"], "assets": []})
    return {"channelId": BUFFER_X_CHANNEL, "schedulingType": "automatic", "mode": "shareNow",
            "text": x["text"], "assets": assets, "metadata": {"twitter": {"thread": thread}}}


def publish_x(spec, urls, save):
    """Publish spec x through Buffer; returns result.x. Resumes a post already created."""
    res = spec["result"]
    pid = res.get("x_buffer")
    if not pid:
        used = buffer_used()
        if used + 6 > BUFFER_BUDGET:
            die(f"buffer: {used} richieste negli ultimi 30 giorni, budget {BUFFER_BUDGET}: X non pubblicato")
        card = (spec.get("x") or {}).get("card")       # the X card (PNG) when the spec names one
        if card and not urls.get("x_card"):
            urls["x_card"] = upload_public(card)
            res["_media"] = urls
            save()
        image = urls.get("x_card") or (urls.get("images") or [None])[0]
        d = buffer(BUFFER_CREATE, {"input": x_input(spec, image)}, "createPost " + spec.get("id", ""))
        out = d["createPost"]
        if "post" not in out:
            die(f"buffer createPost: {out.get('message')}")
        pid = out["post"]["id"]
        res["x_buffer"] = pid                              # before anything else can fail
        save()
    for wait in BUFFER_POLL_S:
        time.sleep(wait)
        post = buffer(BUFFER_READ, {"id": pid}, "read " + pid)["post"]
        if post["status"] == "sent" and post.get("externalLink"):
            return {"post": post["externalLink"], "buffer": pid, "via": "buffer"}
        if post["status"] == "error":
            die(f"buffer: post {pid} in errore: {(post.get('error') or {}).get('message')}")
    die(f"buffer: post {pid} non ancora inviato (stato {post['status']}); rilancia: rilegge lo stesso post")


# ---------- tokens ----------
def refresh_tokens():
    for name, url, grant in (("instagram_token.json", "https://graph.instagram.com/refresh_access_token", "ig_refresh_token"),
                             ("threads_token.json", "https://graph.threads.net/refresh_access_token", "th_refresh_token")):
        f = RENDERS / name
        t = json.loads(f.read_text(encoding="utf-8"))
        r = requests.get(url, params={"grant_type": grant, "access_token": t["access_token"]}, timeout=30).json()
        if "access_token" in r:
            t["access_token"] = r["access_token"]
            t["expires_at"] = int(time.time()) + int(r.get("expires_in", 0))
            f.write_text(json.dumps(t), encoding="utf-8")
            print(name, "rinnovato, scade tra giorni:", int(r.get("expires_in", 0)) // 86400)
        else:
            print(name, "NON rinnovato:", r.get("error", {}).get("message"))


CAP = {"instagram": 2, "threads": 2}
CHANNELS = ("bluesky", "instagram", "threads", "x")
OPT_IN = {"x"}                    # published only when asked (--x, or --only naming it)


def used_today(sp, ch):
    """Posts already published on `ch` by the other specs of the same editorial day."""
    day = sp.name[:10]
    n = 0
    for q in sp.parent.glob(day + "-*.json"):
        if q == sp:
            continue
        try:
            r = json.loads(q.read_text(encoding="utf-8")).get("result", {})
        except Exception:
            continue
        n += 1 if ch in r else 0
    return n


def plan(spec, sp, only=None, force_volume=False):
    """[(channel, action)] with action "publish", "done <url>" or "capped": what a run would do."""
    res = spec.get("result", {})
    out = []
    for c in CHANNELS:
        if not spec.get(c) or (only is not None and c not in only):
            continue
        if c in OPT_IN and not (only and c in only):
            continue
        if c in res:
            out.append((c, f"done {res[c].get('url') or res[c].get('post')}"))
        elif c in CAP and not force_volume and used_today(sp, c) >= CAP[c]:
            out.append((c, "capped"))
        else:
            out.append((c, "publish"))
    return out


def missing_media(spec):
    """Media named by the spec and absent from the working folder."""
    names = list(spec.get("images") or []) + [spec[k] for k in ("video", "cover") if spec.get(k)]
    return [n for n in names if not (pathlib.Path(n) if pathlib.Path(n).is_absolute() else HERE / n).is_file()]


def problems(spec):
    """FIX-1f: what a platform would refuse, on the channels still to publish (social/validate_spec.py)."""
    return validate_spec.check(spec, HERE, pending_only=True)


def dry_run(spec, sp, only, force_volume):
    print("DRY RUN", sp.name, "- nothing is uploaded, published or written")
    for c, action in plan(spec, sp, only, force_volume):
        print(f"  {c}: {action}")
    miss = missing_media(spec)
    print("  media:", "all present" if not miss else "MISSING " + ", ".join(miss))
    ig = spec.get("instagram") or {}
    if ig.get("collaborators") is not None or ig.get("trial") is not None:     # SOC-W5
        trial, warnings = ig_extras(spec)
        print("  instagram.collaborators:", ig.get("collaborators"), "| instagram.trial:", ig.get("trial"),
              "->", f"trial_params {trial}" if trial else "no trial_params")
        for w in warnings:
            print("  WARNING " + w)
    bad = problems(spec)
    print("  spec:", "valid" if not bad else "INVALID")
    for _, reason in bad:
        print("    " + reason)
    return 1 if miss or bad else 0


def check_insights():
    """FIX-1g: Threads insights need the app permission threads_manage_insights. The refresh
    (th_refresh_token) keeps the token's permissions; this reads /me/threads_insights once and
    says whether it answers, without printing the token. Exit 0 = data."""
    t = json.loads((RENDERS / "threads_token.json").read_text(encoding="utf-8"))
    try:
        r = requests.get(f"{TH_API}/me/threads_insights", params={"metric": "views,followers_count",
                         "access_token": t["access_token"]}, timeout=30)
        j = r.json()
    except requests.RequestException as e:
        print("threads insights: NO, network:", type(e).__name__)
        return 2
    names = [d.get("name") for d in j.get("data") or []]
    if r.status_code == 200 and names:
        print("threads insights: OK", ", ".join(names))
        return 0
    err = j.get("error") or {}
    print("threads insights: NO", r.status_code, err.get("code"), err.get("message", "")[:120])
    return 1


def main():
    if "--refresh-tokens" in sys.argv:
        refresh_tokens()
        return
    if "--check-insights" in sys.argv:
        sys.exit(check_insights())
    sp = pathlib.Path(sys.argv[1])
    if not sp.is_absolute():
        sp = HERE / sp
    spec = json.loads(sp.read_text(encoding="utf-8"))
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    if "--x" in sys.argv:          # every channel still missing, X included
        only = (only or set(c for c in CHANNELS)) | {"x"}
    force_volume = "--force-volume" in sys.argv
    if "--dry-run" in sys.argv:
        sys.exit(dry_run(spec, sp, only, force_volume))
    bad = problems(spec)
    if bad:                     # before publishing anything (FIX-1f): fix the spec, then run again
        print("ERRORE: spec non valida, nulla pubblicato:")
        for _, reason in bad:
            print("  " + reason)
        sys.exit(1)
    res = spec.setdefault("result", {})

    def save():
        sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")

    want = [c for c, action in plan(spec, sp, only, force_volume) if action == "publish"]
    urls = res.get("_media")
    if any(c in ("instagram", "threads", "x") for c in want) and not urls:
        urls = {"images": [upload_public(p) for p in spec.get("images") or []]}
        if spec.get("video"):
            urls["video"] = upload_public(spec["video"])
            if spec.get("cover"):
                urls["cover"] = upload_public(spec["cover"])
        res["_media"] = urls
        save()
    # Volume cap (playbook "Slots and volumes", owner 10/10): at most 2 posts a day on
    # Instagram and on Threads. The editorial day is the date prefix of the spec file
    # (slots 3 and 4 carry the date of that day's slot 1). Override: --force-volume.
    day = sp.name[:10]
    for c, action in plan(spec, sp, only, force_volume):
        if action.startswith("done"):
            print(c, "già pubblicato:", res[c].get("url") or res[c].get("post"))
            continue
        if action == "capped":
            print(c, f"SALTATO: tetto di {CAP[c]} post al giorno già raggiunto per {day} (playbook, Slots and volumes)")
            res[c + "_skipped"] = f"volume cap {CAP[c]}/day reached for {day}"
            save()
            continue
        out = {"bluesky": lambda: publish_bluesky(spec),
               "instagram": lambda: publish_instagram(spec, urls),
               "threads": lambda: publish_threads(spec, urls),
               "x": lambda: publish_x(spec, urls, save)}[c]()
        out["at"] = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
        res[c] = out
        save()
        print(c, "OK", out.get("url") or out.get("post"))


if __name__ == "__main__":
    main()
