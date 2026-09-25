"""T-20: the claim page (02 section 6.4). Expiry from the backend, the three
published figures on the plaque, no expired-measurement copy. A v1 token
still resolving is pinned in tests/test_api.py and test_archive_v1.py."""

from pathlib import Path

PAGE = (Path(__file__).resolve().parent.parent / "frontend" / "src" / "app" / "claim"
        / "[token]" / "page.tsx").read_text(encoding="utf-8")


def test_expiry_comes_from_the_backend():
    assert "/api/claim/${encodeURIComponent(token)}/window" in PAGE
    assert "15 * 24 * 60 * 60 * 1000" not in PAGE


def test_the_plaque_carries_peak_vpi_views_and_days_in_most_popular():
    block = PAGE[PAGE.index("data-plaque-figures"):][:1500]
    for label in ("PEAK VPI", "VIEWS", "DAYS IN MOST POPULAR"):
        assert label in block
    assert "post.vpi_max ?? post.vpi_ratio" in PAGE


def test_no_expired_measurement_and_no_fifteen_day_copy():
    for gone in ("MEASUREMENT EXPIRED", "15 days", "15-day", "(15 DAYS)"):
        assert gone not in PAGE, gone


def test_a_v1_token_falls_back_to_the_archive():
    assert "claim_record_v1" in PAGE
