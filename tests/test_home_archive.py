"""UI-3 (01/10/2026): the home archive is paginated, filtered and counted in
the database, never in the browser.

The defect fixed: the page loaded at most 5,000 rows (MAX_RIGHE) and
filtered them client-side, so past that cap records vanished from the table,
the filter counts and the CSV. The checks: home_facets counts on the
database what the table's query selects; the page keeps no row cap, no
client-side filter and no realtime subscription; the state lives in the URL;
the CSV route reads the whole filtered set.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "src"
ARCHIVE = (SRC / "components" / "HomeArchive.tsx").read_text(encoding="utf-8")
QUERY = (SRC / "lib" / "home-query.ts").read_text(encoding="utf-8")
HOME = (SRC / "components" / "HomePage.tsx").read_text(encoding="utf-8")
EXPORT = (SRC / "app" / "api" / "export" / "route.ts").read_text(encoding="utf-8")


def _record(cur, vid, status, countries, categories, title, hidden=False):
    cur.execute(
        "insert into posts (external_post_id, author_handle, baseline_score, vpi_ratio, vpi_level, "
        "vpi_level_name, vpi_color, method_version, baseline_rule, format, status, entered_on, "
        "countries, categories, content_text, hidden) values (%s, '@c', 100, 2.0, 1, 'x', '#888888', "
        "'v2', 'standard', 'LONG', %s, '2026-09-28', %s, %s, %s, %s)",
        (vid, status, countries, categories, title, hidden))


def _facets(cur, **kw):
    args = {"p_floor": "2026-09-27", "p_status": None, "p_country": None, "p_category": None,
            "p_q": None, "p_video": None, **kw}
    cur.execute("savepoint s")
    cur.execute("set local role anon")
    cur.execute("select kind, value, n from home_facets(%(p_floor)s, %(p_status)s, %(p_country)s, "
                "%(p_category)s, %(p_q)s, %(p_video)s)", args)
    rows = {(k, v): n for k, v, n in cur.fetchall()}
    cur.execute("rollback to savepoint s")
    return rows


def test_home_facets_counts_what_the_table_selects(db):
    with db.cursor() as cur:
        cur.execute("grant select on public.posts, public.post_daily to anon")
        _record(cur, "a", "ACTIVE", ["IT", "DE"], ["Gaming"], "Official Trailer")
        _record(cur, "b", "ACTIVE", ["IT"], ["Music"], "a song")
        _record(cur, "c", "CLOSED", ["DE"], ["Gaming"], "speedrun")
        _record(cur, "h", "ACTIVE", ["IT"], ["Gaming"], "hidden trailer", hidden=True)
        f = _facets(cur, p_status="ACTIVE")
        assert f[("status", "ACTIVE")] == 2 and f[("status", "CLOSED")] == 1   # every view, the hidden one out
        assert f[("country", "IT")] == 2 and f[("country", "DE")] == 1          # in the current view only
        assert f[("category", "Gaming")] == 1 and f[("category", "Music")] == 1
        f = _facets(cur, p_country="IT")                                        # all views, Italy
        assert (f[("status", "ACTIVE")], f.get(("status", "CLOSED"))) == (2, None)
        assert f[("category", "Gaming")] == 1 and ("country", "DE") in f        # countries ignore the country filter
        f = _facets(cur, p_q="trailer")
        assert f == {("status", "ACTIVE"): 1, ("country", "IT"): 1, ("country", "DE"): 1,
                     ("category", "Gaming"): 1}
        f = _facets(cur, p_video="c")
        assert f[("status", "CLOSED")] == 1 and ("status", "ACTIVE") not in f
        cur.execute("savepoint s2")
        cur.execute("set local role anon")
        cur.execute("select count(*) from public_records where search_text ilike '%trailer%'")
        assert cur.fetchone() == (1,)
        cur.execute("rollback to savepoint s2")


def test_no_row_cap_no_client_filter_no_realtime():
    for gone in ("MAX_RIGHE", "postgres_changes", ".channel(", "filteredPosts", "range(0, MAX"):
        assert gone not in HOME and gone not in ARCHIVE, gone
    assert "count: 'exact'" in ARCHIVE and ".range(da, da + stato.perPagina - 1)" in ARCHIVE
    assert "supabase.rpc('archive_facets'" in ARCHIVE


def test_state_in_the_url_and_the_controls():
    for p in ("'view'", "'country'", "'category'", "'q'", "'sort'", "'per'", "'page'"):
        assert f"p.set({p}" in QUERY, p
    assert "export const PAGE_SIZES = [25, 50, 100] as const;" in QUERY
    assert "router.push(url" in ARCHIVE and "router.replace(url" in ARCHIVE      # back button; typing does not flood history
    for label in ('aria-label="First page"', 'aria-label="Previous page"', 'aria-label="Next page"',
                  'aria-label="Last page"', "aria-current={n === stato.pagina ? 'page' : undefined}",
                  'htmlFor="salta-pagina"', 'aria-label="Pagination"', 'aria-live="polite"', "data-skeleton"):
        assert label in ARCHIVE, label
    assert "{fmt(primo)}&ndash;{fmt(ultimo)} of" in ARCHIVE


def test_vpi_is_sorted_only_within_one_baseline_band():
    # UI-8 (owner, 01/10/2026): VPI is compared only within a baseline band
    assert "(s.ordine === 'vpi_desc' || s.ordine === 'vpi_asc') && s.banda" in QUERY
    assert "soloInBanda: true" in QUERY and QUERY.count("soloInBanda: true") == 2
    assert "return !!def && def.viste.includes(vista) && (!def.soloInBanda || !!banda);" in QUERY
    assert "if (!ordineAmmesso(ordine, vista, banda)) ordine = 'views';" in QUERY      # a URL cannot force it
    assert "disabled={o.soloInBanda && !stato.banda}" in ARCHIVE
    assert "VPI is compared only within a baseline band" in QUERY and "{SUGGERIMENTO_VPI}" in ARCHIVE
    assert "First observed (oldest)" in QUERY
    bands = [b[2] for b in __import__("main").BASELINE_BANDS]
    for b in bands:
        assert f"valore: '{b}'" in QUERY, b


def test_archive_facets_counts_bands_and_filters_by_band(db):
    with db.cursor() as cur:
        cur.execute("grant select on public.posts, public.post_daily to anon")
        _record(cur, "a", "ACTIVE", ["IT"], ["Gaming"], "x")                    # baseline 100: band 100-1k
        cur.execute("update posts set baseline_score = 50 where external_post_id = 'a'")
        _record(cur, "b", "ACTIVE", ["IT"], ["Gaming"], "y")
        _record(cur, "c", "CLOSED", ["IT"], ["Gaming"], "z")
        cur.execute("savepoint s")
        cur.execute("set local role anon")
        cur.execute("select kind, value, n from archive_facets('2026-09-27', null, null, null, null, null, null, null)")
        f = {(k, v): n for k, v, n in cur.fetchall()}
        cur.execute("select kind, value, n from archive_facets('2026-09-27', null, null, null, null, null, 100, 1000)")
        g = {(k, v): n for k, v, n in cur.fetchall()}
        cur.execute("select external_post_id from public_records where baseline_score >= 100 and baseline_score < 1000 "
                    "order by vpi_shown desc nulls last")
        rows = [r[0] for r in cur.fetchall()]
        cur.execute("rollback to savepoint s")
    assert f[("band", "<100")] == 1 and f[("band", "100-1k")] == 2
    assert g[("status", "ACTIVE")] == 1 and g[("status", "CLOSED")] == 1 and g[("band", "<100")] == 1
    assert set(rows) == {"b", "c"}


def test_csv_covers_the_whole_filtered_set_server_side():
    assert "applicaFiltri(" in EXPORT and "applicaOrdine(" in EXPORT
    assert ".range(da, da + BLOCCO - 1)" in EXPORT and "if (!data || data.length < BLOCCO) break;" in EXPORT
    assert "claim_token" not in QUERY.split("export const COLONNE_CSV")[1]
    assert "pagina: 1, perPagina: 50" in ARCHIVE                                 # the link drops page and rows


def test_the_default_view_is_all():
    # UI-6 (owner, 01/10/2026)
    assert "vista: 'all', paese: null" in QUERY
    assert "if (s.vista !== DEFAULT.vista) p.set('view', s.vista);" in QUERY


def test_the_trigram_search_index_is_dropped(db):
    """DB-1: the search works by scanning; the trigram index does not exist after the migrations."""
    with db.cursor() as cur:
        cur.execute("select count(*) from pg_indexes where indexname = 'posts_v2_search_trgm_idx'")
        assert cur.fetchone()[0] == 0
