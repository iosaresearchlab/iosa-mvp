"""T-21: the public methodology text (02 section 6.5), by the plan's greps."""

import subprocess
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


def test_no_trending_anywhere_in_the_frontend():
    assert _grep("trending", "-i") == []


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
