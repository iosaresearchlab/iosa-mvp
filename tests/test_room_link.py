"""SOC-W3 (24/10/2026): /room?c=<channel_id> lands on that channel's cabinet."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FE = ROOT / "frontend"


def test_the_query_rule_comes_before_the_plain_rewrite():
    cfg = (FE / "next.config.ts").read_text(encoding="utf-8")
    q = cfg.index('beforeFiles: [{ source: "/room", has: [{ type: "query", key: "c" }], destination: "/room/creator" }]')
    plain = cfg.index('afterFiles: [{ source: "/room", destination: "/room/index.html" }]')
    assert q < plain
    assert "'/room/creator': ['./public/room/index.html']" in cfg


def test_the_page_selects_the_cabinet_or_says_why_not():
    html = (FE / "public" / "room" / "index.html").read_text(encoding="utf-8")
    assert '<div id="notice" class="hud" role="status" hidden></div>' in html
    js = html[html.index("function fromChannel()"):]
    assert "new URLSearchParams(location.search).get('c')" in js
    assert "C.findIndex(c => c[2] === id)" in js and "flyToStack(si)" in js
    assert "if (!REEL) fromChannel();" in html


def test_the_route_names_the_channel_in_the_preview_tags():
    src = (FE / "src" / "app" / "room" / "creator" / "route.ts").read_text(encoding="utf-8")
    for tag in ("<title>", 'property="og:title"', 'property="og:url"', 'name="twitter:title"'):
        assert tag in src, tag
    assert "in The Breakout Room" in src and "/^UC[A-Za-z0-9_-]{22}$/" in src
    html = (FE / "public" / "room" / "index.html").read_text(encoding="utf-8")
    for pattern in (r"<title>[^<]*</title>", r'<meta property="og:title" content="[^"]*">',
                    r'<meta property="og:url" content="[^"]*">', r'<meta name="twitter:card" content="summary_large_image">'):
        assert len(re.findall(pattern, html)) == 1, pattern     # each replacement hits exactly one tag


def test_the_creator_cabinet_is_framed_and_the_name_trimmed():
    """SOC-W3b (24/10/2026): one framing for the search box and for /room?c=; the name trimmed."""
    html = (FE / "public" / "room" / "index.html").read_text(encoding="utf-8")
    fly = html[html.index("function flyToStack(si)"):html.index("function flyToZone(bi)")]
    assert "const h = s.top + 1.6;" in fly and "el = THREE.MathUtils.degToRad(42)" in fly
    assert "Math.cos(turn) * Math.cos(el)" in fly                  # in front of the screens (+z)
    assert html.count("flyToStack(si)") >= 3                         # search, link, definition
    src = (FE / "src" / "app" / "room" / "creator" / "route.ts").read_text(encoding="utf-8")
    assert ".replace(/\\s+/g, ' ').trim()" in src


def test_the_creator_card_is_anchored_beside_the_cabinet():
    """SOC-W3c (24/10/2026): beside the selected cabinet (right, else left), re-anchored on every
    frame (flight, drag, zoom), docked at the bottom when there is no room."""
    html = (FE / "public" / "room" / "index.html").read_text(encoding="utf-8")
    assert html.count("  showCreatorCard(si);") == 2                     # search and link, at once
    fn = html[html.index("function anchorCard()"):html.index("card.addEventListener('click'")]
    assert ".project(camera)" in fn and "x1 + GAP" in fn and "x0 - GAP - w" in fn
    assert "card.classList.add('docked')" in fn and "const GAP = 20;" in html
    loop = html[html.index("function frame()"):]
    assert loop.index("anchorCard();") > loop.index("controls.update();")   # after the camera moves
    assert "anchored = null;" in html[html.index("function showCard("):]     # any other card drops it
    assert "#card.docked{" in html and "CARD_X" not in html


def test_the_link_page_is_revalidated_by_browsers():
    src = (FE / "src" / "app" / "room" / "creator" / "route.ts").read_text(encoding="utf-8")
    assert "'Cache-Control': BROWSER_CACHE, 'CDN-Cache-Control': CDN_CACHE" in src
    assert "const BROWSER_CACHE = 'public, max-age=0, must-revalidate';" in src
