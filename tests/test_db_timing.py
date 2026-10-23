"""FIX-1b: TimedClient times every .execute() and keeps the slowest."""

import db_timing
from tests.pg_client import PgClient


def test_every_execute_is_timed_with_its_table_or_function(db):
    c = db_timing.timed(PgClient(db))
    assert db_timing.timed(c) is c
    c.table("ingest_run").select("day").eq("day", "2026-01-01").execute()
    c.table("posts").select("id").limit(1).execute()
    assert c.timings.calls == 2 and c.timings.label in ("ingest_run", "posts")
    note = c.timings.note()
    assert note.startswith("slowest query ") and note.endswith(", 2 calls)")


def test_the_slowest_wins():
    t = db_timing.Timings()
    t.record("a", 5.0)
    t.record("rpc close_exits_of_day", 900.4)
    t.record("b", 12.0)
    assert t.note() == "slowest query 900 ms (rpc close_exits_of_day, 3 calls)"
    assert db_timing.Timings().note() == "slowest query: no database call timed"


def test_analyze_snapshot_reads_only_the_entry_query_columns():
    """FIX-1b reopened (21/10/2026): the whole-table ANALYZE of trend_snapshot was the
    slowest call of the reading of 20/10 (5,424 ms); the latest definition analyzes only
    (day, video_id), the columns the day's entry query reads."""
    import pathlib, re
    mig = pathlib.Path(__file__).resolve().parents[1] / "supabase" / "migrations"
    defs = [f for f in sorted(mig.glob("*.sql"))
            if "function public.analyze_snapshot()" in f.read_text(encoding="utf-8")]
    latest = defs[-1].read_text(encoding="utf-8")
    assert "analyze public.trend_snapshot (day, video_id);" in latest
    assert re.search(r"grant execute on function public\.analyze_snapshot\(\) to service_role;", latest)
    assert "revoke all on function public.analyze_snapshot() from public, anon, authenticated;" in latest


def test_the_notes_carry_the_slowest_call_of_each_label():
    """FIX-1b (23/10/2026): every call near the bound shows, not only the first."""
    from db_timing import Timings
    t = Timings()
    for label, ms in (("rpc entries_of_day", 300), ("rpc entries_of_day", 900), ("rpc purge_snapshot_day", 700),
                      ("trend_snapshot", 50)):
        t.record(label, ms)
    assert t.top(2) == "slowest calls: rpc entries_of_day 900 ms x2, rpc purge_snapshot_day 700 ms x1"
    assert t.note() == "slowest query 900 ms (rpc entries_of_day, 4 calls)"


def test_one_call_returns_every_row_when_the_api_has_no_row_cap(db):
    """FIX-1b (23/10/2026): rpc_all against the real functions: one call without a cap,
    pages with a cap of 1,000, the same rows either way."""
    import census
    from tests.pg_client import PgClient, _Rpc
    client = PgClient(db)
    with db.cursor() as cur:
        cur.execute("insert into trend_snapshot(day, video_id, channel_id, format, countries, categories) "
                    "select date '2026-10-05', 'v' || lpad(g::text, 5, '0'), 'UC', 'LONG', "
                    "array['IT'], array['24'] from generate_series(1, 2345) g")
    try:
        one = census.rpc_all(client, "snapshot_export", {"p_day": "2026-10-05"}, "video_id")
        _Rpc.max_rows = 1000
        paged = census.rpc_all(client, "snapshot_export", {"p_day": "2026-10-05"}, "video_id")
    finally:
        _Rpc.max_rows = None
        with db.cursor() as cur:
            cur.execute("delete from trend_snapshot where day = date '2026-10-05'")
    assert len(one) == 2345 and one == paged
