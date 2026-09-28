"""RET-1: rolling 7-day retention of trend_snapshot (02 section 3.1).

Owner decision 28/09/2026: keep the last 7 reading days, drop the rest, no
exception for day 0; every day leaving the window is exported to Storage,
read back and verified, and only then deleted. The SQL under test is the
migration applied to Supabase (the ``db`` fixture runs every file in
supabase/migrations/); Storage is an in-memory stand-in with the same two
calls.

Fixture days are in the past: purge_snapshot_day also checks the window
against the database clock.
"""

import gzip
import json
from datetime import date, timedelta

import pytest

import retention
import vpi_engine as eng  # noqa: E402
from tests.pg_client import PgClient

D0 = date(2026, 1, 5)
COLUMNS = {"day", "video_id", "channel_id", "format", "published_at", "views",
           "countries", "categories"}


def d(n):
    return D0 + timedelta(days=n)


def fill(db, days, ids=("a", "b", "c"), run="ok"):
    with db.cursor() as cur:
        for n in days:
            cur.executemany(
                "insert into trend_snapshot (day, video_id, channel_id, format, published_at, "
                "views, countries, categories) values (%s, %s, 'UCfixture', 'LONG', "
                "'2025-12-01T10:00:00Z', %s, '{IT,US}', '{24,10}')",
                [(d(n), f"{v}{n}", 1000 + n) for v in ids])
            if run:
                cur.execute("insert into ingest_run (day, started_at, outcome) "
                            "values (%s, now(), %s)", (d(n), run))


def days_left(db):
    with db.cursor() as cur:
        cur.execute("select distinct day from trend_snapshot order by 1")
        return [r[0] for r in cur.fetchall()]


def path(n):
    return f"trend_snapshot/{d(n).isoformat()}.jsonl.gz"


class BadReadBack(retention.MemoryStorage):
    """Stores the file, reads back one line short."""

    def get(self, p):
        lines = retention.decode(super().get(p))
        return retention.encode(lines[:-1])


class FailingOn(retention.MemoryStorage):
    """Uploads fail for paths containing `marker`."""

    def __init__(self, marker):
        super().__init__()
        self.marker = marker

    def put(self, p, blob):
        if self.marker in p:
            raise retention.ArchiveError(f"upload of {p} failed: 500")
        super().put(p, blob)


def test_keeps_the_last_seven_days_and_archives_the_rest_day0_included(db):
    fill(db, range(10))
    store = retention.MemoryStorage()
    done = retention.purge(PgClient(db), store, d(9))
    assert [a["day"] for a in done] == [d(n).isoformat() for n in range(3)]
    assert days_left(db) == [d(n) for n in range(3, 10)]          # d(3)..d(9): 7 days
    assert sorted(store.files) == [path(0), path(1), path(2)]
    assert all(a["rows"] == a["deleted"] == 3 for a in done)
    rows = [json.loads(line) for line in gzip.decompress(store.files[path(0)]).decode().splitlines()]
    assert [r["video_id"] for r in rows] == ["a0", "b0", "c0"]
    assert all(set(r) == COLUMNS and r["day"] == d(0).isoformat() for r in rows)  # every column
    assert rows[0]["countries"] == ["IT", "US"] and rows[0]["views"] == 1000


def test_nothing_older_than_the_window_nothing_happens(db):
    fill(db, range(7))
    store = retention.MemoryStorage()
    assert retention.purge(PgClient(db), store, d(6)) == []
    assert days_left(db) == [d(n) for n in range(7)] and store.files == {}
    assert retention.note(d(6), []) == f"retention: kept from {d(0).isoformat()}, nothing older"


def test_the_file_digest_is_the_sql_md5_of_the_rows(db):
    fill(db, [0], ids=("é-1", "b", "a"))
    lines = [r["line"] for r in retention._pages(PgClient(db), "snapshot_export",
                                                 {"p_day": d(0).isoformat()}, "video_id")]
    with db.cursor() as cur:
        cur.execute("select md5(string_agg(to_jsonb(s)::text, '|' order by s.video_id)) "
                    "from trend_snapshot s where day = %s", (d(0),))
        assert retention.digest(lines) == cur.fetchone()[0]


def test_a_file_that_does_not_read_back_identical_deletes_nothing(db):
    fill(db, range(10))
    with pytest.raises(retention.ArchiveError, match="differs"):
        retention.purge(PgClient(db), BadReadBack(), d(9))
    assert days_left(db) == [d(n) for n in range(10)]


def test_a_failed_upload_deletes_nothing(db):
    fill(db, range(10))
    with pytest.raises(retention.ArchiveError, match="upload"):
        retention.purge(PgClient(db), FailingOn("trend_snapshot/"), d(9))
    assert days_left(db) == [d(n) for n in range(10)]


def test_a_failure_on_one_day_keeps_that_day_and_every_later_one(db):
    fill(db, range(10))
    store = FailingOn(d(1).isoformat())
    with pytest.raises(retention.ArchiveError):
        retention.purge(PgClient(db), store, d(9))
    assert days_left(db) == [d(n) for n in range(1, 10)]          # d(0) archived and gone
    assert list(store.files) == [path(0)]


def _export(db, n):
    lines = [r["line"] for r in retention._pages(PgClient(db), "snapshot_export",
                                                 {"p_day": d(n).isoformat()}, "video_id")]
    return len(lines), retention.digest(lines)


def _purge(db, n, keep_from, rows, md5):
    return PgClient(db).rpc("purge_snapshot_day", {
        "p_day": d(n).isoformat(), "p_keep_from": keep_from.isoformat(),
        "p_rows": rows, "p_md5": md5}).execute().data


def test_the_database_refuses_a_purge_that_does_not_match_the_archive(db):
    fill(db, range(10))
    rows, md5 = _export(db, 0)
    with pytest.raises(Exception, match="purge refused"):
        _purge(db, 0, d(3), rows, "0" * 32)                       # wrong md5
    with pytest.raises(Exception, match="purge refused"):
        _purge(db, 0, d(3), rows + 1, md5)                        # wrong count
    assert days_left(db)[0] == d(0)
    assert _purge(db, 0, d(3), rows, md5) == 3                    # the right ones
    assert days_left(db)[0] == d(1)


def test_the_database_refuses_a_day_inside_the_window(db):
    fill(db, range(10))
    rows, md5 = _export(db, 5)
    with pytest.raises(Exception, match="inside the 7-day window"):
        _purge(db, 5, d(3), rows, md5)
    # and against its own clock, whatever window the caller claims
    today = date.today()
    with db.cursor() as cur:
        cur.execute("insert into trend_snapshot (day, video_id, channel_id, format, countries, "
                    "categories) values (%s, 'z', 'UCz', 'LONG', '{IT}', '{24}')", (today - timedelta(days=3),))
        cur.execute("insert into ingest_run (day, started_at, outcome) values (%s, now(), 'ok')", (today,))
        cur.execute("select md5(string_agg(to_jsonb(s)::text, '|' order by s.video_id)) "
                    "from trend_snapshot s where day = %s", (today - timedelta(days=3),))
        h = cur.fetchone()[0]
    with pytest.raises(Exception, match="inside the 7-day window"):
        PgClient(db).rpc("purge_snapshot_day", {
            "p_day": (today - timedelta(days=3)).isoformat(),
            "p_keep_from": (today + timedelta(days=30)).isoformat(),
            "p_rows": 1, "p_md5": h}).execute()


def test_the_database_refuses_the_reference_whatever_its_age(db):
    # d(0) is the last complete reading; every later day was partial.
    fill(db, [0])
    fill(db, range(1, 10), run="partial")
    rows, md5 = _export(db, 0)
    with pytest.raises(Exception, match="not older than the reference"):
        _purge(db, 0, d(3), rows, md5)
    # and through the module: the reference stays, the rest of the window too
    with pytest.raises(Exception, match="not older than the reference"):
        retention.purge(PgClient(db), retention.MemoryStorage(), d(9))
    assert days_left(db) == [d(n) for n in range(10)]


def test_only_the_service_role_may_list_export_or_purge(db):
    fns = ["public.snapshot_days_before(date)", "public.snapshot_export(date)",
           "public.purge_snapshot_day(date, date, bigint, text)"]
    with db.cursor() as cur:
        for fn in fns:
            cur.execute("select has_function_privilege('anon', %s, 'execute'), "
                        "has_function_privilege('authenticated', %s, 'execute'), "
                        "has_function_privilege('service_role', %s, 'execute')", (fn, fn, fn))
            assert cur.fetchone() == (False, False, True), fn


def test_the_archive_bucket_is_private(db):
    with db.cursor() as cur:
        cur.execute("select public, file_size_limit, allowed_mime_types from storage.buckets "
                    "where id = 'archivio'")
        assert cur.fetchone() == (False, 52428800, ["application/gzip"])


def test_the_engine_notes_the_retention_and_survives_its_failure(db):
    fill(db, range(10))
    notes = []
    eng._retention(PgClient(db), d(9), notes, FailingOn("trend_snapshot/"))
    assert notes[0].startswith("RETENTION FAILED: ArchiveError") and "no day deleted" in notes[0]
    assert days_left(db) == [d(n) for n in range(10)]
    notes = []
    eng._retention(PgClient(db), d(9), notes, retention.MemoryStorage())
    assert notes[0].startswith(f"retention: kept from {d(3).isoformat()}, archived then purged "
                               f"{d(0).isoformat()} 3 rows")
    assert days_left(db) == [d(n) for n in range(3, 10)]


def test_encode_is_deterministic_and_decode_inverts_it():
    lines = ['{"a": 1}', '{"b": "è"}']
    assert retention.encode(lines) == retention.encode(list(lines))
    assert retention.decode(retention.encode(lines)) == lines
    with pytest.raises(retention.ArchiveError, match="truncated"):
        retention.decode(gzip.compress(b'{"a": 1}'))
