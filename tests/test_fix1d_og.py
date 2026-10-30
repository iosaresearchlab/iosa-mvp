"""FIX-1d (20/10/2026): link previews carry the record, without ISR writes.

The live check is tests/check_og.py, run after the deploy."""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "frontend" / "src" / "app"
CARD = ROOT / "frontend" / "src" / "lib" / "og-card.tsx"
ROUTES = ["claim/[token]", "creators/[handle]"]


def _check_og():
    spec = importlib.util.spec_from_file_location("check_og", ROOT / "tests" / "check_og.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_both_pages_have_their_own_card_for_og_and_x():
    for route in ROUTES:
        for name in ("opengraph-image.tsx", "twitter-image.tsx"):
            src = (APP / route / name).read_text(encoding="utf-8")
            assert "cardDelRecord(" in src, (route, name)
            # No ISR write (OPS-1): dynamic, never revalidated, never prerendered.
            assert "export const dynamic = 'force-dynamic'" in src, (route, name)
            assert "revalidate" not in src and "generateStaticParams" not in src, (route, name)


def test_the_card_sets_its_own_cache_and_never_uses_chromium():
    src = CARD.read_text(encoding="utf-8")
    assert "'Cache-Control': 'public, max-age=86400, immutable'" in src
    assert "from 'next/og'" in src
    assert "playwright" not in src.lower() and "chromium" not in re.sub(r"//.*|/\*.*?\*/|\*.*", "", src).lower()


def test_the_card_states_the_reading_date():
    src = CARD.read_text(encoding="utf-8")
    assert "This one: ${views}" in src and "(as of ${quando})" in src
    assert "Usually ${formatCountFull(r.baseline_score)} views." in src
    # The same reads as the pages.
    assert ".from('public_records')" in src and "rpc('claim_record_v1'" in src
    creator = (APP / "creators/[handle]" / "opengraph-image.tsx").read_text(encoding="utf-8")
    assert "recordDelCreator(" in creator


def test_no_page_of_a_record_pins_the_site_image():
    page = (APP / "creators/[handle]" / "page.tsx").read_text(encoding="utf-8")
    assert "/og-image.png" not in page


def test_site_description_is_the_positioning():
    layout = (APP / "layout.tsx").read_text(encoding="utf-8")
    assert ("How far a YouTube video beat its own channel's usual views, read every day in "
            "YouTube's Most Popular charts of 34 countries.") in layout
    assert "Independent audit of social media metrics" not in layout


def test_preview_crawlers_may_read_claim_pages_search_engines_may_not():
    robots = (APP / "robots.ts").read_text(encoding="utf-8")
    assert "disallow: ['/claim/']" in robots
    for bot in ("Twitterbot", "facebookexternalhit", "Bluesky Cardyb"):
        assert f"'{bot}'" in robots


def test_robots_parser_of_the_live_check():
    m = _check_og()
    closed = "User-Agent: *\nAllow: /\nDisallow: /claim/\n"
    assert not m.twitterbot_may_read_claims(closed)
    assert m.twitterbot_may_read_claims(closed + "\nUser-Agent: Twitterbot\nUser-Agent: Slackbot\nAllow: /\n")


def test_no_page_inherits_the_home_page_as_its_og_url():
    """FIX-1d (20/10/2026): the root layout set og:url to the home page, so a
    claim link announced itself as https://iosaresearch.org to preview
    fetchers (Bluesky's card service echoed it). Only a page that knows its
    own address sets og:url."""
    layout = (ROOT / "frontend" / "src" / "app" / "layout.tsx").read_text(encoding="utf-8")
    og = layout[layout.index("openGraph: {"):]
    og = og[:og.index("},\n  twitter")]
    assert "url: SITE_URL" not in og
    creator = (ROOT / "frontend" / "src" / "app" / "creators" / "[handle]" / "page.tsx").read_text(encoding="utf-8")
    assert "url: `${SITO}/creators/${handle}`" in creator


def test_isr_writes_are_cut_where_they_come_from(tmp_path):
    """FIX-1d (23/10/2026): creator pages were 4.8K of ~4.9K ISR writes in 12 h. They keep
    24 h, QlyzeBot may not crawl, and a commit outside frontend/ does not deploy (a
    deploy starts the ISR cache again)."""
    import json, re, shutil, subprocess
    front = ROOT / "frontend"
    page = (front / "src" / "app" / "creators" / "[handle]" / "page.tsx").read_text(encoding="utf-8")
    # OPS-4 (30/10/2026): no ISR at all now; held by tests/test_ops4_isr.py
    assert re.search(r"^export const dynamic = 'force-dynamic';", page, re.M)
    robots = (front / "src" / "app" / "robots.ts").read_text(encoding="utf-8")
    assert "userAgent: 'QlyzeBot',\n        disallow: '/'," in robots
    assert json.loads((front / "vercel.json").read_text())["ignoreCommand"] == "bash scripts/vercel-ignore.sh"
    # the script against a throwaway repo: frontend/ unchanged -> 0 (skip), changed -> 1
    repo = tmp_path / "r"
    (repo / "frontend" / "scripts").mkdir(parents=True)
    shutil.copy(front / "scripts" / "vercel-ignore.sh", repo / "frontend" / "scripts" / "vercel-ignore.sh")
    (repo / "backend").mkdir()
    g = lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
    g("init", "-q"); g("config", "user.email", "t@t"); g("config", "user.name", "t")
    g("add", "-A"); g("commit", "-qm", "a"); first = g("rev-parse", "HEAD")
    (repo / "backend" / "x.py").write_text("1"); g("add", "-A"); g("commit", "-qm", "b")
    run = lambda prev: subprocess.run(["bash", "scripts/vercel-ignore.sh"], cwd=repo / "frontend",
                                      env={"PATH": "/usr/bin:/bin", "VERCEL_GIT_PREVIOUS_SHA": prev}).returncode
    assert run(first) == 0          # only backend/ changed: skip
    (repo / "frontend" / "y.ts").write_text("1"); g("add", "-A"); g("commit", "-qm", "c")
    assert run(first) == 1          # frontend/ changed: build
    assert run("") == 1 and run("0" * 40) == 1     # unknown previous commit: build
