"""T-19: the leaderboard reads day 1 and offers no day selector (02 section 6.3).

The day-1 filter itself is asserted on the API (tests/test_api.py,
test_top10_reads_day_index_1_of_certain_v2_records); here, that the page
uses that endpoint, carries the required labels, and never picks a day.
"""

from pathlib import Path

PAGE = (Path(__file__).resolve().parent.parent / "frontend" / "src" / "app"
        / "leaderboard" / "page.tsx").read_text(encoding="utf-8")


def test_the_ranking_comes_from_the_day1_endpoint():
    assert "/api/analytics/top10" in PAGE


def test_title_and_label():
    assert "Top VPI — first day observed" in PAGE
    assert "VPI on the first day observed in Most Popular. Not age-adjusted." in PAGE
    assert "Highest values observed" in PAGE


def test_no_day_selector_and_no_pooled_average():
    for forbidden in ("setDay", "dayIndex", "avgVpi", "vpiSum", "15d", "24h"):
        assert forbidden not in PAGE, forbidden


def test_timeframes_are_today_7_30_all():
    for t in ("'today'", "'7d'", "'30d'", "'all'"):
        assert t in PAGE
