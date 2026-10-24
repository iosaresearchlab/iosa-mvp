"""Reject a post spec that a platform would refuse (FIX-1f, 20/10/2026).

    python social/validate_spec.py <spec.json> [...]     # exit 0 = valid; otherwise the reasons, exit 1

Limits checked, each with the platform's own way of counting:
- X: `x.text` and `x.reply` at most 280, weighted as twitter-text v3 (social/xtext.py: URLs and
  bare domains 23, CJK and emoji 2);
- Bluesky: `bluesky.text` at most 300 graphemes; alt text on every image it carries;
- Threads: `threads.text` at most 500 characters;
- Instagram: `instagram.caption` at most 2,200 characters and 30 hashtags;
- Instagram, optional (SOC-W5): `instagram.collaborators` a list of at most 3 usernames;
  `instagram.trial` true, "MANUAL" or "SS_PERFORMANCE" (a trial reel; on an image post
  publish_api.py ignores it with a warning);
- media: every file the spec names (`images`, `video`, `cover`, `x.card`, `dm.card`) on disk,
  relative to the working folder (renders/social).

publish_api.py runs the same checks, on the channels still to publish, before publishing anything.
"""
import json
import pathlib
import re
import sys
import unicodedata

try:
    from social import paths, xtext
except ImportError:                                   # run as a script from social/
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    from social import paths, xtext

X_MAX, BLUESKY_MAX, THREADS_MAX, IG_CAPTION_MAX, IG_HASHTAGS_MAX = 280, 300, 500, 2200, 30
HASHTAG = re.compile(r"(?:^|(?<=\s))#\w+", re.UNICODE)
IG_COLLABORATORS_MAX = 3                                 # SOC-W5: Instagram's limit
IG_USERNAME = re.compile(r"[A-Za-z0-9._]{1,30}")
IG_TRIAL_STRATEGIES = ("MANUAL", "SS_PERFORMANCE")      # trial_params.graduation_strategy


def graphemes(text: str) -> int:
    """User-perceived characters, as Bluesky counts them: an emoji sequence is one, a combining
    mark or a variation selector joins the character before it, a Hangul syllable built from
    jamo is one."""
    t = unicodedata.normalize("NFC", text or "")
    n = i = 0
    while i < len(t):
        j = xtext._emoji_end(t, i)
        i = j if j > i else i + 1
        while i < len(t) and (unicodedata.category(t[i]) in ("Mn", "Me", "Mc") or t[i] in "‍︎️"
                              or 0x1160 <= ord(t[i]) <= 0x11FF):
            i += 1
        n += 1
    return n


def chars(text: str) -> int:
    return len(unicodedata.normalize("NFC", text or ""))


def media(spec: dict) -> list:
    names = list(spec.get("images") or [])
    names += [spec[k] for k in ("video", "cover") if spec.get(k)]
    names += [(spec.get(k) or {}).get("card") for k in ("x", "dm") if (spec.get(k) or {}).get("card")]
    return list(dict.fromkeys(names))


def check(spec: dict, work: pathlib.Path = None, pending_only: bool = False) -> list:
    """[(channel, reason)] for every limit broken. pending_only: skip the channels the spec's
    result already holds (they went out; a retry cannot change them)."""
    work = work or paths.work()
    done = spec.get("result") or {}
    skip = (lambda c: c in done) if pending_only else (lambda c: False)
    out = []
    x = spec.get("x") or {}
    if x and not skip("x"):
        for part in ("text", "reply"):
            if x.get(part):
                n = xtext.weighted_length(x[part])
                if n > X_MAX:
                    out.append(("x", f"x.{part}: {n} weighted characters (max {X_MAX})"))
    bs = spec.get("bluesky") or {}
    if bs and not skip("bluesky"):
        n = graphemes(bs.get("text", ""))
        if n > BLUESKY_MAX:
            out.append(("bluesky", f"bluesky.text: {n} graphemes (max {BLUESKY_MAX})"))
        if spec.get("images") and not (bs.get("alt") or "").strip():
            out.append(("bluesky", "bluesky.alt: alt text missing for the images"))
    th = spec.get("threads") or {}
    if th and not skip("threads"):
        n = chars(th.get("text", ""))
        if n > THREADS_MAX:
            out.append(("threads", f"threads.text: {n} characters (max {THREADS_MAX})"))
    ig = spec.get("instagram") or {}
    if ig and not skip("instagram"):
        cap = ig.get("caption", "")
        n, h = chars(cap), len(HASHTAG.findall(cap))
        if n > IG_CAPTION_MAX:
            out.append(("instagram", f"instagram.caption: {n} characters (max {IG_CAPTION_MAX})"))
        if h > IG_HASHTAGS_MAX:
            out.append(("instagram", f"instagram.caption: {h} hashtags (max {IG_HASHTAGS_MAX})"))
        col = ig.get("collaborators")
        if col is not None and (not isinstance(col, list) or len(col) > IG_COLLABORATORS_MAX
                                or not all(isinstance(u, str) and IG_USERNAME.fullmatch(u.lstrip("@")) for u in col)):
            out.append(("instagram", f"instagram.collaborators: a list of at most {IG_COLLABORATORS_MAX} usernames"))
        trial = ig.get("trial")
        if trial is not None and trial is not False and trial is not True and trial not in IG_TRIAL_STRATEGIES:
            out.append(("instagram", "instagram.trial: true, false, \"MANUAL\" or \"SS_PERFORMANCE\""))
    for name in media(spec):
        p = pathlib.Path(name)
        if not (p if p.is_absolute() else work / p).is_file():
            out.append(("media", f"{name}: image missing on disk"))
    return out


def main(argv) -> int:
    if not argv:
        sys.exit(__doc__)
    bad = 0
    for a in argv:
        sp = pathlib.Path(a)
        if not sp.is_absolute() and not sp.exists():
            sp = paths.work() / sp
        problems = check(json.loads(sp.read_text(encoding="utf-8")), work=paths.work())
        if problems:
            bad += 1
            print(f"INVALID {sp.name}")
            for _, reason in problems:
                print("  " + reason)
        else:
            print(f"OK {sp.name}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
