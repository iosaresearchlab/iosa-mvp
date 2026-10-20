"""FIX-1c (20/10/2026): a failed database read is never published as an
empty page. The creator page took a statement timeout for "no records" and
served a 404 that ISR kept for 6 hours; the sitemap dropped its creators,
the segment pages showed no videos. Now every server read throws on error:
the response is a 500, which no cache keeps, and an ISR page keeps its last
good version."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "src"
SERVER_READERS = [
    SRC / "lib" / "supabase-server.ts",
    SRC / "lib" / "og-card.tsx",
    SRC / "app" / "sitemap.ts",
    SRC / "app" / "outliers" / "page.tsx",
]


def test_no_server_read_turns_an_error_into_empty_data():
    for f in SERVER_READERS:
        src = f.read_text(encoding="utf-8")
        assert "if (error) return" not in src, f
        assert not re.search(r"const \{ (data|count) \} = await", src), f
        assert "catch {" not in src and ".catch(() =>" not in src, f


def test_every_awaited_read_checks_its_error():
    for f in SERVER_READERS:
        src = f.read_text(encoding="utf-8")
        reads = len(re.findall(r"const \{[^}]*\berror\b[^}]*\} = (?:await|colonna)", src))
        checks = src.count("if (error) throw") + src.count("if (archived.error) throw")
        assert checks >= reads, (f, reads, checks)


def test_the_creator_read_is_indexed():
    sql = (ROOT / "supabase" / "migrations" / "20261020153158_v2_fix1c_creator_index.sql").read_text()
    assert "posts_v2_author_idx on public.posts (author_handle, entered_on)" in sql
    assert "where method_version = 'v2'" in sql
