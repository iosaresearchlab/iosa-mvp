"""T-21: the public methodology text (02 section 6.5), by the plan's greps."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "src"
MODAL = (SRC / "components" / "MetodologiaModal.tsx").read_text(encoding="utf-8")


def _grep(pattern, *flags):
    hits = []
    for p in SRC.rglob("*.ts*"):
        text = p.read_text(encoding="utf-8")
        hay = text.lower() if "-i" in flags else text
        if (pattern.lower() if "-i" in flags else pattern) in hay:
            hits.append(str(p.relative_to(ROOT)))
    return hits


# The check bans claims, not a word (reformulated 25/09/2026, Migert).
# A level label such as "Lvl 4 - Trending" and the TrendingUp icon carry no
# claim about YouTube's chart and are allowed.
ENTERED_TRENDING = re.compile(
    r"\b(enter(s|ed|ing)?|entry\s+(in|into)|land(s|ed)?\s+(on|in)|made|hit(s)?|reach(es|ed)?"
    r"|appear(s|ed)?\s+(on|in)|featured\s+(on|in)|on|in|into)\s+(the\s+)?(youtube(['’]s)?\s+)?trending\b",
    re.I)
TRENDING_AS_POPULATION = re.compile(
    r"\btrending\s+(page|tab|list|chart|charts|feed|section|videos?|shorts|content|population)\b"
    r"|\byoutube(['’]s)?\s+trending\b",
    re.I)
# "popular" may only appear as the proper name of what we read. Popularity is
# absolute views; VPI is performance against the channel's own baseline.
POPULAR_NOT_THE_NAME = re.compile(r"(?<![Mm]ost )(?<!MOST )\bpopular(ity)?\b", re.I)
MOST_POPULAR_AS_A_VERDICT = re.compile(r"\bMost Popular\s+(videos?|creators?|content|shorts|channels?)\b", re.I)
LOWERCASE_NAME = re.compile(r"\bmost popular\b")


def _copy(path):
    """The file's text without comments: the claims that reach a reader."""
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"\{/\*.*?\*/\}", "", text, flags=re.S)
    return re.sub(r"(^|\s)//[^\n]*", r"\1", text)


def _claims(pattern):
    hits = []
    for p in SRC.rglob("*.ts*"):
        for m in pattern.finditer(_copy(p)):
            hits.append(f"{p.relative_to(ROOT)}: {m.group(0)!r}")
    return hits


def test_no_copy_says_a_video_entered_trending():
    assert _claims(ENTERED_TRENDING) == []


def test_no_copy_treats_the_retired_trending_page_as_the_population():
    assert _claims(TRENDING_AS_POPULATION) == []


def test_popular_is_only_the_proper_name_of_the_charts():
    assert _claims(POPULAR_NOT_THE_NAME) == []
    assert _claims(MOST_POPULAR_AS_A_VERDICT) == []
    assert _claims(LOWERCASE_NAME) == []


def test_most_popular_names_what_we_read():
    for page in ("components/MetodologiaModal.tsx", "app/page.tsx", "app/leaderboard/page.tsx"):
        assert "Most Popular" in _copy(SRC / page), page


def test_the_checks_catch_what_they_are_for():
    """Negative controls: each pattern fires on the claim it bans, not on a label."""
    assert ENTERED_TRENDING.search("This video entered Trending in Italy")
    assert ENTERED_TRENDING.search("spotted on YouTube's trending")
    assert TRENDING_AS_POPULATION.search("we read the Trending page")
    assert POPULAR_NOT_THE_NAME.search("the most popular videos by VPI") is None  # 'most ' precedes
    assert LOWERCASE_NAME.search("the most popular videos by VPI")
    assert POPULAR_NOT_THE_NAME.search("a measure of popularity")
    assert MOST_POPULAR_AS_A_VERDICT.search("the Most Popular videos of the week")
    for allowed in ("Lvl 4 - Trending", "<TrendingUp className", "YouTube's Most Popular charts",
                    "DAYS IN MOST POPULAR"):
        for pattern in (ENTERED_TRENDING, TRENDING_AS_POPULATION, POPULAR_NOT_THE_NAME,
                        MOST_POPULAR_AS_A_VERDICT, LOWERCASE_NAME):
            assert not pattern.search(allowed), (pattern.pattern, allowed)


def test_the_censoring_sentence_is_gone():
    assert _grep("VPI ≤ 1.0x is excluded") == []
    assert "1.0x is excluded" not in MODAL and "excluded from indexing" not in MODAL


def test_the_two_estimand_sentences_verbatim():
    first = ("VPI is cumulative and age-dependent. It is recalculated daily while the video remains\n"
             "            in the observed Most Popular chart, and is interpreted together with the video&apos;s\n"
             "            age and its days observed in the chart.")
    second = ("VPI is not age-adjusted: values observed at different video ages are not directly\n"
              "            comparable as age-independent measures of performance.")
    assert first in MODAL and second in MODAL


def test_most_popular_population_start_date_and_reading_time():
    for needed in ("Most Popular", "34 countries", "23:59 UTC", "7 and 90 days", "frozen",
                   "DATA_INIZIO_INDICE", "set by the project owner"):
        assert needed in MODAL, needed
    assert "15-Day" not in MODAL and "15-day" not in MODAL
