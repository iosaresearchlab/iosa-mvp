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


def test_fmt1_the_public_text_uses_youtubes_definition_of_a_short():
    """FMT-1 (01 section 1.1): no page says long-form = over 3 minutes any more."""
    footer = (SRC / "components" / "SiteFooter.tsx").read_text(encoding="utf-8")
    for name, text in (("home", HOME), ("modal", MODAL), ("footer", footer)):
        assert "over 3 minutes" not in text and "over 180 seconds" not in text, name
    assert HOME.count("long-form videos only (not Shorts, as YouTube defines them)") == 1
    assert HOME.count("long-form videos (not Shorts, as YouTube defines them)") == 1
    assert "long-form videos (not Shorts, as YouTube defines them)" in footer
    assert "long-form videos (YouTube&apos;s definition: everything that is not a Short)" in MODAL
    flat = " ".join(MODAL.split())
    assert ("everything that is not a Short, as YouTube defines it: a Short is square or vertical "
            "and up to 3 minutes") in flat
    assert "Until 4 October 2026 the split was by duration only (up to 180 seconds = Short)." in flat
