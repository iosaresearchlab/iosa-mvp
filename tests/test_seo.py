"""SEO-1 (Search Console, 07/10/2026): every indexable page names its own
canonical URL, without a query string; every filtered or paginated home
names /. The live check is tests/check_seo.py, run after a deploy."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "frontend" / "src" / "app"
PUBLIC = ROOT / "frontend" / "public"

# /claim/ is disallowed in robots.ts: personal pages, reached by token only.
NOT_INDEXED = {"claim/[token]"}


def _check_seo():
    spec = importlib.util.spec_from_file_location("check_seo", ROOT / "tests" / "check_seo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_page_route_declares_a_canonical():
    missing = []
    for page in APP.rglob("page.tsx"):
        route = page.parent.relative_to(APP).as_posix() if page.parent != APP else ""
        if route in NOT_INDEXED:
            continue
        sources = [page.read_text(encoding="utf-8")]
        layout = page.parent / "layout.tsx"
        if layout.exists() and page.parent != APP:
            sources.append(layout.read_text(encoding="utf-8"))
        if not any("canonical" in s or "metadatiPagina(" in s for s in sources):
            missing.append(route or "/")
    assert not missing, missing


def test_the_home_names_the_home():
    page = (APP / "page.tsx").read_text(encoding="utf-8")
    assert "alternates: { canonical: '/' }" in page
    assert "'use client'" not in page                    # metadata needs a server component


def test_the_static_pages_name_themselves():
    for rel, url in (("privacy.html", "https://iosaresearch.org/privacy.html"),
                     ("terms.html", "https://iosaresearch.org/terms.html"),
                     ("room/index.html", "https://iosaresearch.org/room")):
        body = (PUBLIC / rel).read_text(encoding="utf-8")
        assert _check_seo().canonicals(body) == [url], rel


def test_the_check_reads_the_canonical_as_next_renders_it():
    c = _check_seo()
    assert c.canonicals('<link rel="canonical" href="https://iosaresearch.org/outliers"/>') == \
        ["https://iosaresearch.org/outliers"]
    assert c.canonicals("<link href='https://x.org/a?b=1&amp;c=2' rel='canonical'>") == ["https://x.org/a?b=1&c=2"]
    assert c.canonicals('<link rel="icon" href="/favicon.ico"/>') == []


def test_an_empty_path_is_the_root_and_nothing_else_is_normalised():
    c = _check_seo()
    assert c.same("https://iosaresearch.org", "https://iosaresearch.org/")
    assert not c.same("https://iosaresearch.org/?page=2", "https://iosaresearch.org/")
    assert not c.same("https://iosaresearch.org/outliers/", "https://iosaresearch.org/outliers")
