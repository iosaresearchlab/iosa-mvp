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
