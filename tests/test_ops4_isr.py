"""OPS-4 (30/10/2026): creator pages write nothing to ISR.

They were ~89% of the team's ISR write units (3.4K of ~3.8K in 12 h, Vercel
Observability) with 292K writes in 30 days against the Hobby 200K. The page is
rendered per request and kept 24 h by Vercel's CDN through a
Vercel-CDN-Cache-Control header set in next.config.ts for /creators/:handle: the
same freshness as the former `revalidate = 86400`, and the CDN cache counts no
ISR write. Second step (30/10): the country and category pages the same way, 6 h;
`/outliers` and the sitemap keep ISR at 6 h (OPS-1).
"""
import re
from pathlib import Path

FRONT = Path(__file__).resolve().parent.parent / "frontend"
PAGE = FRONT / "src" / "app" / "creators" / "[handle]" / "page.tsx"


def test_the_creator_page_is_not_isr():
    src = PAGE.read_text(encoding="utf-8")
    assert re.search(r"^export const dynamic = 'force-dynamic';", src, re.M)
    for isr in ("export const revalidate", "generateStaticParams", "export const dynamicParams"):
        assert isr not in src, isr


def test_the_cdn_keeps_creator_pages_24_hours():
    cfg = (FRONT / "next.config.ts").read_text(encoding="utf-8")
    m = re.search(r'const CREATOR_CDN_CACHE = "([^"]+)";', cfg)
    assert m and m.group(1) == "s-maxage=86400, stale-while-revalidate=604800, stale-if-error=604800"
    block = cfg[cfg.index("async headers()"):cfg.index("async redirects()")]
    assert 'source: "/creators/:handle"' in block
    assert '{ key: "Vercel-CDN-Cache-Control", value: CREATOR_CDN_CACHE }' in block
    assert "private" not in m.group(1) and "no-store" not in m.group(1)


def test_country_and_category_pages_are_not_isr_and_kept_6_hours():
    """Second step, 30/10: the writes left after the creator pages."""
    cfg = (FRONT / "next.config.ts").read_text(encoding="utf-8")
    m = re.search(r'const SEGMENT_CDN_CACHE = "([^"]+)";', cfg)
    assert m and m.group(1) == "s-maxage=21600, stale-while-revalidate=604800, stale-if-error=604800"
    block = cfg[cfg.index("async headers()"):cfg.index("async redirects()")]
    for src in ('source: "/outliers/:country"', 'source: "/categories/:category"'):
        i = block.index(src)
        assert '{ key: "Vercel-CDN-Cache-Control", value: SEGMENT_CDN_CACHE }' in block[i:i + 160], src
    for rel in ("outliers/[country]/page.tsx", "categories/[category]/page.tsx"):
        src = (FRONT / "src" / "app" / rel).read_text(encoding="utf-8")
        assert re.search(r"^export const dynamic = 'force-dynamic';", src, re.M), rel
        for isr in ("export const revalidate", "generateStaticParams"):
            assert isr not in src, (rel, isr)


def test_the_single_isr_pages_keep_six_hours():
    for rel in ("outliers/page.tsx", "sitemap.ts"):
        src = (FRONT / "src" / "app" / rel).read_text(encoding="utf-8")
        assert re.search(r"^export const revalidate = 21600;", src, re.M), rel
