"""T-06 / T-07 / GATE-1: entries_of_day(), close_exits_of_day(), day 0,
the v1 archiving, and the partial-reading rule.

The SQL under test is the SQL applied to Supabase: every file in
supabase/migrations/ is executed verbatim, in order, on top of a minimal stub
of the pre-v2 ``posts`` table (the ``db`` fixture in conftest.py). Nothing
here is a copy of the function.

A partial reading observes presence but not absence: it can produce entries
and never exits, and it cannot serve as the reference snapshot for the
following day (01 section 4). Every fixture day therefore records its run in
ingest_run, 'ok' unless the test says otherwise.

Sources: docs/01-methodology-protocol.md sections 1 and 4;
docs/02-technical-specification.md sections 3.1, 3.1.1, 3.5, 3.6, 4.3.
"""

from datetime import date, timedelta

# 02 §3.1: retention, day 0 excluded. The cutoff is a parameter here so the
# test does not depend on today's date.
RETENTION = "delete from trend_snapshot where day < %s and permanent = false"

D0 = date(2026, 10, 1)


def d(n):
    """Day n of the fixture calendar: d(0) is day 0."""
    return D0 + timedelta(days=n)


def snap(conn, day, ids, permanent=False, run="ok"):
    """The day's snapshot and, unless run is None, its ingest_run row."""
    with conn.cursor() as cur:
        cur.executemany(
            "insert into trend_snapshot (day, video_id, channel_id, format, "
            "views, countries, categories, permanent) "
            "values (%s, %s, 'UCfixture', 'SHORT', 1000, '{IT}', '{24}', %s)",
            [(day, v, permanent) for v in ids],
        )
        if run is not None:
            cur.execute(
                "insert into ingest_run (day, started_at, outcome) values (%s, now(), %s)",
                (day, run),
            )


def day0(conn, ids):
    """What the day-0 run does: a permanent snapshot, a complete run."""
    snap(conn, d(0), ids, permanent=True)


def entries(conn, day):
    with conn.cursor() as cur:
        cur.execute("select video_id, gap_days, entry_certain from entries_of_day(%s)", (day,))
        return {v: (g, c) for v, g, c in cur.fetchall()}


def record(conn, video_id):
    with conn.cursor() as cur:
        cur.execute(
            "insert into posts (external_post_id, entered_on) values (%s, %s)",  # a v1-default row: only its presence matters here
            (video_id, D0),
        )


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


# --- day 0: excluded by the ordinary test, no list (02 §3.1.1) -----------


def test_day0_video_still_present_never_produces_a_record(db):
    day0(db, ["a"])
    for n in range(1, 10):
        snap(db, d(n), ["a"])
        assert entries(db, d(n)) == {}, f"day {n}"
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
    snap(db, d(2), ["a", "b"])  # b returns: an entry we observed
    assert entries(db, d(2)) == {"b": (0, True)}


def test_day0_video_left_unread_by_a_partial_run_is_not_an_entry(db):
    # A partial run did not read b's slice. It is not the reference, so on
    # d(2) b is compared with day 0, where it is present: not an entry.
    day0(db, ["a", "b"])
    snap(db, d(1), ["a"], run="partial")  # b unread
    snap(db, d(2), ["a", "b"])
    assert entries(db, d(2)) == {}


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


# --- T-07: the partial-reading rule ---------------------------------------


def test_a_partial_day_is_never_the_reference(db):
    day0(db, ["a"])
    snap(db, d(1), ["a"])
    snap(db, d(2), ["a"], run="partial")  # x may have been in an unread slice
    snap(db, d(3), ["a", "x"])
    # reference is d(1), the last complete reading: x's entry day is unknown
    assert entries(db, d(3)) == {"x": (2, False)}


def test_a_partial_day_does_not_hide_a_video_it_did_not_read(db):
    # Without the rule, x would be excluded as "present yesterday" on day 3
    # only if the partial read had seen it; here the partial read DID see it,
    # and the reference is still the last complete day.
    day0(db, ["a"])
    snap(db, d(1), ["a"])
    snap(db, d(2), ["a", "x"], run="partial")
    record(db, "x")  # entered on d(2), observed during the partial run
    snap(db, d(3), ["a", "x"])
    assert entries(db, d(3)) == {}


def test_entries_are_detected_during_a_partial_run_when_the_reference_is_yesterday(db):
    day0(db, ["a"])
    snap(db, d(1), ["a"])
    snap(db, d(2), ["a", "y"], run="partial")
    assert entries(db, d(2)) == {"y": (0, True)}


def test_a_run_still_in_progress_is_not_a_reference(db):
    day0(db, ["a"])
    snap(db, d(1), ["a"], run=None)
    with db.cursor() as cur:  # started, never finished: outcome null
        cur.execute("insert into ingest_run (day, started_at) values (%s, now())", (d(1),))
    snap(db, d(2), ["a", "z"])
    assert entries(db, d(2)) == {"z": (2, False)}  # reference is d(0)


def v2_record(conn, video_id, entered, days_observed):
    with conn.cursor() as cur:
        cur.execute(
            "insert into posts (external_post_id, method_version, status, entered_on, "
            "baseline_rule, baseline_score, vpi_ratio, vpi_level, vpi_level_name, vpi_color) "
            "values (%s, 'v2', 'ACTIVE', %s, 'standard', 500, 2.0, 3, 'Lvl 3 - Rising', '#0099FF') "
            "returning id",
            (video_id, entered),
        )
        pid = cur.fetchone()[0]
        cur.executemany(
            "insert into post_daily (post_id, day, day_index, views) values (%s, %s, %s, 1000)",
            [(pid, entered + timedelta(days=i), i + 1) for i in range(days_observed)],
        )


def closed(conn):
    with conn.cursor() as cur:
        cur.execute("select external_post_id, status, left_on, days_charting "
                    "from posts where method_version = 'v2' order by 1")
        return cur.fetchall()


def close(conn, day):
    with conn.cursor() as cur:
        cur.execute("select close_exits_of_day(%s)", (day,))
        return cur.fetchone()[0]


def test_close_exits_closes_only_v2_records_absent_today(db):
    day0(db, ["a"])
    snap(db, d(1), ["a", "p", "q"])
    v2_record(db, "p", d(1), 3)
    v2_record(db, "q", d(1), 3)
    snap(db, d(4), ["a", "q"], run=None)  # today's run: census complete
    assert close(db, d(4)) == 1
    assert closed(db) == [("p", "CLOSED", d(4), 3), ("q", "ACTIVE", None, None)]
    with db.cursor() as cur:  # the v1 archive is never touched
        cur.execute("select count(*) from posts_v1 where status <> 'ACTIVE'")
        assert cur.fetchone()[0] == 0


def test_close_exits_refuses_when_the_day_is_already_known_partial(db):
    day0(db, ["a"])
    snap(db, d(1), ["a", "p"])
    v2_record(db, "p", d(1), 1)
    snap(db, d(2), ["a"], run="partial")
    assert close(db, d(2)) == 0
    assert closed(db) == [("p", "ACTIVE", None, None)]


def test_close_exits_refuses_without_a_snapshot_for_the_day(db):
    day0(db, ["a"])
    snap(db, d(1), ["a", "p"])
    v2_record(db, "p", d(1), 1)
    assert close(db, d(2)) == 0  # nothing read: nothing observed absent
    assert closed(db) == [("p", "ACTIVE", None, None)]


def test_close_exits_is_not_callable_by_the_public_api_roles(db):
    with db.cursor() as cur:
        cur.execute("select has_function_privilege('anon', 'public.close_exits_of_day(date)', 'execute'), "
                    "has_function_privilege('authenticated', 'public.close_exits_of_day(date)', 'execute'), "
                    "has_function_privilege('service_role', 'public.close_exits_of_day(date)', 'execute')")
        assert cur.fetchone() == (False, False, True)


# --- 02 §3.6: archiving v1 -----------------------------------------------


def test_rows_existing_before_v2_are_archived_as_v1(db):
    """Flagged v1 (T-05), then moved out of posts into posts_v1 (02 §3.6)."""
    with db.cursor() as cur:
        cur.execute("select external_post_id, method_version from posts_v1 order by 1")
        assert cur.fetchall() == [("v1_old_a", "v1"), ("v1_old_b", "v1")]
        cur.execute("select count(*) from posts")
        assert cur.fetchone() == (0,)


def test_the_day0_list_no_longer_exists(db):
    with db.cursor() as cur:
        cur.execute("select to_regclass('public.day0_pending')")
        assert cur.fetchone() == (None,)
