"""APP-4 (01/10/2026): public_records, the view every public page reads.

day_n counts a charting record's days the way days_charting is written at
the close; claim_open_until is the backend's claim_window open_until; the
caller's RLS applies, so a hidden record is not in it for the public roles.
"""

from datetime import date

import main


def _record(cur, vid, status, left_on=None, days=None, hidden=False, n_daily=0):
    cur.execute(
        "insert into posts (external_post_id, author_handle, baseline_score, vpi_ratio, vpi_level, "
        "vpi_level_name, vpi_color, method_version, baseline_rule, format, status, entered_on, "
        "left_on, days_charting, hidden) values (%s, '@c', 100, 3.0, 1, 'x', '#888888', 'v2', "
        "'standard', 'LONG', %s, '2026-09-27', %s, %s, %s) returning id",
        (vid, status, left_on, days, hidden))
    pid = cur.fetchone()[0]
    for i in range(n_daily):
        cur.execute("insert into post_daily (post_id, day, day_index, views, vpi_ratio) "
                    "values (%s, %s, %s, 300, 3.0)", (pid, date(2026, 9, 27 + i), i + 1))
    return pid


def test_claim_days_mirrors_the_backend(db):
    with db.cursor() as cur:
        cur.execute("select public.claim_days()")
        assert cur.fetchone() == (main.CLAIM_DAYS,)


def test_day_n_and_the_claim_date(db):
    with db.cursor() as cur:
        _record(cur, "charting", "ACTIVE", n_daily=3)
        _record(cur, "left", "CLOSED", left_on=date(2026, 9, 30), days=3, n_daily=3)
        _record(cur, "new", "ACTIVE", n_daily=1)
        cur.execute("select external_post_id, day_n, claim_open_until from public_records "
                    "order by external_post_id")
        rows = {r[0]: r[1:] for r in cur.fetchall()}
    assert rows["charting"] == (3, None)
    assert rows["new"] == (1, None)
    w = main.claim_window({"method_version": "v2", "status": "CLOSED", "left_on": "2026-09-30"})
    assert rows["left"] == (3, date.fromisoformat(w["open_until"]))
    assert "v1_old_a" not in rows                     # v2 only


def test_the_view_applies_the_callers_rls(db):
    with db.cursor() as cur:
        cur.execute("grant select on public.posts, public.post_daily to anon")
        _record(cur, "shown", "ACTIVE", n_daily=2)
        _record(cur, "gone", "ACTIVE", hidden=True, n_daily=2)
        cur.execute("savepoint s")
        cur.execute("set local role anon")
        cur.execute("select external_post_id, day_n from public_records")
        rows = cur.fetchall()
        cur.execute("rollback to savepoint s")
        cur.execute("select reloptions from pg_class where oid = 'public.public_records'::regclass")
        assert "security_invoker=true" in cur.fetchone()[0]
    assert rows == [("shown", 2)]
