"""Weekly digest, v2: a DRAFT for the owner's review. It never publishes.

    python tools/weekly_digest.py                 # the last 7 complete readings
    python tools/weekly_digest.py --out DIR       # where the draft files go

DIG-1 (owner decision 01/10/2026), replacing archive/backend/weekly_digest.py
(v1: "broke the algorithm", a pooled top 3 by current VPI, a call to action).
Read-only: GET requests to the Supabase REST API with the service key from
backend/.env (never printed); it writes three files to the output directory
(default tools/drafts/, ignored by git) and nothing anywhere else. No YouTube
quota is spent. It lives outside the backend runtime: Render never runs it.

The week is the last 7 readings with a complete census
(ingest_run.census_complete), never before INDEX_START_DATE: earlier readings
are reference states and nothing in them is published. The blocks:
  hook      long-form videos first observed this week, and how many were seen
            in a single reading only (closed after one day in Most Popular);
  3-2-1     by day-1 VPI (the only index every record has, 01 section 4.2)
            within ONE baseline band, rotating each week; band and n stated;
            certain entries only (entry_certain), long-form only;
  #1        if its record has closed: highest VPI observed, views and days in
            Most Popular, together; if still charting: day N, no award;
  limit     one line with its figure: the small-band concentration (the
            day-1 median of the featured band beside the one of the largest
            band, each a figure of its own band) or the share of the week's
            records without a computable baseline;
  close     iosaresearch.org. No call to action.
Outputs: a ~55 s voiceover with timings, the carousel card texts (1080x1080,
the style of assets/social/iosa_cards.html, also written as an HTML file
that reuses that stylesheet), an X post within 280 characters with the link
counted as 23 (X's t.co length).

Likely live streams and re-uploads are FLAGGED, never dropped: the owner
decides. Markers: "LIVE" as a word in capitals, a red circle, "full match",
"en vivo", "ao vivo", "live stream", "replay", "full game"; or a baseline
under 1,000 views.
"""

import argparse
import html
import re
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from vpi_core import INDEX_START_DATE  # noqa: E402  the published series starts here (01 section 1)

SITE = "iosaresearch.org"
X_LIMIT, X_LINK = 280, 23

# The same bands as backend/main.py BASELINE_BANDS (tests/test_weekly_digest.py
# compares them). A figure is never computed across two of them.
BANDS = (
    (0, 100, "<100"),
    (100, 1_000, "100-1k"),
    (1_000, 10_000, "1k-10k"),
    (10_000, 100_000, "10k-100k"),
    (100_000, float("inf"), ">=100k"),
)
BAND_WORDS = {"<100": "under 100 views", "100-1k": "100 to 1,000 views",
              "1k-10k": "1,000 to 10,000 views", "10k-100k": "10,000 to 100,000 views",
              ">=100k": "100,000 views or more"}

# Wording rules (owner, 01/10/2026). Checked on every output before it is
# written; a draft that breaks one is not written.
BANNED = [
    (r"\bentered\b|\benters\b|\bentering\b|\bentry into\b", 'say "first observed", never "entered"'),
    (r"\btrending\b", '"trending" is not what we read'),
    (r"broke the algorithm|mind[- ]?blowing|insane|crazy|massive|explod|viral hit|shocking"
     r"|unbelievable|incredible|record-breaking|biggest|best\b|top creator|smashed|blew up",
     "no superlatives"),
    (r"\bsubscribe\b|\bfollow us\b|\bcomment\b|\bdrop your\b|\blink in bio\b|\bclick\b|\bcheck out\b"
     r"|\bdon'?t miss\b|\bshare this\b|\btag a\b|\bsign up\b|\bvisit\b", "no call to action"),
    (r"\bshorts?\b", "long-form only"),
    (r"age[- ]adjusted(?! )", None),          # allowed only as "not age-adjusted": checked below
]
LIVE_MARKERS = re.compile(r"🔴|full match|en vivo|ao vivo|live ?stream|\breplay\b|full game",
                          re.IGNORECASE)
LIVE_CAPS = re.compile(r"\bLIVE\b")
REUPLOAD_BASELINE = 1_000


class WordingError(ValueError):
    """A draft broke a wording rule: nothing is written."""


def band_of(baseline):
    if baseline is None:
        return None
    b = float(baseline)
    for lo, hi, name in BANDS:
        if lo <= b < hi:
            return name
    return None


def fmt_int(n):
    return f"{int(round(float(n))):,}"


def fmt_vpi(v):
    v = float(v)
    return f"{v:,.0f}x" if v >= 100 else f"{v:.1f}x"


def flags_of(rec):
    """Reasons the owner may want to exclude a record. Never a filter."""
    out = []
    title = rec.get("content_text") or ""
    if LIVE_CAPS.search(title) or LIVE_MARKERS.search(title):
        out.append("likely live stream or replay (title)")
    if rec.get("baseline_score") is not None and float(rec["baseline_score"]) < REUPLOAD_BASELINE:
        out.append(f"baseline under {REUPLOAD_BASELINE:,} views (possible re-upload or new channel)")
    return out


def check_wording(text):
    """The rule broken, or None. "not age-adjusted" is the only allowed use."""
    low = text.lower()
    for pattern, why in BANNED:
        if why is None:
            continue
        m = re.search(pattern, low)
        if m:
            return f"{why}: {m.group(0)!r}"
    if re.search(r"age[- ]adjusted", low) and not re.search(r"not age[- ]adjusted", low):
        return 'only "not age-adjusted" may be said'
    return None


def x_length(text):
    """Length as X counts it: every URL is 23 characters."""
    return len(re.sub(r"(https?://)?iosaresearch\.org\S*", "x" * X_LINK, text))


def featured_band(week_end, counts):
    """The band of the week: rotating by ISO week, the next one with at least
    3 day-1 VPIs if the rotation lands on a thinner band (said in the draft)."""
    order = [b[2] for b in BANDS]
    start = week_end.isocalendar().week % len(order)
    for i in range(len(order)):
        band = order[(start + i) % len(order)]
        if counts.get(band, 0) >= 3:
            return band, order[start], i > 0
    return None, order[start], True


def build(days, records):
    """The draft from the week's readings and its long-form records.

    records: dicts with author_handle, author_name, content_text, post_url,
    baseline_score, baseline_rule, status, days_charting, day_n, vpi_max,
    views_max, entered_on, left_on, entry_certain, and day1_vpi / day1_views
    (post_daily at day_index 1; None when the baseline was not computable).
    """
    days = sorted(str(d)[:10] for d in days if str(d)[:10] >= INDEX_START_DATE)
    if not days:
        raise ValueError(f"no complete reading on or after {INDEX_START_DATE}")
    week_start, week_end = date.fromisoformat(days[0]), date.fromisoformat(days[-1])
    week = [r for r in records if str(r["entered_on"])[:10] in days]
    single = [r for r in week if r.get("status") == "CLOSED" and r.get("days_charting") == 1]
    no_baseline = [r for r in week if r.get("baseline_rule") == "not_computable"]
    measured = [r for r in week if r.get("entry_certain") and r.get("day1_vpi") is not None]

    by_band = {}
    for r in measured:
        by_band.setdefault(band_of(r["baseline_score"]), []).append(r)
    counts = {b: len(v) for b, v in by_band.items()}
    band, rotated_to, moved = featured_band(week_end, counts)
    ranked = sorted(by_band.get(band, []), key=lambda r: float(r["day1_vpi"]), reverse=True)
    top = ranked[:3]
    medians = {b: statistics.median(float(r["day1_vpi"]) for r in v) for b, v in by_band.items()}

    small = band in ("<100", "100-1k", "1k-10k")
    if band and small and ">=100k" in medians and band != ">=100k":
        limit = (f"Small channels need a far higher VPI to reach Most Popular: this week the median "
                 f"day-1 VPI was {fmt_vpi(medians[band])} for channels with a baseline of "
                 f"{BAND_WORDS[band]}, and {fmt_vpi(medians['>=100k'])} for channels with "
                 f"{BAND_WORDS['>=100k']}.")
        limit_figure = {"kind": "band medians", band: medians[band], ">=100k": medians[">=100k"]}
    else:
        share = 100 * len(no_baseline) / len(week) if week else 0
        limit = (f"{len(no_baseline):,} of the week's {len(week):,} long-form videos "
                 f"({share:.0f}%) have no VPI: their channel had too few long-form videos in the "
                 f"7 to 90 days before them for a baseline.")
        limit_figure = {"kind": "share without a computable baseline", "share": share}

    def who(r):
        return r.get("author_handle") or r.get("author_name") or "a channel"

    def position_1(r):
        if r.get("status") == "CLOSED" and r.get("vpi_max") is not None:
            return (f"At number 1, {who(r)}: {fmt_vpi(r['day1_vpi'])} on its first day observed. "
                    f"It has since left Most Popular, with a highest VPI observed of "
                    f"{fmt_vpi(r['vpi_max'])}, {fmt_int(r['views_max'])} views and "
                    f"{r['days_charting']} day{'s' if r['days_charting'] != 1 else ''} in Most Popular.")
        return (f"At number 1, {who(r)}: {fmt_vpi(r['day1_vpi'])} on its first day observed, "
                f"and still in Most Popular, day {r.get('day_n') or '?'}.")

    hook = (f"This week we first observed {len(week):,} long-form videos in YouTube's Most Popular "
            f"charts. {len(single):,} of them were seen in a single reading only.")
    band_line = (f"Ranked by VPI on the first day observed, among channels with a baseline of "
                 f"{BAND_WORDS[band]}: {len(ranked):,} videos.") if band else \
        "No baseline band had three day-1 VPIs this week: no ranking."
    lines = []
    if len(top) >= 3:
        lines.append(f"At number 3, {who(top[2])}: {fmt_vpi(top[2]['day1_vpi'])}. "
                     f"At number 2, {who(top[1])}: {fmt_vpi(top[1]['day1_vpi'])}.")
        lines.append(position_1(top[0]))
    close = f"Views divided by the channel's own median. Every number is at {SITE}."

    script = [
        ("0:00", "0:08", hook),
        ("0:08", "0:14", band_line),
        ("0:14", "0:26", lines[0] if lines else ""),
        ("0:26", "0:42", lines[1] if len(lines) > 1 else ""),
        ("0:42", "0:51", limit),
        ("0:51", "0:55", close),
    ]
    words = sum(len(t.split()) for _, _, t in script)

    cards = [
        {"eyebrow": f"Weekly digest · {week_start:%d %b} – {week_end:%d %b %Y}",
         "title": f"{len(week):,} long-form videos first observed in Most Popular.",
         "rows": [("seen in a single reading only", f"{len(single):,}"),
                  ("readings with a complete census", f"{len(days)}")]},
    ]
    if band:
        cards.append({"eyebrow": f"Day-1 VPI · baseline {band} · n = {len(ranked):,}",
                      "title": f"Ranked within one band: channels with a baseline of {BAND_WORDS[band]}.",
                      "rows": [(f"#{i + 1} {who(r)}", fmt_vpi(r["day1_vpi"])) for i, r in enumerate(top)]})
    if top:
        r = top[0]
        rows = [("day-1 VPI", fmt_vpi(r["day1_vpi"])), ("baseline", fmt_int(r["baseline_score"]))]
        if r.get("status") == "CLOSED" and r.get("vpi_max") is not None:
            rows += [("highest VPI observed", fmt_vpi(r["vpi_max"])), ("views", fmt_int(r["views_max"])),
                     ("days in Most Popular", str(r["days_charting"]))]
        else:
            rows += [("status", f"in Most Popular, day {r.get('day_n') or '?'}")]
        cards.append({"eyebrow": f"#1 · baseline {band}", "title": who(r), "rows": rows})
    cards.append({"eyebrow": "Limit", "title": limit, "rows": []})
    cards.append({"eyebrow": "VPI", "title": "Views divided by the channel's own median.",
                  "rows": [("baseline", "long-form videos published 7-90 days before"),
                           ("measured", "not age-adjusted")], "foot": SITE})

    x_post = (f"Week of {week_start:%d %b}: {len(week):,} long-form videos first observed in Most Popular, "
              f"{len(single):,} for one reading only.")
    if top:
        x_post += (f" Day-1 VPI, baseline {band} (n={len(ranked):,}): #1 {who(top[0])} "
                   f"{fmt_vpi(top[0]['day1_vpi'])}.")
    x_post += f" https://{SITE}"
    if x_length(x_post) > X_LIMIT:
        x_post = (f"{len(week):,} long-form videos first observed in Most Popular this week. "
                  f"Day-1 VPI, baseline {band}: #1 {fmt_vpi(top[0]['day1_vpi']) if top else '-'}. "
                  f"https://{SITE}")

    flagged = [{"handle": who(r), "title": r.get("content_text"), "url": r.get("post_url"),
                "position": ranked.index(r) + 1, "flags": flags_of(r)}
               for r in ranked[:10] if flags_of(r)]

    draft = {
        "week": days, "band": band, "band_rotation": rotated_to, "band_moved": moved,
        "n_band": len(ranked), "records": len(week), "single_reading": len(single),
        "top": [{"position": i + 1, "handle": who(r), "title": r.get("content_text"),
                 "day1_vpi": float(r["day1_vpi"]), "band": band, "flags": flags_of(r)}
                for i, r in enumerate(top)],
        "limit": limit, "limit_figure": limit_figure,
        "script": script, "script_words": words,
        "script_seconds_estimate": round(words / 2.5),
        "cards": cards, "x_post": x_post, "x_length": x_length(x_post), "flagged": flagged,
    }
    for text in all_texts(draft):
        broken = check_wording(text)
        if broken:
            raise WordingError(f"{broken} in: {text}")
    if draft["x_length"] > X_LIMIT:
        raise WordingError(f"X post is {draft['x_length']} characters")
    return draft


def all_texts(draft):
    """Every sentence the draft would put in public, handles and titles aside."""
    out = [t for _, _, t in draft["script"]] + [draft["x_post"], draft["limit"]]
    for c in draft["cards"]:
        out += [c["eyebrow"], c["title"]] + [k for k, _ in c["rows"]] + [v for _, v in c["rows"]]
    names = {t["handle"] for t in draft["top"]}
    for n in names:   # a channel's own name is not our wording
        out = [o.replace(n, "") for o in out]
    return out


# --- rendering -----------------------------------------------------------------


def markdown(draft):
    lines = [f"# Weekly digest — DRAFT for review, {draft['week'][0]} – {draft['week'][-1]}", "",
             "Not published. Nothing here leaves this file until the owner decides.", "",
             f"- Readings (complete census): {', '.join(draft['week'])}",
             f"- Long-form records first observed: {draft['records']:,}; single reading only: "
             f"{draft['single_reading']:,}",
             f"- Band of the week: {draft['band']} (rotation pointed to {draft['band_rotation']}"
             f"{'; moved: fewer than 3 day-1 VPIs there' if draft['band_moved'] else ''}), "
             f"n = {draft['n_band']:,}", ""]
    if draft["flagged"]:
        lines += ["## Flagged — the owner decides whether to exclude", ""]
        for f in draft["flagged"]:
            lines.append(f"- #{f['position']} {f['handle']} — {f['title']} — {', '.join(f['flags'])} — {f['url']}")
        lines.append("")
    lines += [f"## Voiceover (~55 s; {draft['script_words']} words, "
              f"~{draft['script_seconds_estimate']} s at 2.5 words a second, an estimate)", ""]
    lines += [f"[{a} – {b}] {t}" for a, b, t in draft["script"] if t] + [""]
    lines += ["## Carousel (1080x1080, assets/social style)", ""]
    for i, c in enumerate(draft["cards"], 1):
        lines.append(f"**Card {i}** — {c['eyebrow']}")
        lines.append(f"> {c['title']}")
        lines += [f"> {k}: {v}" for k, v in c["rows"]]
        lines.append("")
    lines += [f"## X post ({draft['x_length']}/280, link counted as 23)", "", draft["x_post"], ""]
    return "\n".join(lines)


def cards_html(draft, stylesheet):
    """The cards in the house style: the <style> of assets/social/iosa_cards.html."""
    sections = []
    for i, c in enumerate(draft["cards"], 1):
        rows = "".join(f'<div class="row"><span class="k">{html.escape(k)}</span>'
                       f'<span class="v">{html.escape(v)}</span></div>' for k, v in c["rows"])
        sections.append(
            f'<section class="card" id="c{i}"><div class="eyebrow"><b>IOSA</b> '
            f'<span>{html.escape(c["eyebrow"])}</span></div><div class="mid">'
            f'<h1>{html.escape(c["title"])}</h1>{f"<div class=ledger>{rows}</div>" if rows else ""}</div>'
            f'<footer><div><span class="mark">IOSA</span><span class="sub">INSTITUTE FOR OPEN SOCIAL '
            f'ANALYTICS</span></div><div>{SITE}</div></footer></section>')
    script = ("<script>document.body.dataset.c=new URLSearchParams(location.search).get('c')||'1';"
              "</script>")
    extra = "<style>" + " ".join(f"body[data-c=\"{i}\"] #c{i}{{display:flex}}"
                                 for i in range(1, len(draft["cards"]) + 1)) + "</style>"
    return (f"<!-- DRAFT for review, not published. Render at 1080x1080 like render_cards.mjs, ?c=1..{len(draft['cards'])} -->\n"
            f"<title>IOSA weekly digest {draft['week'][-1]} (draft)</title>\n{stylesheet}\n{extra}\n<body>"
            + "".join(sections) + script + "</body>")


def house_stylesheet():
    src = (ROOT / "assets" / "social" / "iosa_cards.html").read_text(encoding="utf-8")
    head = src[:src.index("</style>") + len("</style>")]
    return head[head.index("<link"):]


# --- production, read-only -----------------------------------------------------


def _env():
    out = {}
    for line in (ROOT / "backend" / ".env").read_text(encoding="utf-8").splitlines():
        k, _, v = line.strip().partition("=")
        out[k] = v.strip().strip('"')
    return out


def read_week():
    import requests

    e = _env()
    url, svc = e["SUPABASE_URL"], e["SUPABASE_SERVICE_KEY"]
    hdr = {"apikey": svc, "Authorization": f"Bearer {svc}"}

    def get(path, params, rng=None):
        h = dict(hdr, **({"Range": rng} if rng else {}))
        r = requests.get(f"{url}/rest/v1/{path}", headers=h, params=params, timeout=60)
        r.raise_for_status()
        return r.json()

    days = [r["day"] for r in get("ingest_run", {"select": "day", "census_complete": "is.true",
                                                 "day": f"gte.{INDEX_START_DATE}",
                                                 "order": "day.desc", "limit": "7"})]
    cols = ("id,author_handle,author_name,content_text,post_url,baseline_score,baseline_rule,status,"
            "days_charting,vpi_max,views_max,entered_on,left_on,entry_certain,"
            "post_daily(day_index,vpi_ratio,views)")
    records, off = [], 0
    while True:
        batch = get("posts", {"select": cols, "method_version": "eq.v2", "format": "eq.LONG",
                              "hidden": "is.false", "entered_on": f"in.({','.join(days)})",
                              "order": "id"}, f"{off}-{off + 999}")
        records += batch
        if len(batch) < 1000:
            break
        off += 1000
    for r in records:
        series = r.pop("post_daily") or []
        d1 = next((d for d in series if d["day_index"] == 1), None)
        r["day1_vpi"] = d1["vpi_ratio"] if d1 else None
        r["day1_views"] = d1["views"] if d1 else None
        r["day_n"] = len(series) if r["status"] == "ACTIVE" else r["days_charting"]
    return days, records


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "tools" / "drafts"))
    a = ap.parse_args(argv)
    days, records = read_week()
    if len(days) < 7:
        print(f"only {len(days)} complete readings so far: the draft covers those", file=sys.stderr)
    draft = build(days, records)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"digest_{draft['week'][-1]}"
    (out / f"{stem}.md").write_text(markdown(draft), encoding="utf-8")
    (out / f"{stem}_cards.html").write_text(cards_html(draft, house_stylesheet()), encoding="utf-8")
    print(f"DRAFT written: {out / stem}.md and {stem}_cards.html (nothing published)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
