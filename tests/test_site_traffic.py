"""SOC-W4 (24/10/2026): every public page is counted by Vercel Web Analytics (02 section 6.12)."""
from pathlib import Path

FE = Path(__file__).resolve().parents[1] / "frontend"


def test_next_pages_and_the_static_room_carry_the_analytics():
    layout = (FE / "src" / "app" / "layout.tsx").read_text(encoding="utf-8")
    assert 'import { Analytics } from "@vercel/analytics/react";' in layout and "<Analytics />" in layout
    room = (FE / "public" / "room" / "index.html").read_text(encoding="utf-8")
    head = room[:room.index("</head>")]
    assert '<script defer src="/_vercel/insights/script.js"></script>' in head
    assert "window.va = window.va ||" in head


def test_the_claim_page_still_records_one_visit_per_session():
    page = (FE / "src" / "app" / "claim" / "[token]" / "page.tsx").read_text(encoding="utf-8")
    assert ".from('claim_visite')" in page and "sessionStorage.setItem(chiave, '1')" in page


def test_meta_link_scanner_visits_are_marked_automatic():
    """SOC-W4 addition (24/10/2026): referrer facebook.com / m.facebook.com = Meta's link scanner."""
    page = (FE / "src" / "app" / "claim" / "[token]" / "page.tsx").read_text(encoding="utf-8")
    assert "const SCANNER_META = new Set(['facebook.com', 'www.facebook.com', 'm.facebook.com']);" in page
    assert "if (provenienza && SCANNER_META.has(provenienza)) return true;" in page
    assert page.count("automatico: passaggioAutomatico(provenienza),") == 2      # visits and gestures
    assert "passaggioAutomatico()," not in page
