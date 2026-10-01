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
    for label in ("In Most Popular now", "Left Most Popular", "'All'"):
        assert label in HOME, label
    for col in ("Day", "Current VPI &middot; level", "First observed",
                "Highest VPI observed &middot; level", "Days in Most Popular",
                "Left on", "Claim open until"):
        assert f">{col}<" in HOME, col
    assert ".eq('status', 'CLOSED')" in HOME and ".eq('status', 'ACTIVE')" in HOME


def test_the_same_badge_on_the_segment_pages():
    assert "<StatusBadge post={post} />" in HOME and "<StatusBadge post={post} />" in LIST


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
