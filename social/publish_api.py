"""IOSA social publisher: Bluesky, Instagram and Threads through their official APIs.

Usage (from C:\\Work\\iosa-lab\\renders\\social, through the wrapper there):
    python3 publish_api.py queue/<post>.json            # publish every channel still missing
    python3 publish_api.py queue/<post>.json --only bluesky,threads
    python3 publish_api.py queue/<post>.json --dry-run  # say what would go out; no network, no writes

Before publishing anything the spec is checked (social/validate_spec.py, FIX-1f): X over 280
weighted, Bluesky over 300 graphemes or without alt text, Threads over 500, an Instagram caption
over 2,200 characters or 30 hashtags, a named file missing. An invalid spec publishes nothing.
    python3 publish_api.py --refresh-tokens            # extend the Instagram and Threads tokens

The code is versioned in the repo, social/publish_api.py (FIX-1e, 20/10/2026); it works in
renders/social (IOSA_SOCIAL_WORK, set by the wrapper): queue, media, credentials stay there.

Post spec (JSON):
{
  "id": "2026-10-10-ml7",
  "images": ["2026-10-10-breakout-ml7.jpg"],        # JPEG, 1 to 10 (carousel when > 1)
  "video": null, "cover": null,                     # a Reel/video instead of images (mp4 + jpg cover)
  "bluesky":   {"text": "...", "alt": "..."},       # null to skip
  "instagram": {"caption": "...", "user_tags": [{"username": "x", "x": 0.5, "y": 0.8}]},
  "threads":   {"text": "...", "topic_tag": "YouTube Creators"}
}
Results (links and ids) are written back into the spec under "result". A channel that already has a
result is never published again, so a retry cannot double-post.

Credentials are read from renders/*.txt|json and backend/.env and are never printed.
Media go to the public Supabase Storage bucket "social" (the APIs fetch images and videos by URL).
"""
import json, os, re, sys, time, datetime, mimetypes, pathlib, urllib.parse
import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # the repo: social.paths
from social import paths, validate_spec

HERE = paths.work()                                        # renders/social: queue and media
RENDERS = paths.renders()                                  # renders: credentials
REPO = paths.REPO                                          # iosa-lab: backend/.env
IG_API = "https://graph.instagram.com/v21.0"
TH_API = "https://graph.threads.net/v1.0"


def env():
    txt = (REPO / "backend" / ".env").read_text(encoding="utf-8")
    return {k: v.strip().strip('"') for k, v in re.findall(r"^([A-Z_]+)=(.*)$", txt, re.M)}


def die(msg):
    print("ERRORE:", msg)
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


def publish_instagram(spec, urls):
    t = json.loads((RENDERS / "instagram_token.json").read_text(encoding="utf-8"))
    tok, uid = t["access_token"], t["user_id"]
    ig = spec["instagram"]
    tags = json.dumps(ig.get("user_tags") or [])
    if spec.get("video"):
        p = {"media_type": "REELS", "video_url": urls["video"], "caption": ig["caption"],
             "share_to_feed": "true", "access_token": tok}
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
        r = requests.post(f"{TH_API}/{uid}/threads", data=p, timeout=60).json()
        if "id" not in r and "topic_tag" in p:          # topic tag refused: retry without it, say so
            print("Threads: topic_tag rifiutato, pubblico senza:", r.get("error", {}).get("message"))
            p = {k: v for k, v in p.items() if k != "topic_tag"}
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
CHANNELS = ("bluesky", "instagram", "threads")


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
        if c in res:
            out.append((c, f"done {res[c].get('url')}"))
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
    bad = problems(spec)
    print("  spec:", "valid" if not bad else "INVALID")
    for _, reason in bad:
        print("    " + reason)
    return 1 if miss or bad else 0


def main():
    if "--refresh-tokens" in sys.argv:
        refresh_tokens()
        return
    sp = pathlib.Path(sys.argv[1])
    if not sp.is_absolute():
        sp = HERE / sp
    spec = json.loads(sp.read_text(encoding="utf-8"))
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
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

    want = [c for c in CHANNELS if spec.get(c) and (only is None or c in only)]
    urls = res.get("_media")
    if any(c in ("instagram", "threads") and c not in res for c in want) and not urls:
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
            print(c, "già pubblicato:", res[c].get("url"))
            continue
        if action == "capped":
            print(c, f"SALTATO: tetto di {CAP[c]} post al giorno già raggiunto per {day} (playbook, Slots and volumes)")
            res[c + "_skipped"] = f"volume cap {CAP[c]}/day reached for {day}"
            save()
            continue
        out = {"bluesky": lambda: publish_bluesky(spec),
               "instagram": lambda: publish_instagram(spec, urls),
               "threads": lambda: publish_threads(spec, urls)}[c]()
        out["at"] = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
        res[c] = out
        save()
        print(c, "OK", out.get("url"))


if __name__ == "__main__":
    main()
