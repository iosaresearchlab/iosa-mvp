"""DOC-1: the root README stays tied to the code it quotes.

docs/08-implementation-plan.md DOC-1. The README is the public front page of
the repository; docs/ is the authority. These checks fail when a value the
README quotes changes in its own file and the README does not follow.
"""

import re
from datetime import datetime
from pathlib import Path

import census
import vpi_core
import vpi_engine

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")


def _repository_table():
    block = README[README.index("## Repository"):]
    block = block[:block.index("\n\n**")] if "\n\n**" in block else block
    return [row for row in block.splitlines() if row.startswith("| `")]


def test_every_path_in_the_repository_table_exists():
    rows = _repository_table()
    assert rows, "no repository table"
    for row in rows:
        first = row.split("|")[1]
        paths = re.findall(r"`([^`]+)`", first)
        assert paths, row
        for p in paths:
            assert (ROOT / p.rstrip("/")).exists(), f"README lists {p}, which does not exist"


def test_the_series_start_is_index_start_date():
    m = re.search(r"The series starts on (\d{1,2} [A-Z][a-z]+ \d{4})", README)
    assert m, "no 'The series starts on ...' sentence"
    day = datetime.strptime(m.group(1), "%d %B %Y").date().isoformat()
    assert day == vpi_core.INDEX_START_DATE


def test_countries_and_categories_are_the_census_ones():
    m = re.search(r"(\d+) countries and (\d+) categories", README)
    assert m, "no 'N countries and M categories'"
    assert int(m.group(1)) == len(census.TARGET_COUNTRIES)
    assert int(m.group(2)) == len(census.CATEGORY_MAP)


def test_the_perimeter_sentence_follows_measured_formats():
    """When Shorts come back the README fails until it is updated."""
    says_long_only = "For now only long-form is measured" in README
    assert says_long_only == (tuple(vpi_engine.MEASURED_FORMATS) == ("LONG",))


def test_nothing_from_the_v1_readme_survives():
    low = README.lower()
    for word in ("tiktok", "suspended", "15 days", "insights", "entered trending", "is removed"):
        assert word not in low, word


def test_the_links_into_docs_resolve():
    for target in re.findall(r"\]\(((?:docs/)[^)#]+)\)", README):
        assert (ROOT / target).exists(), target
