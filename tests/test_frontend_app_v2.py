"""Public app alignment with v2, owner decisions of 01/10/2026 (02 section 6.7).

String-level checks on the sources: what each page must say, and the words
it must never use. The data behind them is asserted on the database and the
API (test_public_records.py, test_api.py).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "src"


def read(rel):
    return (SRC / rel).read_text(encoding="utf-8")


HOME = read("app/page.tsx")
# UI-3 (01/10/2026): the home table lives in HomeArchive, its state and query in home-query
TABLE = read("components/HomeArchive.tsx") + read("lib/home-query.ts")
STATUS = read("lib/record-status.ts")
LIST = read("components/OutlierList.tsx")


# --- HOME-1 -------------------------------------------------------------------

def test_the_two_status_words():
    assert "`In Most Popular - day ${n}`" in STATUS
    assert "`Left Most Popular - ${giorni(n)}`" in STATUS


def test_status_words_never_qualify_with_hot_trending_or_popular():
    code = re.sub(r"/\*.*?\*/", "", STATUS, flags=re.S)
    code = re.sub(r"//[^\n]*", "", code)
    labels = re.findall(r"`([^`]*)`|'([^']*)'", code)
    for pair in labels:
        text = (pair[0] or pair[1]).lower()
        assert "hot" not in text.split() and "trending" not in text, text
        assert "popular" not in text.replace("most popular", ""), text


def test_one_table_with_three_views_and_dedicated_columns():
    for label in ("'In Most Popular now'", "'Left Most Popular'", "'All'"):
        assert label in TABLE, label
    for col in ("Day", "Current VPI · level", "First observed",
                "Highest VPI observed · level", "Days in Most Popular",
                "Left on", "Claim open until"):
        assert f"titolo: '{col}'" in TABLE, col
    assert "charting: 'ACTIVE', left: 'CLOSED', all: null" in TABLE


def test_the_same_badge_on_the_segment_pages():
    assert "<StatusBadge post={post} />" in TABLE and "<StatusBadge post={post} />" in LIST


# --- CLAIM-2 -------------------------------------------------------------------

CLAIM = read("app/claim/[token]/page.tsx")


def test_the_claim_page_while_charting():
    assert "Measurement in progress. The plaque and the claim window open when the video leaves Most Popular." in CLAIM
    assert "const inMostPopular = isV2 && post.status !== 'CLOSED';" in CLAIM
    # no plaque download and no order unless the plaque is available
    assert "const targaDisponibile = !inMostPopular && !senzaVpi;" in CLAIM
    assert CLAIM.count("{targaDisponibile && (<>") == 1
    assert "{!targaDisponibile ? (" in CLAIM


def test_the_claim_page_after_the_exit():
    assert "`Claim open until ${tokenWindow.openUntil}`" in CLAIM
    assert "'Highest VPI observed in Most Popular \\u2014 independent measurement'" in CLAIM
    assert "isV2 ? post.vpi_max" in CLAIM          # no fallback to the day's VPI after the exit


# --- APP-1 ---------------------------------------------------------------------

def test_insights_is_out_of_the_nav_and_the_sitemap():
    for rel in ("app/page.tsx", "components/PageShell.tsx", "app/layout.tsx", "app/sitemap.ts"):
        assert 'href="/insights"' not in read(rel) and "/insights`" not in read(rel), rel
    assert "indicizzabile: false" in read("app/insights/layout.tsx")


# --- APP-5 ---------------------------------------------------------------------

def test_copy_home_creator_segments_outliers():
    home = read("app/page.tsx")
    assert "long-form videos first observed in YouTube&apos;s Most Popular charts" in home
    assert "short-form" not in home
    creator = read("app/creators/[handle]/page.tsx")
    assert "first observed in Most Popular" in creator
    for word in ("Best result", "strongest", "outperform"):
        assert word.lower() not in creator.lower(), word
    for rel in ("app/outliers/[country]/page.tsx", "app/categories/[category]/page.tsx"):
        page = read(rel)
        assert "Ordered by views, VPI beside each video" in page, rel
        for word in ("strongest", "Top measurement"):
            assert word.lower() not in page.lower(), (rel, word)
    assert "videos charting now" in read("app/outliers/page.tsx")


# --- APP-6 ---------------------------------------------------------------------

def test_the_disclosure_box_is_on_top_vpi_home_and_the_methodology():
    box = read("components/DisclosureBox.tsx")
    assert "/api/analytics/day1-bands?format=LONG" in box
    for rel in ("app/leaderboard/page.tsx", "app/page.tsx", "components/MetodologiaModal.tsx"):
        assert "<DisclosureBox" in read(rel), rel


# --- APP-7 ---------------------------------------------------------------------

def test_no_vpi_says_why_never_no_level():
    assert "'No VPI (baseline not computable)'" in STATUS
    assert "'No VPI yet (baseline still to be read)'" in STATUS
    # "No level" only for a VPI below the first threshold: every list page goes through livelloPubblicato
    for rel in ("components/HomeArchive.tsx", "components/OutlierList.tsx"):
        assert "livelloPubblicato(post)" in read(rel) and "livelloDiRecord" not in read(rel), rel
    assert "without a computable baseline" in read("app/leaderboard/page.tsx")
    assert "without a computable baseline" in read("components/DisclosureBox.tsx")


# --- APP-8 ---------------------------------------------------------------------

def test_creator_pages_keep_closed_records_peak_first():
    lib = read("lib/supabase-server.ts")
    body = lib[lib.index("export async function recordDelCreator"):][:700]
    assert ".eq('status'" not in body
    assert ".order('vpi_max', { ascending: false, nullsFirst: false })" in body
    creator = read("app/creators/[handle]/page.tsx")
    assert "outlierDi" not in creator and creator.count("recordDelCreator(author)") == 2
    sitemap = read("app/sitemap.ts")
    assert ".eq('status', 'ACTIVE')" not in sitemap


# --- APP-9 ---------------------------------------------------------------------

def test_privacy_and_terms_say_v2():
    pub = ROOT / "frontend" / "public"
    for name in ("privacy.html", "terms.html"):
        page = (pub / name).read_text(encoding="utf-8")
        low = page.lower()
        for gone in ("tiktok", "shorts", "short-form", "15 days", "15-day", "expired"):
            assert gone not in low, (name, gone)
        assert "Last updated: 1 October 2026" in page, name
    assert "hidden from public pages" in (pub / "privacy.html").read_text(encoding="utf-8")


# --- UI-4 ----------------------------------------------------------------------

def test_one_header_one_footer_one_logo():
    layout = read("app/layout.tsx")
    assert "<SiteHeader />" in layout and "<SiteFooter />" in layout
    spike = 'd="M1 26.5H6.5L14 8.5L17.5 14"'
    for f in sorted(SRC.rglob("*.tsx")):
        text = f.read_text(encoding="utf-8")
        assert spike not in text, f                                   # no spike-plus-text left
        if f.name not in ("SiteHeader.tsx", "SiteFooter.tsx"):
            assert "<header" not in text and "<footer" not in text, f
    logo = read("components/Logo.tsx")
    assert 'alt="IOSA - Institute for Open Social Analytics"' in logo
    assert "width={larghezza}" in logo and "height={altezza}" in logo
    pub = ROOT / "frontend" / "public" / "brand"
    for name in ("iosa-logo@1x.png", "iosa-logo@2x.png", "iosa-logo@1x.webp", "iosa-logo@2x.webp"):
        assert (pub / name).stat().st_size > 0, name
