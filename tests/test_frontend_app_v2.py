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
