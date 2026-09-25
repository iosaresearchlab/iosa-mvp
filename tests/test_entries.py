"""T-06: entries_of_day(), the day-0 exclusion list, and the v1 archiving.

The SQL under test is the SQL applied to Supabase: every file in
supabase/migrations/ is executed verbatim, in order, on top of a minimal stub
of the pre-v2 ``posts`` table. Nothing here is a copy of the function.

Needs a PostgreSQL database in IOSA_TEST_DATABASE_URL. Without it the tests
are skipped, unless IOSA_REQUIRE_DB_TESTS=1 (set in CI), in which case a
missing database is a failure: a skipped test is not a verdict.

Each test runs inside one transaction that is rolled back, schema included.

Sources: docs/01-methodology-protocol.md sections 1 and 4;
docs/02-technical-specification.md sections 3.1, 3.1.1, 3.5, 3.6.
"""

import os
from datetime import date, timedelta
from pathlib import Path

import pytest

MIGRATIONS = sorted(
    (Path(__file__).resolve().parent.parent / "supabase" / "migrations").glob("*.sql")
)

DB_URL = os.environ.get("IOSA_TEST_DATABASE_URL")
if not DB_URL:
    if os.environ.get("IOSA_REQUIRE_DB_TESTS") == "1":
        raise RuntimeError("IOSA_REQUIRE_DB_TESTS=1 but IOSA_TEST_DATABASE_URL is not set")
    pytest.skip("IOSA_TEST_DATABASE_URL not set", allow_module_level=True)

psycopg = pytest.importorskip("psycopg")

# The pre-v2 posts table, reduced to what the migrations touch. T-05 adds the
# v2 columns and releases the not-null on vpi_ratio / vpi_level.
POSTS_STUB = """
create table public.posts (
  id               uuid primary key default gen_random_uuid(),
  external_post_id text not null,
  vpi_ratio        numeric not null,
  vpi_level        int not null
);
"""

# 02 §3.1.1: after every complete run, drain the day-0 list.
DRAIN = """
delete from day0_pending
where video_id not in (select video_id from trend_snapshot where day = %s)
"""

# 02 §3.1: retention, day 0 excluded. The cutoff is a parameter here so the
# test does not depend on today's date.
RETENTION = "delete from trend_snapshot where day < %s and permanent = false"

D0 = date(2026, 10, 1)


def d(n):
    """Day n of the fixture calendar: d(0) is day 0."""
    return D0 + timedelta(days=n)


@pytest.fixture
def db():
    conn = psycopg.connect(DB_URL, autocommit=False)
    try:
        with conn.cursor() as cur:
            # v1 rows exist before the v2 migrations run.
            cur.execute(POSTS_STUB)
            cur.execute(
                "insert into posts (external_post_id, vpi_ratio, vpi_level) "
                "values ('v1_old_a', 3.2, 4), ('v1_old_b', 1.1, 1)"
            )
            for f in MIGRATIONS:
                cur.execute(f.read_text(encoding="utf-8"))
        yield conn
    finally:
        conn.rollback()
        conn.close()


def snap(conn, day, ids, permanent=False):
    with conn.cursor() as cur:
        cur.executemany(
            "insert into trend_snapshot (day, video_id, channel_id, format, "
            "views, countries, categories, permanent) "
            "values (%s, %s, 'UCfixture', 'SHORT', 1000, '{IT}', '{24}', %s)",
            [(day, v, permanent) for v in ids],
        )


def day0(conn, ids):
    """What the day-0 run does: permanent snapshot, list seeded from it."""
    snap(conn, d(0), ids, permanent=True)
    with conn.cursor() as cur:
        cur.execute(
            "insert into day0_pending select video_id from trend_snapshot where day = %s",
            (d(0),),
        )


def entries(conn, day):
    with conn.cursor() as cur:
        cur.execute("select video_id, gap_days, entry_certain from entries_of_day(%s)", (day,))
        return {v: (g, c) for v, g, c in cur.fetchall()}


def record(conn, video_id):
    with conn.cursor() as cur:
        cur.execute(
            "insert into posts (external_post_id, entered_on) values (%s, %s)",
            (video_id, D0),
        )


def drain(conn, day):
    with conn.cursor() as cur:
        cur.execute(DRAIN, (day,))


# --- the cases named in 08 T-06 ------------------------------------------


def test_day0_with_no_previous_snapshot_produces_no_entries(db):
    # Even before the list is seeded: with nothing to compare against, no
    # entry is observable (01 §4, "Day 0 — snapshot only").
    snap(db, d(0), ["a", "b"], permanent=True)
    assert entries(db, d(0)) == {}


def test_normal_entry_is_certain_with_no_gap(db):
    day0(db, ["a", "b"])
    snap(db, d(1), ["a", "b", "c"])
    assert entries(db, d(1)) == {"c": (0, True)}


def test_exit_is_not_an_entry(db):
    day0(db, ["a"])
    snap(db, d(1), ["a", "c"])
    record(db, "c")
    snap(db, d(2), ["a"])  # c left the charts
    assert entries(db, d(2)) == {}


def test_reentry_produces_no_new_record(db):
    day0(db, ["a"])
    snap(db, d(1), ["a", "c"])
    record(db, "c")
    snap(db, d(2), ["a"])
    snap(db, d(3), ["a", "c"])  # c comes back
    assert entries(db, d(3)) == {}


def test_missing_day_never_produces_a_certain_entry(db):
    day0(db, ["a"])
    snap(db, d(1), ["a", "b"])
    record(db, "b")
    # no reading on d(2)
    snap(db, d(3), ["a", "b", "e"])
    assert entries(db, d(3)) == {"e": (2, False)}


def test_every_record_after_a_gap_is_uncertain(db):
    day0(db, ["a"])
    snap(db, d(1), ["a"])
    # no readings on d(2), d(3), d(4)
    snap(db, d(5), ["a", "e", "f"])
    got = entries(db, d(5))
    assert set(got) == {"e", "f"}
    assert all(certain is False and gap == 4 for gap, certain in got.values())


# --- the day-0 cases decided on 25/09 ------------------------------------


def test_day0_video_still_present_never_produces_a_record(db):
    day0(db, ["a"])
    for n in range(1, 10):
        snap(db, d(n), ["a"])
        assert entries(db, d(n)) == {}, f"day {n}"
        drain(db, d(n))
    # past the 7-day buffer, and after retention ran
    with db.cursor() as cur:
        cur.execute(RETENTION, (d(9) - timedelta(days=7),))
    snap(db, d(10), ["a"])
    assert entries(db, d(10)) == {}


def test_day0_video_present_across_a_gap_still_produces_no_record(db):
    day0(db, ["a"])
    # no reading on d(1)
    snap(db, d(2), ["a"])
    assert entries(db, d(2)) == {}


def test_day0_video_observed_absent_then_returning_produces_a_record(db):
    day0(db, ["a", "b"])
    snap(db, d(1), ["a"])  # b observed absent
    assert entries(db, d(1)) == {}
    drain(db, d(1))
    snap(db, d(2), ["a", "b"])  # b returns: an entry we observed
    assert entries(db, d(2)) == {"b": (0, True)}


def test_day0_video_left_unread_by_a_partial_run_is_not_an_entry(db):
    # The case the list exists for (02 §3.1.1): a partial run did not read
    # b's slice, so b is missing from the previous snapshot. A partial run
    # does not drain, so b is still pending and must not enter.
    day0(db, ["a", "b"])
    snap(db, d(1), ["a"])  # partial run: b unread, no drain
    snap(db, d(2), ["a", "b"])
    assert entries(db, d(2)) == {}


def test_drain_removes_only_ids_absent_today(db):
    day0(db, ["a", "b", "c"])
    snap(db, d(1), ["a", "c", "x"])
    drain(db, d(1))
    with db.cursor() as cur:
        cur.execute("select video_id from day0_pending order by 1")
        assert [r[0] for r in cur.fetchall()] == ["a", "c"]


def test_retention_keeps_day0_and_drops_old_working_rows(db):
    day0(db, ["a"])
    for n in range(1, 11):
        snap(db, d(n), ["a"])
    with db.cursor() as cur:
        cur.execute(RETENTION, (d(10) - timedelta(days=7),))
        cur.execute("select day, permanent from trend_snapshot order by day")
        rows = cur.fetchall()
    assert rows[0] == (d(0), True)
    assert [r[0] for r in rows[1:]] == [d(n) for n in range(3, 11)]


def test_draining_never_touches_the_day0_archive(db):
    day0(db, ["a", "b"])
    snap(db, d(1), [])
    drain(db, d(1))
    with db.cursor() as cur:
        cur.execute("select count(*) from day0_pending")
        assert cur.fetchone()[0] == 0
        cur.execute("select count(*) from trend_snapshot where day = %s and permanent", (d(0),))
        assert cur.fetchone()[0] == 2


# --- 02 §3.6: archiving v1 -----------------------------------------------


def test_rows_existing_before_v2_are_archived_as_v1_and_new_rows_default_to_v2(db):
    with db.cursor() as cur:
        cur.execute("select external_post_id, method_version from posts order by 1")
        assert cur.fetchall() == [("v1_old_a", "v1"), ("v1_old_b", "v1")]
        cur.execute(
            "insert into posts (external_post_id, entered_on) values ('new', %s) "
            "returning method_version, vpi_ratio",
            (d(1),),
        )
        assert cur.fetchone() == ("v2", None)
