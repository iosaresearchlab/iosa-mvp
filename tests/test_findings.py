"""SOC-W1 (24/10/2026): the Findings stories in frontend/content/findings.

The Next build validates a published story's front matter and data file (src/lib/findings.ts)
and, where the build can see tools/, its query. This test holds the same rules on every push,
so a story whose figures arrive without the query that produced them never goes out.
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTENT = ROOT / "frontend" / "content" / "findings"
SQL = ROOT / "tools" / "findings"
FIELDS = ("title", "date", "summary", "status", "chart", "source_sql", "og_title")


def front_matter(path):
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", path.read_text(encoding="utf-8"), re.S)
    assert m, f"{path.name}: front matter missing"
    fields = {}
    for line in m.group(1).splitlines():
        if line.strip() and not line.strip().startswith("#"):
            k, _, v = line.partition(":")
            fields[k.strip()] = v.strip().strip('"').strip("'")
    return fields, m.group(2)


def stories():
    return sorted(CONTENT.glob("*.md"))


def test_every_story_is_well_formed():
    assert stories(), "no story in frontend/content/findings"
    for md in stories():
        slug = md.stem
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug), slug
        f, body = front_matter(md)
        assert f.get("status") in ("draft", "published"), slug
        if f["status"] != "published":
            continue
        for k in FIELDS:
            assert f.get(k), f"{slug}: {k} missing"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", f["date"]), slug
        data = json.loads((CONTENT / f["chart"]).read_text(encoding="utf-8"))
        assert data["type"] in ("bar", "line") and data["measure"], slug
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["reading_date"]), slug
        assert data["points"] and all(isinstance(p["value"], (int, float)) and p["label"] for p in data["points"]), slug
        sql = SQL / f["source_sql"]
        assert sql.is_file(), f"{slug}: tools/findings/{f['source_sql']} missing"
        text = sql.read_text(encoding="utf-8").lower()
        assert not re.search(r"\b(insert|update|delete|drop|alter|create|truncate|grant)\b",
                             re.sub(r"--.*", "", text)), f"{slug}: the query must be read-only"
        assert body.strip(), f"{slug}: empty body"


def test_the_placeholder_stays_a_draft():
    f, _ = front_matter(CONTENT / "pipeline-check.md")
    assert f["status"] == "draft"
    assert (SQL / f["source_sql"]).is_file() and (CONTENT / f["chart"]).is_file()


def test_drafts_are_never_listed():
    """The sitemap, the /insights block and the index read storiePubblicate(); the pages
    build only its slugs and refuse any other (dynamicParams = false)."""
    fe = ROOT / "frontend" / "src"
    lib = (fe / "lib" / "findings.ts").read_text(encoding="utf-8")
    assert "m.status === 'published'" in lib
    for rel in ("app/sitemap.ts", "app/insights/page.tsx", "app/insights/findings/page.tsx",
                "app/insights/findings/[slug]/page.tsx", "app/insights/findings/[slug]/og.png/route.tsx"):
        src = (fe / rel).read_text(encoding="utf-8")
        assert "storiePubblicate()" in src, rel
        assert "tutteLeStorie" not in src, rel
    for rel in ("app/insights/findings/[slug]/page.tsx", "app/insights/findings/[slug]/og.png/route.tsx"):
        assert "export const dynamicParams = false" in (fe / rel).read_text(encoding="utf-8"), rel
