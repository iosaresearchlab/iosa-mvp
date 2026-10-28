"""SOC-TXT2 (28/10/2026, playbook rule 1): the breakout reel, the watch5 v2 reel and the
watch5 v2 card show no "usual" or "median" label or figure of their own. The chart's
reference line is labelled "1×"; both reels close on "VPI · Viral Performance Index".

The text fields that come from the spec (lede, src, hook_sub, ...) are the spec's: here they
are set to neutral text, so whatever the page shows beyond them is the template's. The render
part is skipped without Playwright's Chromium."""
import json
import pathlib
import urllib.parse

import pytest

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / "templates"
CHROMIUM = pathlib.Path("/opt/pw-browsers/chromium")
OUTRO = "VPI · Viral Performance Index"
WORDS = ("usual", "median")

needs_chromium = pytest.mark.skipif(not CHROMIUM.exists(), reason="Playwright Chromium not installed here")


def _data(name, **neutral):
    d = json.loads((TEMPLATES / name).read_text(encoding="utf-8"))
    d.update(neutral)
    return d


def _page(p, template, data, width, height):
    b = p.chromium.launch(executable_path=str(CHROMIUM))
    pg = b.new_page(viewport={"width": width, "height": height})
    pg.goto((TEMPLATES / template).as_uri() + "?d=" + urllib.parse.quote(json.dumps(data)))
    return b, pg


TEXT = """() => [document.body.innerText,
                 ...[...document.querySelectorAll('svg text')].map(t => t.textContent)].join('\\n')"""


def _reel_frames(template, data):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b, pg = _page(p, template, data, 1080, 1920)
        pg.wait_for_function("window.__ready === true", timeout=60000)
        dur = pg.evaluate("window.DURATION")
        texts = []
        for i in range(int(dur * 2) + 1):                  # every half second of the reel
            pg.evaluate(f"render({i / 2})")
            texts.append(pg.evaluate(TEXT))
        pg.evaluate(f"render({dur - 0.05})")
        outro = pg.evaluate("document.getElementById('outS').textContent")
        b.close()
    return texts, outro


@pytest.mark.parametrize("template", ["reel_breakout.html", "reel_watch5_v2.html", "card_watch5_v2.html"])
def test_no_usual_or_median_in_the_template_strings(template):
    src = (TEMPLATES / template).read_text(encoding="utf-8")
    for bad in ("median ·", "'usual'", "usual 1×", "≥ 2× its usual", "usual ${", "their own usual",
                "the median of its earlier videos", "usual <b>"):
        assert bad not in src, bad


@needs_chromium
def test_the_breakout_reel():
    texts, outro = _reel_frames("reel_breakout.html", _data("example_reel_breakout.json"))
    assert any("1×" in t for t in texts)
    assert not any(w in t.lower() for t in texts for w in WORDS)
    assert outro == OUTRO


@needs_chromium
def test_the_watch5_v2_reel():
    data = _data("example_reel_watch5.json", lede="x", src="x", hook_sub="x", out_sub="x")
    texts, outro = _reel_frames("reel_watch5_v2.html", data)
    assert any("1×" in t for t in texts)
    assert not any(w in t.lower() for t in texts for w in WORDS)
    assert outro == OUTRO


@needs_chromium
def test_the_watch5_v2_card():
    from playwright.sync_api import sync_playwright
    data = _data("example_watch5_v2.json", lede="x", src="x")
    with sync_playwright() as p:
        b, pg = _page(p, "card_watch5_v2.html", data, 1080, 1350)
        pg.wait_for_timeout(1500)
        text = pg.evaluate(TEXT)
        b.close()
    assert "1×" in text and "their own numbers" in text and "VPI" in text
    assert not any(w in text.lower() for w in WORDS)
