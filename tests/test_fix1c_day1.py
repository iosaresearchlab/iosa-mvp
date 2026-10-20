"""FIX-1c (20/10/2026): day1_band_cells() in the database gives exactly the
cells and the without-VPI counts that main._cells and main._without_vpi
computed over the rows of main._day1_rows, which were paged into memory."""
from datetime import date

import main
from tests.pg_client import PgClient

CASES = [  # (baseline, format, vpi day 1, baseline_rule, hidden, entry_certain, entered_on)
    (50, "LONG", 40.0, "standard", False, True, "2026-10-01"),
    (80, "LONG", 61.5, "standard", False, True, "2026-10-01"),
    (80, "LONG", 7.25, "standard", False, True, "2026-10-02"),
    (500, "LONG", 3.0, "standard", False, True, "2026-10-01"),
    (50_000, "LONG", 1.2, "standard", False, True, "2026-10-03"),
    (60_000, "LONG", 1.6, "standard", False, True, "2026-10-03"),
    (99_999.5, "LONG", 2.4, "standard", False, True, "2026-10-04"),
    (100_000, "LONG", 1.1, "standard", False, True, "2026-10-04"),
    (None, "LONG", None, "not_computable", False, True, "2026-10-01"),
    (None, "LONG", None, "quota_stop", False, True, "2026-10-01"),
    (None, "LONG", None, "read_failed", False, True, "2026-10-01"),
    (70, "LONG", 99.0, "standard", True, True, "2026-10-01"),      # hidden: out
    (70, "LONG", 98.0, "standard", False, False, "2026-10-01"),    # entry not certain: out
    (70, "LONG", 97.0, "standard", False, True, "2026-09-20"),     # before the series: out
    (70, "SHORT", 96.0, "standard", False, True, "2026-10-01"),    # other format: out
]


def _load(cur):
    for i, (base, fmt, vpi, rule, hidden, certain, entered) in enumerate(CASES):
        level = (1, "x", "#888888") if vpi is not None else (None, None, None)
        cur.execute(
            "insert into posts (external_post_id, author_handle, baseline_score, vpi_ratio, vpi_level, "
            "vpi_level_name, vpi_color, method_version, baseline_rule, format, status, entered_on, "
            "hidden, entry_certain) values (%s, '@c', %s, %s, %s, %s, %s, "
            "'v2', %s, %s, 'ACTIVE', %s, %s, %s) returning id",
            (f"v{i}", base, vpi, *level, rule, fmt, entered, hidden, certain))
        pid = cur.fetchone()[0]
        cur.execute("insert into post_daily (post_id, day, day_index, views, vpi_ratio) values "
                    "(%s, %s, 1, 1000, %s), (%s, %s, 2, 2000, 5.0)",
                    (pid, entered, vpi, pid, date(2026, 10, 9)))


def _reference(cur, fmt):
    """The rows _day1_rows returned, rebuilt with SQL, then the Python cells."""
    cur.execute(
        "select d.vpi_ratio, p.baseline_score, p.format, p.baseline_rule from post_daily d "
        "join posts p on p.id = d.post_id where d.day_index = 1 and p.method_version = 'v2' "
        "and p.hidden = false and p.entry_certain and p.entered_on >= %s and p.format = %s",
        (main.vpi_core.series_floor(), fmt))
    rows = [{"vpi_ratio": float(v) if v is not None else None,
             "posts": {"baseline_score": float(b) if b is not None else None, "format": f, "baseline_rule": r}}
            for v, b, f, r in cur.fetchall()]
    return main._cells(rows), main._without_vpi(rows)


def test_sql_cells_equal_the_python_cells(db, monkeypatch):
    with db.cursor() as cur:
        _load(cur)
        expected = _reference(cur, "LONG")
    monkeypatch.setattr(main, "supabase", None)
    monkeypatch.setattr(main, "supabase_service", PgClient(db))     # the service client is used
    cells, without = main._band_cells_sql("LONG")
    assert without == expected[1] == {"not_computable": 1, "pending": 2}
    assert [(c["baseline_band"], c["n"]) for c in cells] == [(c["baseline_band"], c["n"]) for c in expected[0]]
    for got, want in zip(cells, expected[0]):
        assert abs(got["median_vpi"] - want["median_vpi"]) < 1e-9, (got, want)
    assert [c["baseline_band"] for c in cells] == ["<100", "100-1k", "10k-100k", ">=100k"]


def test_the_function_is_a_definer_with_its_own_hidden_filter(db):
    with db.cursor() as cur:
        cur.execute("select prosecdef, proconfig from pg_proc where proname = 'day1_band_cells'")
        definer, config = cur.fetchone()
        cur.execute("select pg_get_functiondef('public.day1_band_cells(date, text, numeric[])'::regprocedure)")
        src = cur.fetchone()[0]
    assert definer and any(c.startswith("search_path=") for c in config)
    assert "p.hidden = false" in src and "p.entry_certain" in src and "d.day_index = 1" in src
