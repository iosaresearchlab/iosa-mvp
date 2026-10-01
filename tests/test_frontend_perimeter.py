"""27/09/2026: the perimeter is long-form only, and the front page says so."""

from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "frontend" / "src"
HOME = (SRC / "app" / "page.tsx").read_text(encoding="utf-8")
BOARD = (SRC / "app" / "leaderboard" / "page.tsx").read_text(encoding="utf-8")
MODAL = (SRC / "components" / "MetodologiaModal.tsx").read_text(encoding="utf-8")


def test_the_front_page_states_it_before_everything_else():
    notice = HOME.index("data-perimeter-notice")
    assert notice < HOME.index("WHO WE ARE") and notice < HOME.index('<HomeArchive')
    block = HOME[notice:notice + 900]
    assert "long-form videos only" in block and "Shorts are not measured" in block


def test_the_methodology_says_it_plainly():
    assert "For now the index does not measure Shorts." in MODAL
    assert "never compared or pooled" in MODAL


def test_no_ranking_pools_the_two_formats():
    assert 'value="ALL">Shorts and long-form' not in BOARD
    assert "params.set('format', formato)" in BOARD
