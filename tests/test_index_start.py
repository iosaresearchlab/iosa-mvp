"""Owner decision 27/09/2026: nights 0 and 1 are reference-only; the published
series starts on the first run that passes tests/check_run.py. One date, in
three places, and every public read of posts is floored by it."""

import re
from pathlib import Path

import vpi_core as core

ROOT = Path(__file__).resolve().parent.parent
TS = (ROOT / "frontend" / "src" / "lib" / "index-start.ts").read_text(encoding="utf-8")
DOC = (ROOT / "docs" / "01-methodology-protocol.md").read_text(encoding="utf-8")


def _ts_date():
    m = re.search(r"INDEX_START_DATE: string \| null = (null|'(\d{4}-\d{2}-\d{2})');", TS)
    return m.group(2)


def test_backend_frontend_and_protocol_carry_the_same_date():
    doc = re.search(r"\*\*The series begins on day 1\.\*\* The index starts on `([^`]+)`", DOC).group(1)
    assert _ts_date() == core.INDEX_START_DATE
    assert doc == (core.INDEX_START_DATE or "YYYY-MM-DD")


def test_nights_0_and_1_are_never_published():
    assert core.series_floor() > "2026-09-26"


def test_every_public_read_of_posts_is_floored():
    src = ROOT / "frontend" / "src"
    for p in src.rglob("*.ts*"):
        text = p.read_text(encoding="utf-8")
        if "[token]" in str(p):
            continue                             # a claim page resolves one record by token
        for m in re.finditer(r"\.from\('posts'\)", text):
            chain = text[m.start():m.start() + 400]
            assert "SERIES_FLOOR" in chain, f"{p.relative_to(ROOT)}: unfloored read of posts"
