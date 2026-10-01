"""CHECK-2 (01/10/2026): the nightly check gives no false FAIL.

tests/check_run.sql (the query the scheduled task runs) and tests/check_run.py
(the same criteria for any day) are run on the same fixtures, the shapes of
real nights, and must agree on the verdict and on quota_stop_expected. The
day is 2026-09-30, the night whose 1,205 quota_stop records the morning pass
completed: the 02:07 UTC check must PASS it.
"""

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from psycopg.rows import dict_row

from tests import check_run as cr

ROOT = Path(__file__).resolve().parent.parent
DAY = date(2026, 9, 30)
UTC = timezone.utc

NOTES_RUN = ("slice order seed 1283498327; countries 34, categories 13; quota limit 9900; "
             "baselines stopped: 403 on playlistItems; INCIDENT: 3 entries recorded without a VPI "
             "(quota_stop); baselines: 2789 units for 2016 channels = 1.38 per channel; "
             "retention: kept from 2026-09-24, nothing older")
NOTES_PREV = ("slice order seed 2382183458; baselines: 1019 units for 1886 channels = 0.54 per "
              "channel; retention: kept from 2026-09-23, nothing older; reprocessed at "
              "2026-09-30T08:20:00+00:00 by reprocess_day: ...; 1693/1693 records completed that "
              "were written without a baseline; 0 still without a VPI; 5695 units in this pass")


def sql_for(day):
    text = (ROOT / "tests" / "check_run.sql").read_text(encoding="utf-8")
    body = "\n".join(line for line in text.splitlines() if not line.startswith("--"))
    first = "with d as (select (now() at time zone 'utc')::date - 1 as day),"
    assert body.lstrip().startswith(first)
    return body.replace(first, f"with d as (select date '{day.isoformat()}' as day),", 1)


def run(cur, day, *, started, quota, notes, outcome="ok", census=True, reprocessed=None,
        finished=True, slices_error=0):
    cur.execute(
        "insert into ingest_run (day, started_at, finished_at, outcome, quota_total, slices_error, "
        "notes, census_complete, reprocessed_at) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (day, started, started + timedelta(minutes=17) if finished else None, outcome, quota,
         slices_error, notes, census, reprocessed))


def records(cur, day, rules):
    for i, rule in enumerate(rules):
        std = rule == "standard"
        cur.execute(
            "insert into posts (external_post_id, author_handle, baseline_score, vpi_ratio, vpi_level, "
            "vpi_level_name, vpi_color, method_version, baseline_rule, format, status, entered_on) "
            "values (%s, '@c', %s, %s, %s, %s, %s, 'v2', %s, 'LONG', 'ACTIVE', %s)",
            (f"{day}-{i}", 1000 if std else None, 2.0 if std else None, 1 if std else None,
             "Lvl 1 - Standard" if std else None, "#888888" if std else None, rule, day))


def night(db, *, rules=("standard", "standard", "not_computable", "quota_stop", "quota_stop",
                        "quota_stop"),
          prev_rules=("standard", "standard"), quota=4155, notes=NOTES_RUN, census=True,
          outcome="ok", prev_pass_at=datetime(2026, 9, 30, 8, 20, tzinfo=UTC), prev_notes=NOTES_PREV):
    """30/09 as the 02:07 UTC check of 01/10 saw it, by default."""
    with db.cursor() as cur:
        run(cur, DAY - timedelta(days=1), started=datetime(2026, 9, 29, 23, 59, tzinfo=UTC),
            quota=8082, notes=prev_notes, reprocessed=prev_pass_at)
        run(cur, DAY, started=datetime(2026, 9, 30, 23, 59, tzinfo=UTC), quota=quota, notes=notes,
            census=census, outcome=outcome)
        records(cur, DAY - timedelta(days=1), prev_rules)
        records(cur, DAY, rules)
        cur.execute("insert into trend_snapshot (day, video_id, channel_id, format, countries, "
                    "categories) values (%s, 'v', 'UC', 'LONG', '{IT}', '{24}')", (DAY,))


def by_sql(db):
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(sql_for(DAY))
        return cur.fetchone()


def by_python(db):
    """check_run.py's criteria on the rows the REST reads would return."""
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute("select * from ingest_run where day = %s", (DAY,))
        runs = cur.fetchall()
        cur.execute("select * from ingest_run where day = %s", (DAY - timedelta(days=1),))
        prev = cur.fetchone()
        cur.execute("select format, baseline_rule, baseline_score, vpi_ratio from posts "
                    "where entered_on = %s and method_version = 'v2'", (DAY,))
        recs = cur.fetchall()
        cur.execute("select count(*) as n from posts where entered_on = %s and method_version = 'v2' "
                    "and baseline_rule in ('quota_stop', 'read_failed')", (DAY - timedelta(days=1),))
        waiting = cur.fetchone()["n"]
        cur.execute("select count(*) as n from snapshot_days_before(%s)",
                    (DAY - timedelta(days=cr.WINDOW_DAYS - 1),))
        stale = cur.fetchone()["n"]
        cur.execute("select * from check_run_sizes()")
        sizes = cur.fetchone()
    for r in runs + ([prev] if prev else []):
        for k in ("started_at", "reprocessed_at", "finished_at"):
            r[k] = r[k].isoformat() if r[k] else None
    f = cr.facts(runs, prev, recs, waiting, stale, sizes["db_bytes"], sizes["storage_bytes"])
    return cr.evaluate(f)


def both(db):
    s = by_sql(db)
    verdict, expected, failed = by_python(db)
    assert (s["verdict"], bool(s["quota_stop_expected"])) == (verdict, expected), (s, failed)
    return s, verdict, expected, failed


def test_2026_09_30_passes_with_its_expected_quota_stop(db):
    night(db)
    s, verdict, expected, _ = both(db)
    assert verdict == "PASS" and expected and s["quota_stop"] == 3
    assert s["same_quota_day_pass_units"] == 5695 and s["quota_total"] == 4155


def test_a_clean_day_passes(db):
    night(db, rules=("standard", "not_computable"),
          notes=NOTES_RUN.replace("baselines stopped: 403 on playlistItems; ", ""))
    assert both(db)[1] == "PASS"


def test_no_morning_pass_counts_zero_not_a_false_fail(db):
    # the reading alone exhausted the Google day: 403 at 9,200 units
    night(db, quota=9200, prev_pass_at=None, prev_notes="0 still without a VPI")
    s, verdict, expected, _ = both(db)
    assert s["same_quota_day_pass_units"] == 0 and expected and verdict == "PASS"


@pytest.mark.parametrize("change, reason", [
    # the pass was in another Pacific day: the Google day was not exhausted
    (dict(prev_pass_at=datetime(2026, 9, 30, 6, 30, tzinfo=UTC)), "quota_stop = 0 or expected"),
    # stopped, but not by Google's 403 ("403" only inside the slice seed)
    (dict(notes=NOTES_RUN.replace("baselines stopped: 403 on playlistItems; ", "")
          .replace("1283498327", "1240398327")), "quota_stop = 0 or expected"),
    (dict(prev_rules=("standard", "quota_stop")), "previous day not waiting"),
    (dict(prev_rules=("standard", "read_failed")), "previous day not waiting"),
    (dict(rules=("standard", "read_failed")), "read_failed = 0"),
    (dict(census=False), "census complete"),
    # with no quota_stop too: an incomplete census fails the day by itself
    (dict(census=False, rules=("standard",),
          notes=NOTES_RUN.replace("baselines stopped: 403 on playlistItems; ", "")), "census complete"),
    (dict(outcome="failed"), "outcome ok"),
    (dict(notes=NOTES_RUN + "; RETENTION FAILED: ArchiveError, no day deleted"),
     "no retention failure"),
    (dict(notes=NOTES_RUN.replace("retention: kept from 2026-09-24, nothing older", "")),
     "retention ran"),
])
def test_fails_only_on_the_listed_conditions(db, change, reason):
    night(db, **change)
    _, verdict, _, failed = both(db)
    assert verdict == "FAIL" and reason in failed, failed


def test_waiting_records_without_a_vpi_are_well_formed():
    assert cr.well_formed({"baseline_rule": "quota_stop", "baseline_score": None, "vpi_ratio": None})
    assert cr.well_formed({"baseline_rule": "read_failed", "baseline_score": None, "vpi_ratio": None})
    assert not cr.well_formed({"baseline_rule": "quota_stop", "baseline_score": None, "vpi_ratio": 2.0})


def test_size_thresholds():
    f = {"runs": 1, "finished": True, "quota_total": 4000, "outcome": "ok", "census_complete": True,
         "slices_error": 0, "records": 5, "read_failed": 0, "quota_stop": 0,
         "previous_day_still_waiting": 0, "bad_records": 0, "shorts": 0, "units_in_notes": True,
         "retention_ran": True, "retention_failed": False, "stale_snapshot_days": 0,
         "same_quota_day_pass_units": 0, "stopped_by_google_403": False,
         "db_bytes": cr.DB_LIMIT - 1, "storage_bytes": cr.STORAGE_LIMIT - 1}
    assert cr.evaluate(f)[0] == "PASS"
    assert "database < 400 MB" in cr.evaluate({**f, "db_bytes": cr.DB_LIMIT})[2]
    assert "Storage < 800 MB" in cr.evaluate({**f, "storage_bytes": cr.STORAGE_LIMIT})[2]


def test_the_query_and_the_script_name_the_same_rule():
    sql = (ROOT / "tests" / "check_run.sql").read_text(encoding="utf-8")
    assert f"like '%{cr.GOOGLE_403}%'" in sql
    assert f">= {cr.QUOTA_DAY_EXHAUSTED}" in sql and f"<= {cr.QUOTA_BRAKE}" in sql
    assert re.search(r"baseline_rule in \('not_computable', 'quota_stop', 'read_failed'\) "
                     r"and vpi_ratio is null", sql)
