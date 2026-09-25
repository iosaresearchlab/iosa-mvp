"""T-14 preparation: the reading day, the pg_cron schedule, the public columns.

docs/02-technical-specification.md section 5: the reading is triggered at
23:59 UTC with a second attempt at 00:30 UTC; both belong to the day just
closed. The schedule SQL is in supabase/pending/ (prepared, not applied) and
conftest runs it after the migrations.
"""

from datetime import date, datetime, timezone, timedelta

import pytest

import main
from vpi_engine import reading_day

UTC = timezone.utc


@pytest.mark.parametrize("now, expected", [
    (datetime(2026, 10, 1, 23, 59, tzinfo=UTC), date(2026, 10, 1)),    # the trigger
    (datetime(2026, 10, 2, 0, 1, tzinfo=UTC), date(2026, 10, 1)),      # Render slow to wake
    (datetime(2026, 10, 2, 0, 30, tzinfo=UTC), date(2026, 10, 1)),     # the second attempt
    (datetime(2026, 10, 2, 0, 59, tzinfo=UTC), date(2026, 10, 1)),
    (datetime(2026, 10, 2, 1, 0, tzinfo=UTC), date(2026, 10, 2)),
    (datetime(2026, 10, 2, 12, 0, tzinfo=UTC), date(2026, 10, 2)),     # a daytime manual run
    (datetime(2026, 10, 2, 2, 30, tzinfo=timezone(timedelta(hours=2))), date(2026, 10, 1)),
])
def test_reading_day(now, expected):
    assert reading_day(now) == expected


def test_reading_day_refuses_a_naive_datetime():
    with pytest.raises(ValueError):
        reading_day(datetime(2026, 10, 2, 0, 30))


def test_the_schedule_is_2359_with_a_0030_second_attempt(db):
    with db.cursor() as cur:
        cur.execute("select jobname, schedule, command, active from cron.job order by jobid")
        jobs = {r[0]: r[1:] for r in cur.fetchall()}
    assert jobs["ingestione-iosa"][0] == "59 23 * * *" and jobs["ingestione-iosa"][2] is True
    assert jobs["ingestione-iosa-retry"] == ("30 0 * * *",
                                             "select public.chiedi_un_giro_di_ingestione()", True)
    assert len(jobs) == 2


def test_public_columns_are_every_posts_column_but_the_private_ones(db):
    with db.cursor() as cur:
        cur.execute("select column_name from information_schema.columns "
                    "where table_schema = 'public' and table_name = 'posts'")
        schema = {r[0] for r in cur.fetchall()}
    public = set(main.PUBLIC_POST_COLUMNS.split(","))
    assert public == schema - set(main.PRIVATE_POST_COLUMNS)
    assert set(main.PRIVATE_POST_COLUMNS) <= schema


# --- day 0 is automatic -----------------------------------------------------------


def _run_row(cur, day, outcome):
    cur.execute("insert into ingest_run (day, started_at, outcome) values (%s, now(), %s)", (day, outcome))


def test_day0_until_a_complete_reading_exists(db):
    from tests.pg_client import PgClient
    from vpi_engine import has_complete_reading_before
    client = PgClient(db)
    d0, d1, d2 = date(2026, 9, 25), date(2026, 9, 26), date(2026, 9, 27)
    assert not has_complete_reading_before(client, d0)          # nothing yet: day 0
    with db.cursor() as cur:
        _run_row(cur, d0, "partial")
    assert not has_complete_reading_before(client, d1)          # a partial day 0 is no reference
    with db.cursor() as cur:
        _run_row(cur, d1, "ok")
    assert not has_complete_reading_before(client, d1)          # the day itself does not count
    assert has_complete_reading_before(client, d2)


def test_esegui_un_ciclo_forces_snapshot_only_on_day0(monkeypatch):
    import vpi_engine
    seen = {}

    class _Res:
        data = []

    class _Q:
        def __getattr__(self, name):
            return lambda *a, **k: self

        def execute(self):
            return _Res()

    class _C:
        def table(self, name):
            return _Q()

    monkeypatch.setattr(vpi_engine, "create_client", lambda *a: _C())
    monkeypatch.setattr(vpi_engine, "run_daily",
                        lambda client, day, **kw: seen.update(kw) or {"outcome": "ok"})
    monkeypatch.delenv("SNAPSHOT_ONLY", raising=False)
    vpi_engine.esegui_un_ciclo()
    assert seen["snapshot_only"] is True
