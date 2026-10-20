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
